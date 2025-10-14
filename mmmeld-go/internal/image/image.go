package image

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"mmmeld/internal/config"
	"mmmeld/internal/fileutil"
)

type MediaInput struct {
	Path        string
	IsVideo     bool
	IsGenerated bool
}

type OpenAIImageRequest struct {
	Model   string `json:"model"`
	Prompt  string `json:"prompt"`
	N       int    `json:"n"`
	Size    string `json:"size"`
	Quality string `json:"quality,omitempty"`
}

type OpenAIImageResponse struct {
	Data []struct {
		URL string `json:"url"`
	} `json:"data"`
}

type OpenAIChatRequest struct {
	Model    string    `json:"model"`
	Messages []Message `json:"messages"`
}

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type OpenAIChatResponse struct {
	Choices []struct {
		Message Message `json:"message"`
	} `json:"choices"`
}

// GetImageInputs processes image/video inputs from configuration
func GetImageInputs(cfg *config.Config, title, description string, cleanup *fileutil.CleanupManager) ([]MediaInput, error) {
	var inputs []MediaInput
	
	if cfg.Image != "" {
		log.Printf("Processing image inputs: %s", cfg.Image)
		
		inputPaths := strings.Split(cfg.Image, ",")
		for _, inputPath := range inputPaths {
			inputPath = strings.TrimSpace(inputPath)
			
			input, err := processImageInput(inputPath, cfg.ImageDescription, title, description, cleanup)
			if err != nil {
				return nil, fmt.Errorf("failed to process image input %s: %w", inputPath, err)
			}
			
			inputs = append(inputs, *input)
		}
	} else if cfg.AutoFill {
		log.Println("Auto-generating default image")
		
		imageDesc := cfg.ImageDescription
		if imageDesc == "" {
			if title != "" {
				imageDesc = fmt.Sprintf("A visual representation of audio titled %s", title)
			} else {
				imageDesc = "A visually engaging background image"
			}
		}
		
		input, err := generateImage(imageDesc, title, cleanup)
		if err != nil {
			return nil, fmt.Errorf("failed to generate default image: %w", err)
		}
		
		inputs = append(inputs, *input)
	}
	
	log.Printf("Processed %d media inputs", len(inputs))
	return inputs, nil
}

func processImageInput(inputPath, imageDescription, title, description string, cleanup *fileutil.CleanupManager) (*MediaInput, error) {
	switch {
	case strings.ToLower(inputPath) == "generate":
		desc := imageDescription
		if desc == "" {
			if description != "" {
				// Use the raw audio prompt to avoid encouraging text overlays in the image
				desc = description
			} else if title != "" {
				desc = fmt.Sprintf("A visual representation of audio titled %s", title)
			} else {
				desc = "A visually engaging background image"
			}
		}
		log.Printf("Generating image with description: %s", desc)
		return generateImage(desc, title, cleanup)
		
	case fileutil.IsYouTubeURL(inputPath):
		log.Printf("Downloading YouTube video: %s", inputPath)
		videoPath, err := fileutil.DownloadYouTubeVideo(inputPath, cleanup)
		if err != nil {
			return nil, err
		}
		return &MediaInput{
			Path:    videoPath,
			IsVideo: true,
		}, nil
		
	case strings.HasPrefix(inputPath, "http"):
		log.Printf("Downloading image from URL: %s", inputPath)
		imagePath, err := fileutil.DownloadImage(inputPath, cleanup)
		if err != nil {
			return nil, err
		}
		return &MediaInput{
			Path: imagePath,
		}, nil
		
	case fileutil.FileExists(inputPath):
		log.Printf("Using local file: %s", inputPath)
		isVideo := IsVideoFile(inputPath)
		return &MediaInput{
			Path:    inputPath,
			IsVideo: isVideo,
		}, nil
		
	default:
		return nil, fmt.Errorf("invalid image/video input: %s", inputPath)
	}
}

func generateImage(description, title string, cleanup *fileutil.CleanupManager) (*MediaInput, error) {
	if err := fileutil.EnsureTempFolder(); err != nil {
		return nil, fmt.Errorf("failed to create temp folder: %w", err)
	}
	
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		apiKey = os.Getenv("OPENAI_PERSONAL_API_KEY")
	}
	if apiKey == "" {
		return nil, fmt.Errorf("OpenAI API key not found in environment")
	}
	
	maxRetries := 5
	prompt := description
	var lastErr error
	for attempt := 0; attempt < maxRetries; attempt++ {
		// Enhance the prompt each attempt; pass isRetry=true on subsequent attempts
		enhancedPrompt, err := enhanceImagePrompt(prompt, apiKey, attempt > 0)
		if err != nil {
			log.Printf("Failed to enhance prompt (attempt %d), using original: %v", attempt+1, err)
			enhancedPrompt = prompt
		}
		
		imageURL, err := generateDALLEImage(enhancedPrompt, apiKey)
		if err == nil {
			// Download the generated image, using title and original description to derive the filename
			imagePath, dlErr := downloadGeneratedImage(imageURL, title, description, cleanup)
			if dlErr != nil {
				return nil, fmt.Errorf("failed to download generated image: %w", dlErr)
			}
			return &MediaInput{Path: imagePath, IsGenerated: true}, nil
		}
		
		lastErr = err
		if strings.Contains(err.Error(), "content_policy_violation") {
			log.Printf("DALL-E content policy violation on attempt %d/%d. Retrying with a safer prompt...", attempt+1, maxRetries)
			// On retry, modify the prompt slightly to encourage safer content
			prompt = prompt + " (safe, descriptive, no sensitive content)"
			continue
		}
		
		// Non-policy errors: do not retry
		break
	}
	
	return nil, fmt.Errorf("failed to generate image after %d attempts: %w", maxRetries, lastErr)
}

func enhanceImagePrompt(description, apiKey string, isRetry bool) (string, error) {
	systemContent := "You are a helpful assistant that creates high-quality, safe image prompts for DALL-E based on user descriptions."
	if len(description) < 15 {
		systemContent += " Always include visual elements that represent music or audio in your prompts, even if not explicitly mentioned in the description."
	}
	if isRetry {
		systemContent += " The previous prompt may have violated content policy. Create a new, safe prompt that avoids sensitive or controversial topics."
	}
	
	userContent := fmt.Sprintf("Create a detailed, high-quality image prompt for DALL-E based on this description: %s", description)
	if len(description) < 15 {
		userContent += " Ensure to include visual elements representing music or audio."
	}
	
	request := OpenAIChatRequest{
		Model: "gpt-3.5-turbo",
		Messages: []Message{
			{Role: "system", Content: systemContent},
			{Role: "user", Content: userContent},
		},
	}
	
	jsonData, err := json.Marshal(request)
	if err != nil {
		return "", fmt.Errorf("failed to marshal chat request: %w", err)
	}
	
	req, err := http.NewRequest("POST", "https://api.openai.com/v1/chat/completions", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("failed to create chat request: %w", err)
	}
	
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")
	
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to make chat request: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("OpenAI chat API error %d: %s", resp.StatusCode, string(body))
	}
	
	var chatResp OpenAIChatResponse
	if err := json.NewDecoder(resp.Body).Decode(&chatResp); err != nil {
		return "", fmt.Errorf("failed to decode chat response: %w", err)
	}
	
	if len(chatResp.Choices) == 0 {
		return "", fmt.Errorf("no chat response received")
	}
	
	return chatResp.Choices[0].Message.Content, nil
}

func generateDALLEImage(prompt, apiKey string) (string, error) {
	request := OpenAIImageRequest{
		Model:   "dall-e-3",
		Prompt:  prompt,
		N:       1,
		Size:    "1024x1024",
		Quality: "standard",
	}
	
	jsonData, err := json.Marshal(request)
	if err != nil {
		return "", fmt.Errorf("failed to marshal image request: %w", err)
	}
	
	req, err := http.NewRequest("POST", "https://api.openai.com/v1/images/generations", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("failed to create image request: %w", err)
	}
	
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")
	
	client := &http.Client{Timeout: 60 * time.Second} // DALL-E can take longer
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to make image request: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("DALL-E API error %d: %s", resp.StatusCode, string(body))
	}
	
	var imageResp OpenAIImageResponse
	if err := json.NewDecoder(resp.Body).Decode(&imageResp); err != nil {
		return "", fmt.Errorf("failed to decode image response: %w", err)
	}
	
	if len(imageResp.Data) == 0 {
		return "", fmt.Errorf("no image URL received")
	}
	
	return imageResp.Data[0].URL, nil
}

func downloadGeneratedImage(imageURL, title, description string, cleanup *fileutil.CleanupManager) (string, error) {
	resp, err := http.Get(imageURL)
	if err != nil {
		return "", fmt.Errorf("failed to download generated image: %w", err)
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("failed to download image: HTTP %d", resp.StatusCode)
	}
	
	// Create filename using title and a snippet of the description. Avoid generic prefixes.
	sanitizedTitle := fileutil.SanitizeFilename(title)
	sanitizedDesc := fileutil.SanitizeFilename(description)
	if len(sanitizedDesc) > 50 {
		sanitizedDesc = sanitizedDesc[:50]
	}
	var nameParts []string
	if sanitizedTitle != "" {
		nameParts = append(nameParts, sanitizedTitle)
	}
	if sanitizedDesc != "" {
		nameParts = append(nameParts, sanitizedDesc)
	}
	name := strings.Join(nameParts, "_")
	if name == "" {
		name = fmt.Sprintf("%d", time.Now().UnixNano())
	}
	filename := name + ".png"
	imagePath := filepath.Join(config.TempAssetsFolder, filename)
	
	file, err := os.Create(imagePath)
	if err != nil {
		return "", fmt.Errorf("failed to create image file: %w", err)
	}
	defer file.Close()
	
	_, err = io.Copy(file, resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to save image: %w", err)
	}
	
	cleanup.Add(imagePath)
	log.Printf("Downloaded generated image: %s", imagePath)
	
	return imagePath, nil
}

// IsVideoFile checks if a file is a video based on its extension
func IsVideoFile(filePath string) bool {
	ext := strings.ToLower(filepath.Ext(filePath))
	videoExts := []string{".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv", ".flv", ".m4v"}
	
	for _, videoExt := range videoExts {
		if ext == videoExt {
			return true
		}
	}
	
	return false
}

// IsImageFile checks if a file is an image based on its extension
func IsImageFile(filePath string) bool {
	ext := strings.ToLower(filepath.Ext(filePath))
	imageExts := []string{".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
	
	for _, imageExt := range imageExts {
		if ext == imageExt {
			return true
		}
	}
	
	return false
}

// GetMediaType returns the type of media file
func GetMediaType(filePath string) string {
	if IsVideoFile(filePath) {
		return "video"
	}
	if IsImageFile(filePath) {
		return "image"
	}
	return "unknown"
}
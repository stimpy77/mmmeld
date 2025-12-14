package image

import (
	"bytes"
	"context"
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
	"mmmeld/internal/genai"
)

type MediaInput struct {
	Path        string
	IsVideo     bool
	IsGenerated bool
}

// ImageGenOptions contains options for image generation including validation
type ImageGenOptions struct {
	Description  string
	Title        string
	Provider     config.ImageProvider
	Caption      string             // Expected caption text for validation
	Subcaption   string             // Expected subcaption text for validation
	AspectRatio  config.AspectRatio // Aspect ratio for generated image
	MaxRetries   int                // Max retries for validation failures (default 10)
	ValidateText bool               // Whether to validate text rendering
	AttemptNum   int                // Current attempt number for file naming (1-based)
	StyleType    string             // Ideogram style type (AUTO, GENERAL, REALISTIC, DESIGN, FICTION)
	StylePreset  string             // Ideogram style preset (e.g., CINEMATIC, OIL_PAINTING, etc.)
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

// Ideogram API types
type IdeogramRequest struct {
	Prompt         string `json:"prompt"`
	AspectRatio    string `json:"aspect_ratio,omitempty"`
	RenderingSpeed string `json:"rendering_speed,omitempty"`
	StyleType      string `json:"style_type,omitempty"`
	StylePreset    string `json:"style_preset,omitempty"`
}

type IdeogramResponse struct {
	Data []struct {
		URL string `json:"url"`
	} `json:"data"`
}

// GetImageInputs processes image/video inputs from configuration
func GetImageInputs(cfg *config.Config, title, description string, cleanup *fileutil.CleanupManager) ([]MediaInput, error) {
	return GetImageInputsWithAudio(cfg, title, description, "", cleanup)
}

// GetImageInputsWithAudio processes image/video inputs from configuration,
// optionally analyzing an audio file to generate an image prompt using Gemini.
func GetImageInputsWithAudio(cfg *config.Config, title, description, audioPath string, cleanup *fileutil.CleanupManager) ([]MediaInput, error) {
	var inputs []MediaInput

	// If analyze-audio is enabled and we have an audio file, generate prompt from audio
	audioGeneratedPrompt := ""
	if cfg.AnalyzeAudio && audioPath != "" && genai.IsAudioFile(audioPath) {
		log.Println("Analyzing audio with Gemini to generate image prompt...")
		// Use AudioNotes if provided, otherwise fall back to description
		notes := cfg.AudioNotes
		if notes == "" {
			notes = description
		}
		prompt, err := analyzeAudioForPrompt(audioPath, title, notes, cfg.ImageCaption, cfg.ImageSubcaption, cfg.ImageStyle)
		if err != nil {
			log.Printf("Warning: Audio analysis failed, falling back to default: %v", err)
		} else {
			audioGeneratedPrompt = prompt
			log.Printf("Generated prompt from audio:\n%s", prompt)
		}
	}

	if cfg.Image != "" {
		log.Printf("Processing image inputs: %s", cfg.Image)

		inputPaths := strings.Split(cfg.Image, ",")
		for _, inputPath := range inputPaths {
			inputPath = strings.TrimSpace(inputPath)

			// Use audio-generated prompt if available and this is a "generate" request
			effectiveDesc := cfg.ImageDescription
			if audioGeneratedPrompt != "" && strings.ToLower(inputPath) == "generate" && effectiveDesc == "" {
				effectiveDesc = audioGeneratedPrompt
			}

			// Build options with caption/subcaption for validation
			opts := ImageGenOptions{
				Description:  effectiveDesc,
				Title:        title,
				Provider:     cfg.ImageProvider,
				Caption:      cfg.ImageCaption,
				Subcaption:   cfg.ImageSubcaption,
				AspectRatio:  cfg.AspectRatio,
				ValidateText: cfg.ImageCaption != "" || cfg.ImageSubcaption != "",
				MaxRetries:   10,
				StyleType:    cfg.StyleType,
				StylePreset:  cfg.StylePreset,
			}

			input, err := processImageInputWithOpts(inputPath, opts, description, cleanup)
			if err != nil {
				return nil, fmt.Errorf("failed to process image input %s: %w", inputPath, err)
			}

			inputs = append(inputs, *input)
		}
	} else if cfg.AutoFill {
		log.Println("Auto-generating default image")

		imageDesc := cfg.ImageDescription
		if imageDesc == "" {
			// Prefer audio-generated prompt, then title-based fallback
			if audioGeneratedPrompt != "" {
				imageDesc = audioGeneratedPrompt
			} else if title != "" {
				imageDesc = fmt.Sprintf("A visual representation of audio titled %s", title)
			} else {
				imageDesc = "A visually engaging background image"
			}
		}

		opts := ImageGenOptions{
			Description:  imageDesc,
			Title:        title,
			Provider:     cfg.ImageProvider,
			Caption:      cfg.ImageCaption,
			Subcaption:   cfg.ImageSubcaption,
			AspectRatio:  cfg.AspectRatio,
			ValidateText: cfg.ImageCaption != "" || cfg.ImageSubcaption != "",
			MaxRetries:   10,
			StyleType:    cfg.StyleType,
			StylePreset:  cfg.StylePreset,
		}

		input, err := generateImageWithValidation(opts, cleanup)
		if err != nil {
			return nil, fmt.Errorf("failed to generate default image: %w", err)
		}

		inputs = append(inputs, *input)
	}

	log.Printf("Processed %d media inputs", len(inputs))
	return inputs, nil
}

func processImageInputWithOpts(inputPath string, opts ImageGenOptions, fallbackDesc string, cleanup *fileutil.CleanupManager) (*MediaInput, error) {
	switch {
	case strings.ToLower(inputPath) == "generate":
		desc := opts.Description
		if desc == "" {
			if fallbackDesc != "" {
				desc = fallbackDesc
			} else if opts.Title != "" {
				desc = fmt.Sprintf("A visual representation of audio titled %s", opts.Title)
			} else {
				desc = "A visually engaging background image"
			}
			opts.Description = desc
		}
		log.Printf("Generating image with %s: %s", opts.Provider, desc)
		return generateImageWithValidation(opts, cleanup)

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

func generateImage(description, title string, provider config.ImageProvider, cleanup *fileutil.CleanupManager) (*MediaInput, error) {
	if err := fileutil.EnsureTempFolder(); err != nil {
		return nil, fmt.Errorf("failed to create temp folder: %w", err)
	}

	// Route to appropriate provider
	switch provider {
	case config.ImageProviderDALLE:
		return generateDALLEImage3(description, title, 1, cleanup)
	case config.ImageProviderIdeogram:
		fallthrough
	default:
		return generateIdeogramImage(description, title, cleanup)
	}
}

// GenerateAndValidateImage is a public wrapper for generateImageWithValidation
func GenerateAndValidateImage(opts ImageGenOptions, cleanup *fileutil.CleanupManager) (*MediaInput, error) {
	return generateImageWithValidation(opts, cleanup)
}

// generateImageWithValidation generates an image and validates text rendering using Gemini
func generateImageWithValidation(opts ImageGenOptions, cleanup *fileutil.CleanupManager) (*MediaInput, error) {
	if err := fileutil.EnsureTempFolder(); err != nil {
		return nil, fmt.Errorf("failed to create temp folder: %w", err)
	}

	maxRetries := opts.MaxRetries
	if maxRetries <= 0 {
		maxRetries = 10
	}

	var lastErr error
	var bestInput *MediaInput
	var bestScore float64 = 0

	// Track all generated images to clean up non-best at the end
	type attemptResult struct {
		input *MediaInput
		score float64
	}
	var allAttempts []attemptResult

	for attempt := 1; attempt <= maxRetries; attempt++ {
		// Generate the image - pass attempt number for file naming
		var input *MediaInput
		var err error

		// Set attempt number for file naming
		attemptOpts := opts
		attemptOpts.AttemptNum = attempt

		switch opts.Provider {
		case config.ImageProviderDALLE:
			input, err = generateDALLEImage3(opts.Description, opts.Title, attempt, cleanup)
		case config.ImageProviderIdeogram:
			fallthrough
		default:
			input, err = generateIdeogramImageWithOpts(attemptOpts, cleanup)
		}

		if err != nil {
			lastErr = err
			log.Printf("Image generation failed on attempt %d/%d: %v", attempt, maxRetries, err)
			continue
		}

		// If validation not needed, return immediately (clean up any previous attempts)
		if !opts.ValidateText || (opts.Caption == "" && opts.Subcaption == "") {
			// Clean up any previous attempts
			for _, prev := range allAttempts {
				if prev.input != nil && cleanup != nil && strings.Contains(prev.input.Path, "temp_assets") {
					os.Remove(prev.input.Path)
				}
			}
			// Preserve the selected image from cleanup
			if cleanup != nil {
				cleanup.Remove(input.Path)
			}
			return input, nil
		}

		// Validate text rendering with Gemini
		log.Printf("Validating image text rendering (attempt %d/%d)...", attempt, maxRetries)
		result, err := genai.ValidateGeneratedImage(input.Path, opts.Caption, opts.Subcaption)
		if err != nil {
			log.Printf("Warning: Image validation failed, accepting image: %v", err)
			// Clean up any previous attempts
			for _, prev := range allAttempts {
				if prev.input != nil && cleanup != nil && strings.Contains(prev.input.Path, "temp_assets") {
					os.Remove(prev.input.Path)
				}
			}
			// Preserve the selected image from cleanup
			if cleanup != nil {
				cleanup.Remove(input.Path)
			}
			return input, nil
		}

		// Track this attempt (keep all images until we know which is best)
		allAttempts = append(allAttempts, attemptResult{input: input, score: result.Score})

		// Track best scoring image
		if result.Score > bestScore {
			bestInput = input
			bestScore = result.Score
		}

		if result.IsAcceptable {
			log.Printf("✓ Image text validation passed (score: %.1f)", result.Score)
			// Clean up non-selected images
			for _, prev := range allAttempts {
				if prev.input != nil && prev.input.Path != input.Path && cleanup != nil && strings.Contains(prev.input.Path, "temp_assets") {
					os.Remove(prev.input.Path)
				}
			}
			// Preserve the selected image from cleanup
			if cleanup != nil {
				cleanup.Remove(input.Path)
			}
			return input, nil
		}

		// Validation failed - log issues and retry
		log.Printf("✗ Image text validation failed (attempt %d/%d, score: %.1f):", attempt, maxRetries, result.Score)
		for _, issue := range result.Issues {
			log.Printf("  - %s", issue)
		}
		if len(result.Suggestions) > 0 {
			log.Printf("  Suggestions:")
			for _, suggestion := range result.Suggestions {
				log.Printf("    • %s", suggestion)
			}
		}

		if attempt < maxRetries {
			log.Printf("Retrying image generation... (best score so far: %.1f)", bestScore)
		}
	}

	// If best score is above minimum threshold (6.0), use it with a warning
	if bestInput != nil && bestScore > 6.0 {
		log.Printf("Warning: Text validation failed after %d attempts, using best image (score: %.1f)", maxRetries, bestScore)
		// Clean up non-best images
		for _, prev := range allAttempts {
			if prev.input != nil && prev.input.Path != bestInput.Path && cleanup != nil && strings.Contains(prev.input.Path, "temp_assets") {
				os.Remove(prev.input.Path)
			}
		}
		// Preserve the selected image from cleanup
		if cleanup != nil {
			cleanup.Remove(bestInput.Path)
		}
		return bestInput, nil
	}

	// Score too low (≤6.0) - fail and retain all images for inspection
	if bestInput != nil {
		log.Printf("ERROR: Best score %.1f is below minimum threshold (6.0) after %d attempts", bestScore, maxRetries)
		log.Printf("Retaining all %d generated images in temp_assets for inspection", len(allAttempts))
		// Preserve all images from cleanup so user can inspect them
		for _, prev := range allAttempts {
			if prev.input != nil && cleanup != nil {
				cleanup.Remove(prev.input.Path)
			}
		}
		return nil, fmt.Errorf("image validation failed: best score %.1f is below minimum threshold (6.0) after %d attempts", bestScore, maxRetries)
	}

	return nil, fmt.Errorf("failed to generate image after %d attempts: %w", maxRetries, lastErr)
}

// generateDALLEImage3 generates an image using DALL-E 3 with retry logic
func generateDALLEImage3(description, title string, attemptNum int, cleanup *fileutil.CleanupManager) (*MediaInput, error) {
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
			// Download the generated image with attempt number for naming
			imagePath, dlErr := downloadGeneratedImage(imageURL, title, description, attemptNum, cleanup)
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

// generateIdeogramImage generates an image using Ideogram v3 API (legacy wrapper)
func generateIdeogramImage(description, title string, cleanup *fileutil.CleanupManager) (*MediaInput, error) {
	opts := ImageGenOptions{
		Description: description,
		Title:       title,
		AspectRatio: config.AspectRatio16x9, // Default to 16:9
		AttemptNum:  1,                      // Default to attempt 1
	}
	return generateIdeogramImageWithOpts(opts, cleanup)
}

// generateIdeogramImageWithOpts generates an image using Ideogram v3 API with full options
func generateIdeogramImageWithOpts(opts ImageGenOptions, cleanup *fileutil.CleanupManager) (*MediaInput, error) {
	apiKey := os.Getenv("IDEOGRAM_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("IDEOGRAM_API_KEY not found in environment")
	}

	aspectRatioStr := opts.AspectRatio.IdeogramAspectRatio()

	// When using style_preset, style_type must be AUTO or GENERAL (API constraint)
	styleType := opts.StyleType
	if opts.StylePreset != "" && styleType != "" && styleType != "AUTO" && styleType != "GENERAL" {
		log.Printf("Note: style_preset requires AUTO or GENERAL style_type, overriding %s -> GENERAL", styleType)
		styleType = "GENERAL"
	}

	// Log style options if set
	styleInfo := ""
	if styleType != "" {
		styleInfo += fmt.Sprintf(", style_type: %s", styleType)
	}
	if opts.StylePreset != "" {
		styleInfo += fmt.Sprintf(", style_preset: %s", opts.StylePreset)
	}
	log.Printf("Generating image with Ideogram v3 (aspect ratio: %s%s)...", aspectRatioStr, styleInfo)

	// Create the request
	reqBody := IdeogramRequest{
		Prompt:         opts.Description,
		AspectRatio:    aspectRatioStr,
		RenderingSpeed: "TURBO",
		StyleType:      styleType,
		StylePreset:    opts.StylePreset,
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal Ideogram request: %w", err)
	}

	req, err := http.NewRequest("POST", "https://api.ideogram.ai/v1/ideogram-v3/generate", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create Ideogram request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Api-Key", apiKey)

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Ideogram API request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read Ideogram response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Ideogram API error (status %d): %s", resp.StatusCode, string(body))
	}

	var ideogramResp IdeogramResponse
	if err := json.Unmarshal(body, &ideogramResp); err != nil {
		return nil, fmt.Errorf("failed to parse Ideogram response: %w", err)
	}

	if len(ideogramResp.Data) == 0 || ideogramResp.Data[0].URL == "" {
		return nil, fmt.Errorf("no image URL in Ideogram response")
	}

	imageURL := ideogramResp.Data[0].URL
	log.Printf("Ideogram image generated successfully")

	// Download the generated image with attempt number for naming
	attemptNum := opts.AttemptNum
	if attemptNum <= 0 {
		attemptNum = 1
	}
	imagePath, err := downloadGeneratedImage(imageURL, opts.Title, opts.Description, attemptNum, cleanup)
	if err != nil {
		return nil, fmt.Errorf("failed to download Ideogram image: %w", err)
	}

	return &MediaInput{Path: imagePath, IsGenerated: true}, nil
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
		Model: "gpt-5-nano",
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

func downloadGeneratedImage(imageURL, title, description string, attemptNum int, cleanup *fileutil.CleanupManager) (string, error) {
	resp, err := http.Get(imageURL)
	if err != nil {
		return "", fmt.Errorf("failed to download generated image: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("failed to download image: HTTP %d", resp.StatusCode)
	}

	// Create numbered filename format: ideogram_0001.png, ideogram_0002.png, etc.
	filename := fmt.Sprintf("ideogram_%04d.png", attemptNum)
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

// analyzeAudioForPrompt uses Gemini to analyze an audio file and generate an image prompt
func analyzeAudioForPrompt(audioPath, title, notes, caption, subcaption, style string) (string, error) {
	ctx := context.Background()

	log.Printf("Gemini analysis - Title: %q", title)
	log.Printf("Gemini analysis - Notes: %q", notes)
	if caption != "" {
		log.Printf("Gemini analysis - Caption: %q", caption)
	}
	if subcaption != "" {
		log.Printf("Gemini analysis - Subcaption: %q", subcaption)
	}
	if style != "" && style != "auto" {
		log.Printf("Gemini analysis - Style: %q", style)
	}

	client, err := genai.NewClient(ctx)
	if err != nil {
		return "", fmt.Errorf("failed to create Gemini client: %w", err)
	}

	// Convert style string to StylePreference
	stylePref := genai.StyleAuto
	switch style {
	case "photorealistic":
		stylePref = genai.StylePhotorealistic
	case "artistic":
		stylePref = genai.StyleArtistic
	case "abstract":
		stylePref = genai.StyleAbstract
	case "cinematic":
		stylePref = genai.StyleCinematic
	}

	opts := genai.PromptOptions{
		Title:           title,
		Notes:           notes,
		Caption:         caption,
		Subcaption:      subcaption,
		StylePreference: stylePref,
		Quiet:           false,
	}

	result, err := client.GenerateImagePrompt(audioPath, opts)
	if err != nil {
		return "", fmt.Errorf("failed to generate prompt from audio: %w", err)
	}

	return result.Prompt, nil
}

// truncateString truncates a string to the specified length, adding "..." if truncated
func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen-3] + "..."
}

package tts

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"mmmeld/internal/config"
	"mmmeld/internal/fileutil"
)

const (
	MaxChunkSize = 4096
)

type TTSResult struct {
	AudioPath   string
	Title       string
	Description string
}

type ElevenLabsRequest struct {
	Text          string                 `json:"text"`
	ModelID       string                 `json:"model_id"`
	OutputFormat  string                 `json:"output_format"`
	VoiceSettings map[string]interface{} `json:"voice_settings"`
}

type OpenAITTSRequest struct {
	Model string `json:"model"`
	Input string `json:"input"`
	Voice string `json:"voice"`
}

type DeepgramTTSRequest struct {
	Text string `json:"text"`
}

// SplitTextIntoChunks breaks text into chunks suitable for TTS processing
func SplitTextIntoChunks(text string, maxSize int) []string {
	if maxSize <= 0 {
		maxSize = MaxChunkSize
	}

	var chunks []string
	var currentChunk strings.Builder

	lines := strings.Split(text, "\n")

	for _, line := range lines {
		if len(line) > maxSize {
			// Split long lines by sentences
			sentences := regexp.MustCompile(`(?:[.!?]+\s+)`).Split(line, -1)
			for _, sentence := range sentences {
				if len(sentence) > maxSize {
					// Split by words as last resort
					words := strings.Fields(sentence)
					for _, word := range words {
						if currentChunk.Len()+len(word)+1 > maxSize {
							if currentChunk.Len() > 0 {
								chunks = append(chunks, currentChunk.String())
								currentChunk.Reset()
							}
						}
						if currentChunk.Len() > 0 {
							currentChunk.WriteString(" ")
						}
						currentChunk.WriteString(word)
					}
				} else {
					if currentChunk.Len()+len(sentence)+1 > maxSize {
						if currentChunk.Len() > 0 {
							chunks = append(chunks, currentChunk.String())
							currentChunk.Reset()
						}
					}
					if currentChunk.Len() > 0 {
						currentChunk.WriteString(" ")
					}
					currentChunk.WriteString(sentence)
				}
			}
		} else {
			if currentChunk.Len()+len(line)+1 > maxSize {
				if currentChunk.Len() > 0 {
					chunks = append(chunks, currentChunk.String())
					currentChunk.Reset()
				}
			}
			if currentChunk.Len() > 0 {
				currentChunk.WriteString("\n")
			}
			currentChunk.WriteString(line)
		}
	}

	if currentChunk.Len() > 0 {
		chunks = append(chunks, currentChunk.String())
	}

	return chunks
}

// GenerateSpeech generates speech from text using the specified provider
func GenerateSpeech(text, voiceID string, provider config.TTSProvider, cleanup *fileutil.CleanupManager, outputFilename string) (*TTSResult, error) {
	if err := fileutil.EnsureTempFolder(); err != nil {
		return nil, fmt.Errorf("failed to create temp folder: %w", err)
	}

	chunks := SplitTextIntoChunks(text, MaxChunkSize)
	var audioFiles []string
	var title string

	log.Printf("Generating speech using %s with %d chunks", provider, len(chunks))

	for i, chunk := range chunks {
		log.Printf("Processing chunk %d/%d", i+1, len(chunks))

		var audioFile string
		var err error

		switch provider {
		case config.ProviderElevenLabs:
			audioFile, err = generateElevenLabsSpeech(chunk, voiceID, cleanup)
		case config.ProviderOpenAI:
			audioFile, err = generateOpenAISpeech(chunk, voiceID, cleanup)
		case config.ProviderDeepgram:
			audioFile, err = generateDeepgramSpeech(chunk, voiceID, cleanup)
		default:
			return nil, fmt.Errorf("unsupported TTS provider: %s", provider)
		}

		if err != nil {
			return nil, fmt.Errorf("failed to generate speech for chunk %d: %w", i+1, err)
		}

		audioFiles = append(audioFiles, audioFile)

		if title == "" {
			title = generateTitleFromText(chunk)
		}
	}

	var finalAudioPath string
	if len(audioFiles) > 1 {
		var err error
		finalAudioPath, err = concatenateAudioFiles(audioFiles, cleanup)
		if err != nil {
			return nil, fmt.Errorf("failed to concatenate audio files: %w", err)
		}
	} else {
		finalAudioPath = audioFiles[0]
	}

	// Handle custom output filename
	if outputFilename != "" {
		ext := filepath.Ext(finalAudioPath)
		customPath := strings.TrimSuffix(outputFilename, filepath.Ext(outputFilename)) + ext

		if err := os.Rename(finalAudioPath, customPath); err != nil {
			return nil, fmt.Errorf("failed to rename output file: %w", err)
		}
		finalAudioPath = customPath
	}

	return &TTSResult{
		AudioPath:   finalAudioPath,
		Title:       title,
		Description: text,
	}, nil
}

func generateElevenLabsSpeech(text, voiceID string, cleanup *fileutil.CleanupManager) (string, error) {
	apiKey := os.Getenv("ELEVENLABS_API_KEY")
	if apiKey == "" {
		apiKey = os.Getenv("XI_API_KEY")
	}
	if apiKey == "" {
		return "", fmt.Errorf("ElevenLabs API key not found in environment")
	}

	url := fmt.Sprintf("https://api.elevenlabs.io/v1/text-to-speech/%s/stream", voiceID)

	requestBody := ElevenLabsRequest{
		Text:         text,
		ModelID:      config.ElevenLabsModelID,
		OutputFormat: "mp3_44100_192",
		VoiceSettings: map[string]interface{}{
			"stability":         0.5,
			"similarity_boost":  0.8,
			"style":             0.0,
			"use_speaker_boost": true,
		},
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Accept", "audio/mpeg")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("xi-api-key", apiKey)

	client := &http.Client{Timeout: 300 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("ElevenLabs API error %d: %s", resp.StatusCode, string(body))
	}

	filename := fmt.Sprintf("elevenlabs_%d.mp3", time.Now().UnixNano())
	filepath := filepath.Join(config.TempAssetsFolder, filename)

	file, err := os.Create(filepath)
	if err != nil {
		return "", fmt.Errorf("failed to create audio file: %w", err)
	}
	defer file.Close()

	_, err = io.Copy(file, resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to save audio: %w", err)
	}

	cleanup.Add(filepath)
	log.Printf("Generated ElevenLabs audio: %s", filepath)

	return filepath, nil
}

func generateOpenAISpeech(text, voiceID string, cleanup *fileutil.CleanupManager) (string, error) {
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		return "", fmt.Errorf("OpenAI API key not found in environment")
	}

	url := "https://api.openai.com/v1/audio/speech"

	requestBody := OpenAITTSRequest{
		Model: "tts-1",
		Input: text,
		Voice: voiceID,
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 300 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("OpenAI API error %d: %s", resp.StatusCode, string(body))
	}

	filename := fmt.Sprintf("openai_%d.mp3", time.Now().UnixNano())
	filepath := filepath.Join(config.TempAssetsFolder, filename)

	file, err := os.Create(filepath)
	if err != nil {
		return "", fmt.Errorf("failed to create audio file: %w", err)
	}
	defer file.Close()

	_, err = io.Copy(file, resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to save audio: %w", err)
	}

	cleanup.Add(filepath)
	log.Printf("Generated OpenAI audio: %s", filepath)

	return filepath, nil
}

func generateDeepgramSpeech(text, voiceID string, cleanup *fileutil.CleanupManager) (string, error) {
	apiKey := os.Getenv("DEEPGRAM_API_KEY")
	if apiKey == "" {
		return "", fmt.Errorf("Deepgram API key not found in environment")
	}

	url := fmt.Sprintf("https://api.deepgram.com/v1/speak?model=%s&encoding=mp3&sample_rate=44100", voiceID)

	requestBody := DeepgramTTSRequest{
		Text: text,
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Token "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 300 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("Deepgram API error %d: %s", resp.StatusCode, string(body))
	}

	filename := fmt.Sprintf("deepgram_%d.mp3", time.Now().UnixNano())
	filepath := filepath.Join(config.TempAssetsFolder, filename)

	file, err := os.Create(filepath)
	if err != nil {
		return "", fmt.Errorf("failed to create audio file: %w", err)
	}
	defer file.Close()

	_, err = io.Copy(file, resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to save audio: %w", err)
	}

	cleanup.Add(filepath)
	log.Printf("Generated Deepgram audio: %s", filepath)

	return filepath, nil
}

func concatenateAudioFiles(audioFiles []string, cleanup *fileutil.CleanupManager) (string, error) {
	if len(audioFiles) == 0 {
		return "", fmt.Errorf("no audio files to concatenate")
	}

	if len(audioFiles) == 1 {
		return audioFiles[0], nil
	}

	outputPath := filepath.Join(config.TempAssetsFolder, fmt.Sprintf("concatenated_%d.mp3", time.Now().UnixNano()))

	// Create a temporary file list for ffmpeg concat
	listFile := filepath.Join(config.TempAssetsFolder, fmt.Sprintf("concat_list_%d.txt", time.Now().UnixNano()))

	var listContent strings.Builder
	for _, file := range audioFiles {
		absPath, err := filepath.Abs(file)
		if err != nil {
			return "", fmt.Errorf("failed to resolve audio path %s: %w", file, err)
		}
		safePath := strings.ReplaceAll(absPath, "'", "'\\''")
		listContent.WriteString(fmt.Sprintf("file '%s'\n", safePath))
	}

	if err := os.WriteFile(listFile, []byte(listContent.String()), 0644); err != nil {
		return "", fmt.Errorf("failed to create concat list: %w", err)
	}
	defer os.Remove(listFile)

	cmd := exec.Command("ffmpeg", "-f", "concat", "-safe", "0", "-i", listFile, "-c", "copy", outputPath)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("ffmpeg concat failed: %w\nOutput: %s", err, output)
	}

	cleanup.Add(outputPath)
	log.Printf("Concatenated %d audio files to: %s", len(audioFiles), outputPath)

	return outputPath, nil
}

func generateTitleFromText(text string) string {
	// Simple title generation - take first sentence or first 50 characters
	sentences := regexp.MustCompile(`[.!?]+`).Split(text, -1)
	if len(sentences) > 0 && len(sentences[0]) > 0 {
		title := strings.TrimSpace(sentences[0])
		if len(title) > 50 {
			title = title[:47] + "..."
		}
		return title
	}

	if len(text) > 50 {
		return text[:47] + "..."
	}

	return text
}

// IsValidAudioFile checks if a file is valid audio using ffmpeg
func IsValidAudioFile(filepath string) bool {
	cmd := exec.Command("ffmpeg", "-v", "error", "-i", filepath, "-f", "null", "-")
	err := cmd.Run()
	return err == nil
}

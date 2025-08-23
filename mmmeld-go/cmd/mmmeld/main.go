package main

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"mmmeld/internal/audio"
	"mmmeld/internal/config"
	"mmmeld/internal/fileutil"
	"mmmeld/internal/image"
	"mmmeld/internal/video"
)

var stdinReader = bufio.NewReader(os.Stdin)

func main() {
	// Setup logging
	config.SetupLogging()
	
	// Create and load configuration
	cfg := config.New()
	if err := cfg.LoadFromFlags(); err != nil {
		log.Fatalf("Configuration error: %v", err)
	}
	
	// Set API keys in environment
	cfg.SetAPIKeys()
	
	// Create cleanup manager
	cleanup := fileutil.NewCleanupManager()
	defer func() {
		if cfg.Cleanup {
			if err := cleanup.Cleanup(); err != nil {
				log.Printf("Cleanup error: %v", err)
			}
		}
	}()
	
	// Ensure temp folder exists
	if err := fileutil.EnsureTempFolder(); err != nil {
		log.Fatalf("Failed to create temp folder: %v", err)
	}
	
	// Process inputs based on configuration
	if err := processInputs(cfg, cleanup); err != nil {
		log.Fatalf("Processing error: %v", err)
	}
}

func processInputs(cfg *config.Config, cleanup *fileutil.CleanupManager) error {
	var audioSource *audio.AudioSource
	var err error
	
	// Handle audio processing
	if cfg.Audio != "" {
		log.Println("Processing audio input...")
		audioSource, err = audio.GetAudioSource(cfg, cleanup)
		if err != nil {
			return fmt.Errorf("failed to process audio: %w", err)
		}
		log.Printf("Audio processed: %s (title: %s)", audioSource.Path, audioSource.Title)
	} else if !cfg.AutoFill {
		// Interactive mode for audio
		audioSource, err = getAudioInteractive(cfg, cleanup)
		if err != nil {
			return fmt.Errorf("interactive audio input failed: %w", err)
		}
	}
	
	// Handle image/video processing
	var mediaInputs []image.MediaInput
	// Derive title/description from audio if available (used in both non-interactive and interactive flows)
	title := ""
	description := ""
	if audioSource != nil {
		title = audioSource.Title
		description = audioSource.Description
	}
	if cfg.Image != "" || cfg.AutoFill {
		log.Println("Processing image/video inputs...")
		mediaInputs, err = image.GetImageInputs(cfg, title, description, cleanup)
		if err != nil {
			return fmt.Errorf("failed to process images: %w", err)
		}
	} else {
		// Interactive mode for images
		mediaInputs, err = getImagesInteractive(cfg, cleanup, title, description)
		if err != nil {
			return fmt.Errorf("interactive image input failed: %w", err)
		}
	}
	
	// Ensure we have at least some media input
	if len(mediaInputs) == 0 {
		return fmt.Errorf("no image or video inputs provided")
	}
	
	// Handle background music
	var bgMusicPath string
	if cfg.BGMusic != "" {
		log.Println("Processing background music...")
		bgMusicPath, err = audio.GetBackgroundMusic(cfg.BGMusic, cleanup)
		if err != nil {
			return fmt.Errorf("failed to process background music: %w", err)
		}
		log.Printf("Background music processed: %s", bgMusicPath)
	}
	
	// Determine output path
	outputPath := cfg.Output
	if outputPath == "" {
		audioPath := ""
		if audioSource != nil {
			audioPath = audioSource.Path
		}
		outputPath = fileutil.GetDefaultOutputPath(audioPath)
	}
	
	// Ensure output directory exists
	outputDir := filepath.Dir(outputPath)
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("failed to create output directory: %w", err)
	}
	
	// Generate video
	log.Println("Generating video...")
	audioPath := ""
	if audioSource != nil {
		audioPath = audioSource.Path
	}
	
	params := video.VideoGenParams{
		MediaInputs:   mediaInputs,
		AudioPath:     audioPath,
		BGMusicPath:   bgMusicPath,
		OutputPath:    outputPath,
		BGMusicVolume: cfg.BGMusicVolume,
		AudioMargins:  cfg.AudioMargins,
		TempFolder:    config.TempAssetsFolder,
	}
	
	if err := video.GenerateVideo(params); err != nil {
		return fmt.Errorf("failed to generate video: %w", err)
	}
	
	// Validate the output
	expectedDuration, err := video.CalculateTotalDuration(audioPath, mediaInputs, cfg.AudioMargins)
	if err != nil {
		log.Printf("Warning: Could not calculate expected duration for validation: %v", err)
	} else {
		if err := video.ValidateVideo(outputPath, expectedDuration, audioPath != "" || bgMusicPath != ""); err != nil {
			log.Printf("Warning: Video validation failed: %v", err)
		}
	}
	
	fmt.Printf("Video generated successfully: %s\n", outputPath)
	return nil
}

// Interactive mode functions

// readLine reads a full line from stdin after printing the prompt.
func readLine(prompt string) string {
	fmt.Print(prompt)
	line, _ := stdinReader.ReadString('\n')
	return strings.TrimSpace(line)
}

// readMultiline reads multiple lines until the user presses Enter twice consecutively.
func readMultiline(prompt string) string {
	fmt.Println(prompt)
	var lines []string
	emptyCount := 0
	for {
		line, _ := stdinReader.ReadString('\n')
		line = strings.TrimRight(line, "\r\n")
		if line == "" {
			emptyCount++
			if emptyCount >= 2 {
				break
			}
			continue
		}
		emptyCount = 0
		lines = append(lines, line)
	}
	return strings.Join(lines, "\n")
}

func getAudioInteractive(cfg *config.Config, cleanup *fileutil.CleanupManager) (*audio.AudioSource, error) {
	input := readLine("Enter audio source (file path, YouTube URL, or 'generate' for TTS): ")
	if input == "" {
		return nil, nil // No audio
	}
	
	cfg.Audio = input
	
	if input == "generate" {
		text := readMultiline("Enter the text you want to convert to speech (press Enter twice to finish):")
		if strings.TrimSpace(text) == "" {
			fmt.Println("No text provided. Skipping audio generation.")
			cfg.Audio = "" // skip audio per Python behavior
			return nil, nil
		}
		cfg.Text = text
		
		voiceID := readLine(fmt.Sprintf("Enter voice ID (default: %s): ", cfg.VoiceID))
		if voiceID != "" {
			cfg.VoiceID = voiceID
		}
	}
	
	return audio.GetAudioSource(cfg, cleanup)
}

func getImagesInteractive(cfg *config.Config, cleanup *fileutil.CleanupManager, title, description string) ([]image.MediaInput, error) {
	var results []image.MediaInput
	
	fmt.Println("Enter image/video sources (press Enter on empty line to finish):")
	first := true
	for {
		input := readLine("Path/URL ('generate' for AI image): ")
		if first && input == "" {
			fmt.Println("Input was empty, will treat first image as 'generate'.")
			input = "generate"
		} else if !first && input == "" {
			break
		}

		prevImage := cfg.Image
		prevDesc := cfg.ImageDescription

		endAfterThis := false
		if input == "generate" {
			desc := readMultiline("Enter image description (press Enter twice to finish; leave empty to infer from audio and finish):")
			if strings.TrimSpace(desc) == "" {
				// Use inference and end the list after adding this item
				endAfterThis = true
			}
			cfg.Image = "generate"
			cfg.ImageDescription = desc
		} else {
			cfg.Image = input
			cfg.ImageDescription = ""
		}

		items, err := image.GetImageInputs(cfg, title, description, cleanup)
		if err != nil {
			return nil, err
		}
		results = append(results, items...)

		cfg.Image = prevImage
		cfg.ImageDescription = prevDesc
		first = false

		if endAfterThis {
			break
		}
	}
	
	if len(results) == 0 {
		// Python fallback: generate a default image when no inputs are provided interactively
		prevImage := cfg.Image
		prevDesc := cfg.ImageDescription
		cfg.Image = "generate"
		cfg.ImageDescription = "A visually engaging background image"
		items, err := image.GetImageInputs(cfg, title, description, cleanup)
		cfg.Image = prevImage
		cfg.ImageDescription = prevDesc
		if err != nil {
			return nil, err
		}
		results = append(results, items...)
	}
	
	return results, nil
}

package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"

	"mmmeld/internal/audio"
	"mmmeld/internal/config"
	"mmmeld/internal/fileutil"
	"mmmeld/internal/image"
	"mmmeld/internal/video"
)

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
	if cfg.Image != "" || cfg.AutoFill {
		title := ""
		description := ""
		if audioSource != nil {
			title = audioSource.Title
			description = audioSource.Description
		}
		
		log.Println("Processing image/video inputs...")
		mediaInputs, err = image.GetImageInputs(cfg, title, description, cleanup)
		if err != nil {
			return fmt.Errorf("failed to process images: %w", err)
		}
	} else {
		// Interactive mode for images
		mediaInputs, err = getImagesInteractive(cfg, cleanup)
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
func getAudioInteractive(cfg *config.Config, cleanup *fileutil.CleanupManager) (*audio.AudioSource, error) {
	fmt.Print("Enter audio source (file path, YouTube URL, or 'generate' for TTS): ")
	var input string
	fmt.Scanln(&input)
	
	if input == "" {
		return nil, nil // No audio
	}
	
	cfg.Audio = input
	
	if input == "generate" {
		fmt.Print("Enter text for speech generation: ")
		var text string
		fmt.Scanln(&text)
		cfg.Text = text
		
		fmt.Printf("Enter voice ID (default: %s): ", cfg.VoiceID)
		var voiceID string
		fmt.Scanln(&voiceID)
		if voiceID != "" {
			cfg.VoiceID = voiceID
		}
	}
	
	return audio.GetAudioSource(cfg, cleanup)
}

func getImagesInteractive(cfg *config.Config, cleanup *fileutil.CleanupManager) ([]image.MediaInput, error) {
	var inputs []string
	
	fmt.Println("Enter image/video sources (press Enter on empty line to finish):")
	for {
		fmt.Print("Path/URL ('generate' for AI image): ")
		var input string
		fmt.Scanln(&input)
		
		if input == "" {
			break
		}
		
		inputs = append(inputs, input)
		
		if input == "generate" && cfg.ImageDescription == "" {
			fmt.Print("Enter image description (optional): ")
			var desc string
			fmt.Scanln(&desc)
			if desc != "" {
				cfg.ImageDescription = desc
			}
		}
	}
	
	if len(inputs) == 0 {
		return nil, fmt.Errorf("no image inputs provided")
	}
	
	cfg.Image = fmt.Sprintf("%v", inputs[0])
	for i := 1; i < len(inputs); i++ {
		cfg.Image += "," + inputs[i]
	}
	
	return image.GetImageInputs(cfg, "", "", cleanup)
}
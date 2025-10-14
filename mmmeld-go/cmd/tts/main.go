package main

import (
	"flag"
	"fmt"
	"io"
	"log"
	"os"

	"mmmeld/internal/config"
	"mmmeld/internal/fileutil"
	"mmmeld/internal/tts"
)

type TTSConfig struct {
	Text         string
	TextFile     string
	Provider     string
	VoiceID      string
	Output       string
	DefaultFile  string
}

func main() {
	// Setup logging
	config.SetupLogging()
	
	// Parse command line arguments
	cfg, err := parseArgs()
	if err != nil {
		log.Fatalf("Argument parsing error: %v", err)
	}
	
	// Get text input
	text, err := getTextInput(cfg)
	if err != nil {
		log.Fatalf("Text input error: %v", err)
	}
	
	if text == "" {
		log.Fatal("No text provided for speech generation")
	}
	
	// Validate provider
	var provider config.TTSProvider
	switch cfg.Provider {
	case "elevenlabs":
		provider = config.ProviderElevenLabs
	case "openai":
		provider = config.ProviderOpenAI
	case "deepgram":
		provider = config.ProviderDeepgram
	default:
		log.Fatalf("Invalid TTS provider: %s. Must be one of: elevenlabs, openai, deepgram", cfg.Provider)
	}
	
	// Create cleanup manager
	cleanup := fileutil.NewCleanupManager()
	defer func() {
		if err := cleanup.Cleanup(); err != nil {
			log.Printf("Cleanup error: %v", err)
		}
	}()
	
	// Generate speech
	log.Printf("Generating speech using %s provider with voice %s", provider, cfg.VoiceID)
	result, err := tts.GenerateSpeech(text, cfg.VoiceID, provider, cleanup, cfg.Output)
	if err != nil {
		log.Fatalf("Speech generation failed: %v", err)
	}
	
	fmt.Printf("Generated speech saved to: %s\n", result.AudioPath)
	if result.Title != "" {
		fmt.Printf("Title: %s\n", result.Title)
	}
}

func parseArgs() (*TTSConfig, error) {
	cfg := &TTSConfig{}
	
	flag.StringVar(&cfg.Text, "text", "", "Text to convert to speech")
	flag.StringVar(&cfg.Text, "t", "", "Text to convert to speech")
	
	flag.StringVar(&cfg.TextFile, "textfile", "", "File containing text to convert to speech")
	flag.StringVar(&cfg.TextFile, "tf", "", "File containing text to convert to speech")
	
	flag.StringVar(&cfg.Provider, "provider", "", "TTS provider (elevenlabs, openai, deepgram)")
	flag.StringVar(&cfg.Provider, "p", "", "TTS provider (elevenlabs, openai, deepgram)")
	
	flag.StringVar(&cfg.VoiceID, "voiceid", "", "Voice ID for the TTS provider")
	flag.StringVar(&cfg.VoiceID, "v", "", "Voice ID for the TTS provider")
	
	flag.StringVar(&cfg.Output, "output", "", "Output filename or file path")
	flag.StringVar(&cfg.Output, "o", "", "Output filename or file path")
	
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage of %s:\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "Text to Speech Command Line Tool\n\n")
		flag.PrintDefaults()
		fmt.Fprintf(os.Stderr, "\nExamples:\n")
		fmt.Fprintf(os.Stderr, "  %s --text \"Hello world\" --provider elevenlabs --voiceid %s\n", os.Args[0], config.ElevenLabsVoiceID)
		fmt.Fprintf(os.Stderr, "  %s --textfile input.txt --provider openai --voiceid %s --output speech.mp3\n", os.Args[0], config.OpenAIVoiceID)
		fmt.Fprintf(os.Stderr, "  %s --provider deepgram --voiceid %s < input.txt\n", os.Args[0], config.DeepgramVoiceID)
	}
	
	flag.Parse()
	
	// Handle positional argument for default text file
	if flag.NArg() > 0 {
		cfg.DefaultFile = flag.Arg(0)
	}
	
	// Validate required arguments
	if cfg.Provider == "" {
		return nil, fmt.Errorf("provider is required")
	}
	
	if cfg.VoiceID == "" {
		return nil, fmt.Errorf("voice ID is required")
	}
	
	// Must have either text, textfile, or default file
	if cfg.Text == "" && cfg.TextFile == "" && cfg.DefaultFile == "" {
		return nil, fmt.Errorf("must provide either --text, --textfile, or a default text file argument")
	}
	
	// Cannot have multiple text sources
	textSources := 0
	if cfg.Text != "" {
		textSources++
	}
	if cfg.TextFile != "" {
		textSources++
	}
	if cfg.DefaultFile != "" {
		textSources++
	}
	
	if textSources > 1 {
		return nil, fmt.Errorf("provide only one text source")
	}
	
	return cfg, nil
}

func getTextInput(cfg *TTSConfig) (string, error) {
	if cfg.Text != "" {
		return cfg.Text, nil
	}
	
	var filename string
	if cfg.TextFile != "" {
		filename = cfg.TextFile
	} else if cfg.DefaultFile != "" {
		filename = cfg.DefaultFile
	}
	
	if filename != "" {
		// Read from file
		content, err := os.ReadFile(filename)
		if err != nil {
			return "", fmt.Errorf("failed to read text file %s: %w", filename, err)
		}
		return string(content), nil
	}
	
	// Read from stdin
	content, err := io.ReadAll(os.Stdin)
	if err != nil {
		return "", fmt.Errorf("failed to read from stdin: %w", err)
	}
	
	return string(content), nil
}
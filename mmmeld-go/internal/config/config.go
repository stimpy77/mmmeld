package config

import (
	"errors"
	"flag"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
)

const (
	TempAssetsFolder      = "temp_assets"
	MaxFilenameLength     = 100
	ElevenLabsVoiceID     = "WWr4C8ld745zI3BiA8n7"
	OpenAIVoiceID         = "onyx"
	DeepgramVoiceID       = "aura-zeus-en"
	DefaultBGMusicVolume  = 0.2
)

type TTSProvider string

const (
	ProviderElevenLabs TTSProvider = "elevenlabs"
	ProviderOpenAI     TTSProvider = "openai"
	ProviderDeepgram   TTSProvider = "deepgram"
)

type AudioMargins struct {
	Start float64
	End   float64
}

type Config struct {
	// Audio options
	Audio       string      `json:"audio"`
	Text        string      `json:"text"`
	VoiceID     string      `json:"voice_id"`
	TTSProvider TTSProvider `json:"tts_provider"`
	
	// Image/Video options
	Image            string `json:"image"`
	ImageDescription string `json:"image_description"`
	
	// Background music
	BGMusic       string  `json:"bg_music"`
	BGMusicVolume float64 `json:"bg_music_volume"`
	
	// Output options
	Output       string       `json:"output"`
	AudioMargins AudioMargins `json:"audio_margins"`
	
	// Behavior flags
	Cleanup     bool `json:"cleanup"`
	AutoFill    bool `json:"auto_fill"`
	ShowPrompts bool `json:"show_prompts"`
	
	// API Keys
	OpenAIKey     string `json:"-"` // Don't serialize keys
	ElevenLabsKey string `json:"-"`
	DeepgramKey   string `json:"-"`
}

func New() *Config {
	return &Config{
		VoiceID:       ElevenLabsVoiceID,
		TTSProvider:   ProviderElevenLabs,
		BGMusicVolume: DefaultBGMusicVolume,
		AudioMargins:  AudioMargins{Start: 0.5, End: 2.0},
		Cleanup:       true,
	}
}

func (c *Config) LoadFromFlags() error {
	// Use a custom FlagSet for better control
	fs := flag.NewFlagSet("mmmeld", flag.ContinueOnError)
	
	var (
		ttsProvider   = fs.String("tts-provider", string(ProviderElevenLabs), "Text-to-speech provider (elevenlabs, openai, deepgram)")
		audioMargin   = fs.String("audiomargin", "0.5,2.0", "Start and end audio margins in seconds, comma-separated")
		noCleanup     = fs.Bool("nocleanup", false, "Do not clean up temporary files")
	)
	
	fs.StringVar(&c.Audio, "audio", "", "Path to audio file, YouTube URL, or 'generate' for text-to-speech")
	fs.StringVar(&c.Audio, "a", "", "Path to audio file, YouTube URL, or 'generate' for text-to-speech")
	
	fs.StringVar(&c.Text, "text", "", "Text for speech generation")
	fs.StringVar(&c.Text, "t", "", "Text for speech generation")
	
	fs.StringVar(&c.VoiceID, "voice-id", ElevenLabsVoiceID, "Voice ID for TTS")
	fs.StringVar(&c.VoiceID, "vid", ElevenLabsVoiceID, "Voice ID for TTS")
	
	fs.StringVar(&c.Image, "image", "", "Path to image/video file(s), URL(s), or 'generate'")
	fs.StringVar(&c.Image, "i", "", "Path to image/video file(s), URL(s), or 'generate'")
	
	fs.StringVar(&c.ImageDescription, "image-description", "", "Description for image generation")
	fs.StringVar(&c.ImageDescription, "img-desc", "", "Description for image generation")
	
	fs.StringVar(&c.BGMusic, "bg-music", "", "Path to background music file or YouTube URL")
	fs.StringVar(&c.BGMusic, "bm", "", "Path to background music file or YouTube URL")
	
	fs.Float64Var(&c.BGMusicVolume, "bg-music-volume", DefaultBGMusicVolume, "Volume of background music (0.0 to 1.0)")
	fs.Float64Var(&c.BGMusicVolume, "bmv", DefaultBGMusicVolume, "Volume of background music (0.0 to 1.0)")
	
	fs.BoolVar(&c.AutoFill, "autofill", false, "Use defaults for all unspecified options")
	fs.BoolVar(&c.AutoFill, "af", false, "Use defaults for all unspecified options")
	
	fs.BoolVar(&c.ShowPrompts, "showprompts", false, "Show all prompts")
	fs.BoolVar(&c.ShowPrompts, "sp", false, "Show all prompts")
	
	fs.StringVar(&c.Output, "output", "", "Path for the output video file")
	fs.StringVar(&c.Output, "o", "", "Path for the output video file")
	
	fs.StringVar(&c.OpenAIKey, "openai-key", "", "OpenAI API key")
	fs.StringVar(&c.ElevenLabsKey, "elevenlabs-key", "", "ElevenLabs API key")
	fs.StringVar(&c.DeepgramKey, "deepgram-key", "", "DeepGram API key")
	
	if err := fs.Parse(os.Args[1:]); err != nil {
		return fmt.Errorf("failed to parse flags: %w", err)
	}
	
	// Post-process values
	c.TTSProvider = TTSProvider(*ttsProvider)
	c.Cleanup = !*noCleanup
	
	if err := c.parseAudioMargin(*audioMargin); err != nil {
		return err
	}
	
	c.loadAPIKeysFromEnv()
	
	return c.validate()
}

func (c *Config) parseAudioMargin(margin string) error {
	parts := strings.Split(margin, ",")
	if len(parts) != 2 {
		return errors.New("audiomargin must be in format 'start,end'")
	}
	
	start, err := strconv.ParseFloat(strings.TrimSpace(parts[0]), 64)
	if err != nil {
		return fmt.Errorf("invalid start margin: %w", err)
	}
	
	end, err := strconv.ParseFloat(strings.TrimSpace(parts[1]), 64)
	if err != nil {
		return fmt.Errorf("invalid end margin: %w", err)
	}
	
	c.AudioMargins = AudioMargins{Start: start, End: end}
	return nil
}

func (c *Config) loadAPIKeysFromEnv() {
	if c.OpenAIKey == "" {
		c.OpenAIKey = os.Getenv("OPENAI_API_KEY")
	}
	if c.ElevenLabsKey == "" {
		c.ElevenLabsKey = os.Getenv("ELEVENLABS_API_KEY")
	}
	if c.DeepgramKey == "" {
		c.DeepgramKey = os.Getenv("DEEPGRAM_API_KEY")
	}
}

func (c *Config) validate() error {
	// Validate TTS provider
	switch c.TTSProvider {
	case ProviderElevenLabs, ProviderOpenAI, ProviderDeepgram:
		// Valid
	default:
		return fmt.Errorf("invalid TTS provider: %s", c.TTSProvider)
	}
	
	// Validate audio margins
	if c.AudioMargins.Start < 0 || c.AudioMargins.End < 0 {
		return errors.New("audio margins must be positive")
	}
	
	// Validate background music volume
	if c.BGMusicVolume < 0 || c.BGMusicVolume > 1 {
		return errors.New("background music volume must be between 0.0 and 1.0")
	}
	
	return nil
}

func (c *Config) SetAPIKeys() {
	if c.OpenAIKey != "" {
		os.Setenv("OPENAI_API_KEY", c.OpenAIKey)
	}
	if c.ElevenLabsKey != "" {
		os.Setenv("ELEVENLABS_API_KEY", c.ElevenLabsKey)
	}
	if c.DeepgramKey != "" {
		os.Setenv("DEEPGRAM_API_KEY", c.DeepgramKey)
	}
}

func SetupLogging() {
	log.SetFlags(log.LstdFlags | log.Lshortfile)
}

func ValidateInput(inputType, value string) bool {
	switch inputType {
	case "audio":
		return strings.ToLower(value) == "generate" ||
			fileExists(value) ||
			strings.Contains(value, "youtube.com") ||
			strings.Contains(value, "youtu.be")
	case "image":
		return strings.ToLower(value) == "generate" ||
			fileExists(value) ||
			strings.HasPrefix(value, "http")
	}
	return false
}

func fileExists(filename string) bool {
	_, err := os.Stat(filename)
	return err == nil
}
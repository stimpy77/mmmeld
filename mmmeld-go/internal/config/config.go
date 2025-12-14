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
	TempAssetsFolder     = "temp_assets"
	MaxFilenameLength    = 100
	ElevenLabsVoiceID    = "WWr4C8ld745zI3BiA8n7"
	OpenAIVoiceID        = "onyx"
	DeepgramVoiceID      = "aura-zeus-en"
	DefaultBGMusicVolume = 0.2
)

type TTSProvider string

const (
	ProviderElevenLabs TTSProvider = "elevenlabs"
	ProviderOpenAI     TTSProvider = "openai"
	ProviderDeepgram   TTSProvider = "deepgram"
)

type ImageProvider string

const (
	ImageProviderDALLE    ImageProvider = "dalle"
	ImageProviderIdeogram ImageProvider = "ideogram"
)

type AspectRatio string

const (
	AspectRatio16x9 AspectRatio = "16:9" // YouTube landscape (default)
	AspectRatio9x16 AspectRatio = "9:16" // YouTube Shorts / vertical
	AspectRatio1x1  AspectRatio = "1:1"  // Square
	AspectRatio4x3  AspectRatio = "4:3"  // Classic TV
	AspectRatio3x4  AspectRatio = "3:4"  // Portrait
	AspectRatio3x2  AspectRatio = "3:2"  // Photo
	AspectRatio2x3  AspectRatio = "2:3"  // Portrait photo
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
	Image            string        `json:"image"`
	ImageDescription string        `json:"image_description"`
	ImageProvider    ImageProvider `json:"image_provider"`

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
	GeminiKey     string `json:"-"`
	IdeogramKey   string `json:"-"`

	// Audio analysis options
	AnalyzeAudio    bool   `json:"analyze_audio"`    // Use Gemini to analyze audio for image prompt
	AudioNotes      string `json:"audio_notes"`      // Notes for audio analysis (genre, mood, themes)
	ImageCaption    string `json:"image_caption"`    // Caption/title text to render on the image
	ImageSubcaption string `json:"image_subcaption"` // Subcaption/subtitle text to render on the image

	// Image generation options
	AspectRatio AspectRatio `json:"aspect_ratio"` // Aspect ratio for generated images
}

func New() *Config {
	return &Config{
		VoiceID:       ElevenLabsVoiceID,
		TTSProvider:   ProviderElevenLabs,
		ImageProvider: ImageProviderIdeogram, // Default to Ideogram
		BGMusicVolume: DefaultBGMusicVolume,
		AudioMargins:  AudioMargins{Start: 0.5, End: 2.0},
		Cleanup:       true,
		AspectRatio:   AspectRatio16x9, // Default to YouTube landscape
	}
}

func (c *Config) LoadFromFlags() error {
	// Use a custom FlagSet for better control
	fs := flag.NewFlagSet("mmmeld", flag.ContinueOnError)

	var (
		ttsProvider = fs.String("tts-provider", string(ProviderElevenLabs), "Text-to-speech provider (elevenlabs, openai, deepgram)")
		audioMargin = fs.String("audiomargin", "0.5,2.0", "Start and end audio margins in seconds, comma-separated")
		noCleanup   = fs.Bool("nocleanup", false, "Do not clean up temporary files")
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
	fs.StringVar(&c.GeminiKey, "gemini-key", "", "Google Gemini API key")
	fs.StringVar(&c.IdeogramKey, "ideogram-key", "", "Ideogram API key")

	var imageProvider = fs.String("image-provider", "ideogram", "Image generation provider (ideogram, dalle)")
	fs.String("ip", "ideogram", "Image generation provider (shorthand)")

	fs.BoolVar(&c.AnalyzeAudio, "analyze-audio", false, "Use Gemini to analyze audio and generate image prompt")
	fs.BoolVar(&c.AnalyzeAudio, "aa", false, "Use Gemini to analyze audio and generate image prompt")

	fs.StringVar(&c.AudioNotes, "audio-image-notes", "", "Notes for audio-to-image generation (style, mood, exclusions)")
	fs.StringVar(&c.AudioNotes, "ain", "", "Notes for audio-to-image generation (style, mood, exclusions)")

	fs.StringVar(&c.ImageCaption, "image-caption", "", "Caption/title text to render on the generated image")
	fs.StringVar(&c.ImageCaption, "ic", "", "Caption/title text to render on the generated image")

	fs.StringVar(&c.ImageSubcaption, "image-subcaption", "", "Subcaption/subtitle text to render on the generated image")
	fs.StringVar(&c.ImageSubcaption, "isc", "", "Subcaption/subtitle text to render on the generated image")

	var aspectRatioStr string
	fs.StringVar(&aspectRatioStr, "aspect-ratio", "16:9", "Aspect ratio for generated images (16:9, 9:16, 1:1, 4:3, 3:4, 3:2, 2:3)")
	fs.StringVar(&aspectRatioStr, "ar", "16:9", "Aspect ratio for generated images (shorthand)")

	if err := fs.Parse(os.Args[1:]); err != nil {
		return fmt.Errorf("failed to parse flags: %w", err)
	}

	// Post-process values
	c.TTSProvider = TTSProvider(*ttsProvider)
	c.ImageProvider = ImageProvider(*imageProvider)
	c.Cleanup = !*noCleanup
	c.AspectRatio = parseAspectRatio(aspectRatioStr)

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

func parseAspectRatio(s string) AspectRatio {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case "16:9", "16x9":
		return AspectRatio16x9
	case "9:16", "9x16":
		return AspectRatio9x16
	case "1:1", "1x1", "square":
		return AspectRatio1x1
	case "4:3", "4x3":
		return AspectRatio4x3
	case "3:4", "3x4":
		return AspectRatio3x4
	case "3:2", "3x2":
		return AspectRatio3x2
	case "2:3", "2x3":
		return AspectRatio2x3
	default:
		return AspectRatio16x9 // Default to YouTube landscape
	}
}

// IdeogramAspectRatio converts AspectRatio to Ideogram API format
func (ar AspectRatio) IdeogramAspectRatio() string {
	switch ar {
	case AspectRatio16x9:
		return "16x9"
	case AspectRatio9x16:
		return "9x16"
	case AspectRatio1x1:
		return "1x1"
	case AspectRatio4x3:
		return "4x3"
	case AspectRatio3x4:
		return "3x4"
	case AspectRatio3x2:
		return "3x2"
	case AspectRatio2x3:
		return "2x3"
	default:
		return "16x9"
	}
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
	if c.GeminiKey == "" {
		c.GeminiKey = os.Getenv("GEMINI_API_KEY")
	}
	if c.IdeogramKey == "" {
		c.IdeogramKey = os.Getenv("IDEOGRAM_API_KEY")
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

	// Validate Image provider
	switch c.ImageProvider {
	case ImageProviderDALLE, ImageProviderIdeogram:
		// Valid
	default:
		return fmt.Errorf("invalid image provider: %s (must be 'dalle' or 'ideogram')", c.ImageProvider)
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
	if c.GeminiKey != "" {
		os.Setenv("GEMINI_API_KEY", c.GeminiKey)
	}
	if c.IdeogramKey != "" {
		os.Setenv("IDEOGRAM_API_KEY", c.IdeogramKey)
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

package config

import (
	"os"
	"testing"
)

func TestNew(t *testing.T) {
	cfg := New()
	
	if cfg.VoiceID != ElevenLabsVoiceID {
		t.Errorf("Expected default voice ID %s, got %s", ElevenLabsVoiceID, cfg.VoiceID)
	}
	
	if cfg.TTSProvider != ProviderElevenLabs {
		t.Errorf("Expected default TTS provider %s, got %s", ProviderElevenLabs, cfg.TTSProvider)
	}
	
	if cfg.BGMusicVolume != DefaultBGMusicVolume {
		t.Errorf("Expected default BG music volume %f, got %f", DefaultBGMusicVolume, cfg.BGMusicVolume)
	}
	
	if cfg.AudioMargins.Start != 0.5 || cfg.AudioMargins.End != 2.0 {
		t.Errorf("Expected default margins 0.5,2.0, got %f,%f", cfg.AudioMargins.Start, cfg.AudioMargins.End)
	}
	
	if !cfg.Cleanup {
		t.Error("Expected default cleanup to be true")
	}
}

func TestParseAudioMargin(t *testing.T) {
	cfg := New()
	
	tests := []struct {
		input       string
		expectStart float64
		expectEnd   float64
		expectError bool
	}{
		{"0.5,2.0", 0.5, 2.0, false},
		{"1.0,3.5", 1.0, 3.5, false},
		{"0,0", 0.0, 0.0, false},
		{"invalid", 0, 0, true},
		{"1.0", 0, 0, true},
		{"1.0,2.0,3.0", 0, 0, true},
		{"abc,def", 0, 0, true},
	}
	
	for _, test := range tests {
		err := cfg.parseAudioMargin(test.input)
		
		if test.expectError {
			if err == nil {
				t.Errorf("Expected error for input %s, but got none", test.input)
			}
		} else {
			if err != nil {
				t.Errorf("Unexpected error for input %s: %v", test.input, err)
			}
			if cfg.AudioMargins.Start != test.expectStart {
				t.Errorf("Expected start %f for input %s, got %f", test.expectStart, test.input, cfg.AudioMargins.Start)
			}
			if cfg.AudioMargins.End != test.expectEnd {
				t.Errorf("Expected end %f for input %s, got %f", test.expectEnd, test.input, cfg.AudioMargins.End)
			}
		}
	}
}

func TestValidate(t *testing.T) {
	tests := []struct {
		name        string
		setup       func(*Config)
		expectError bool
	}{
		{
			name:        "valid config",
			setup:       func(c *Config) {},
			expectError: false,
		},
		{
			name: "invalid TTS provider",
			setup: func(c *Config) {
				c.TTSProvider = "invalid"
			},
			expectError: true,
		},
		{
			name: "negative start margin",
			setup: func(c *Config) {
				c.AudioMargins.Start = -1.0
			},
			expectError: true,
		},
		{
			name: "negative end margin",
			setup: func(c *Config) {
				c.AudioMargins.End = -1.0
			},
			expectError: true,
		},
		{
			name: "invalid BG music volume - too low",
			setup: func(c *Config) {
				c.BGMusicVolume = -0.1
			},
			expectError: true,
		},
		{
			name: "invalid BG music volume - too high",
			setup: func(c *Config) {
				c.BGMusicVolume = 1.1
			},
			expectError: true,
		},
	}
	
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			cfg := New()
			test.setup(cfg)
			
			err := cfg.validate()
			if test.expectError && err == nil {
				t.Error("Expected validation error but got none")
			}
			if !test.expectError && err != nil {
				t.Errorf("Unexpected validation error: %v", err)
			}
		})
	}
}

func TestLoadAPIKeysFromEnv(t *testing.T) {
	// Save original env vars
	originalOpenAI := os.Getenv("OPENAI_API_KEY")
	originalElevenLabs := os.Getenv("ELEVENLABS_API_KEY")
	originalDeepgram := os.Getenv("DEEPGRAM_API_KEY")
	
	// Clean up after test
	defer func() {
		os.Setenv("OPENAI_API_KEY", originalOpenAI)
		os.Setenv("ELEVENLABS_API_KEY", originalElevenLabs)
		os.Setenv("DEEPGRAM_API_KEY", originalDeepgram)
	}()
	
	// Set test env vars
	os.Setenv("OPENAI_API_KEY", "test-openai-key")
	os.Setenv("ELEVENLABS_API_KEY", "test-elevenlabs-key")
	os.Setenv("DEEPGRAM_API_KEY", "test-deepgram-key")
	
	cfg := New()
	cfg.loadAPIKeysFromEnv()
	
	if cfg.OpenAIKey != "test-openai-key" {
		t.Errorf("Expected OpenAI key 'test-openai-key', got '%s'", cfg.OpenAIKey)
	}
	if cfg.ElevenLabsKey != "test-elevenlabs-key" {
		t.Errorf("Expected ElevenLabs key 'test-elevenlabs-key', got '%s'", cfg.ElevenLabsKey)
	}
	if cfg.DeepgramKey != "test-deepgram-key" {
		t.Errorf("Expected Deepgram key 'test-deepgram-key', got '%s'", cfg.DeepgramKey)
	}
}

func TestValidateInput(t *testing.T) {
	tests := []struct {
		inputType string
		value     string
		expected  bool
	}{
		{"audio", "generate", true},
		{"audio", "https://youtube.com/watch?v=test", true},
		{"audio", "https://youtu.be/test", true},
		{"audio", "invalid-file.mp3", false}, // File doesn't exist
		{"image", "generate", true},
		{"image", "http://example.com/image.jpg", true},
		{"image", "invalid-file.jpg", false}, // File doesn't exist
		{"unknown", "anything", false},
	}
	
	for _, test := range tests {
		result := ValidateInput(test.inputType, test.value)
		if result != test.expected {
			t.Errorf("ValidateInput(%s, %s) = %v, expected %v", 
				test.inputType, test.value, result, test.expected)
		}
	}
}
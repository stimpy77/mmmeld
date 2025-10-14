package video

import (
	"testing"

	"mmmeld/internal/config"
	"mmmeld/internal/image"
)

func TestCalculateTotalDuration(t *testing.T) {
	tests := []struct {
		name         string
		audioPath    string
		mediaInputs  []image.MediaInput
		margins      config.AudioMargins
		expectError  bool
		expectedMin  float64 // Minimum expected duration
	}{
		{
			name:      "no audio, no inputs",
			audioPath: "",
			mediaInputs: []image.MediaInput{},
			margins:   config.AudioMargins{Start: 0.5, End: 2.0},
			expectedMin: 5.0, // Minimum duration
		},
		{
			name:      "no audio, single image",
			audioPath: "",
			mediaInputs: []image.MediaInput{
				{Path: "test.jpg", IsVideo: false},
			},
			margins:     config.AudioMargins{Start: 0.5, End: 2.0},
			expectedMin: 5.0, // Single image = 5 seconds
		},
		{
			name:      "audio with margins",
			audioPath: "test_audio.mp3", // This would need to exist for real test
			mediaInputs: []image.MediaInput{
				{Path: "test.jpg", IsVideo: false},
			},
			margins:     config.AudioMargins{Start: 0.5, End: 2.0},
			expectError: true, // File doesn't exist
		},
	}
	
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			duration, err := CalculateTotalDuration(test.audioPath, test.mediaInputs, test.margins)
			
			if test.expectError {
				if err == nil {
					t.Error("Expected error but got none")
				}
				return
			}
			
			if err != nil {
				t.Errorf("Unexpected error: %v", err)
				return
			}
			
			if duration < test.expectedMin {
				t.Errorf("Expected duration >= %f, got %f", test.expectedMin, duration)
			}
		})
	}
}

func TestCalculateMaxDimensions(t *testing.T) {
	tests := []struct {
		name        string
		mediaInputs []image.MediaInput
		expectError bool
	}{
		{
			name: "empty inputs",
			mediaInputs: []image.MediaInput{},
			expectError: false, // Should return default dimensions
		},
		{
			name: "non-existent files",
			mediaInputs: []image.MediaInput{
				{Path: "nonexistent.jpg", IsVideo: false},
			},
			expectError: false, // Should handle gracefully
		},
	}
	
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			dimensions, err := CalculateMaxDimensions(test.mediaInputs)
			
			if test.expectError && err == nil {
				t.Error("Expected error but got none")
				return
			}
			
			if !test.expectError && err != nil {
				t.Errorf("Unexpected error: %v", err)
				return
			}
			
			// Should return some reasonable dimensions
			if dimensions.Width <= 0 || dimensions.Height <= 0 {
				t.Errorf("Invalid dimensions: %dx%d", dimensions.Width, dimensions.Height)
			}
		})
	}
}

func TestHelperFunctions(t *testing.T) {
	// Test min function
	if min(5.0, 3.0) != 3.0 {
		t.Error("min(5.0, 3.0) should return 3.0")
	}
	if min(2.0, 7.0) != 2.0 {
		t.Error("min(2.0, 7.0) should return 2.0")
	}
	
	// Test abs function
	if abs(-5.0) != 5.0 {
		t.Error("abs(-5.0) should return 5.0")
	}
	if abs(3.0) != 3.0 {
		t.Error("abs(3.0) should return 3.0")
	}
	if abs(0.0) != 0.0 {
		t.Error("abs(0.0) should return 0.0")
	}
}

func TestVideoGenParams(t *testing.T) {
	// Test that VideoGenParams struct can be created and has expected fields
	params := VideoGenParams{
		MediaInputs:   []image.MediaInput{},
		AudioPath:     "test.mp3",
		BGMusicPath:   "bg.mp3",
		OutputPath:    "output.mp4",
		BGMusicVolume: 0.5,
		AudioMargins:  config.AudioMargins{Start: 1.0, End: 2.0},
		TempFolder:    "/tmp",
	}
	
	if params.AudioPath != "test.mp3" {
		t.Error("AudioPath not set correctly")
	}
	if params.BGMusicVolume != 0.5 {
		t.Error("BGMusicVolume not set correctly")
	}
	if params.AudioMargins.Start != 1.0 {
		t.Error("AudioMargins.Start not set correctly")
	}
}

func TestDimensions(t *testing.T) {
	// Test Dimensions struct
	dims := Dimensions{Width: 1920, Height: 1080}
	
	if dims.Width != 1920 {
		t.Error("Width not set correctly")
	}
	if dims.Height != 1080 {
		t.Error("Height not set correctly")
	}
}
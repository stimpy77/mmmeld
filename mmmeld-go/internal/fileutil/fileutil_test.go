package fileutil

import (
	"os"
	"path/filepath"
	"testing"
)

func TestSanitizeFilename(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"normal_file.txt", "normal_file.txt"},
		{"file with spaces.txt", "file with spaces.txt"},
		{"file<>:\"?*/\\|.txt", "file_________.txt"},
		{"", "unnamed"},
		{"   ", "unnamed"},
		{"...", "unnamed"},
		{string(make([]rune, 150)), ""}, // Test length limit - will be checked separately
		{"file\x00with\x01control.txt", "filewithcontrol.txt"},
	}
	
	for _, test := range tests {
		result := SanitizeFilename(test.input)
		if test.expected == "" {
			// For the length test case - just check that result is not empty and within limit
			if len(result) == 0 || len(result) > 100 {
				t.Errorf("SanitizeFilename length test failed: expected non-empty result with max length 100, got length %d", len(result))
			}
		} else if result != test.expected {
			t.Errorf("SanitizeFilename(%q) = %q, expected %q", test.input, result, test.expected)
		}
	}
}

func TestGetDefaultOutputPath(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"", "mmmeld_output.mp4"},
		{"generate", "mmmeld_output.mp4"},
		{"audio.mp3", "audio_mmmeld.mp4"},
		{"/path/to/audio.wav", "audio_mmmeld.mp4"},
		{"complex file name.m4a", "complex file name_mmmeld.mp4"},
	}
	
	for _, test := range tests {
		result := GetDefaultOutputPath(test.input)
		if result != test.expected {
			t.Errorf("GetDefaultOutputPath(%q) = %q, expected %q", test.input, result, test.expected)
		}
	}
}

func TestIsYouTubeURL(t *testing.T) {
	tests := []struct {
		url      string
		expected bool
	}{
		{"https://www.youtube.com/watch?v=dQw4w9WgXcQ", true},
		{"http://youtube.com/watch?v=test", true},
		{"https://youtu.be/dQw4w9WgXcQ", true},
		{"youtube.com/watch?v=test", true},
		{"www.youtube.com/watch?v=test", true},
		{"https://youtube-nocookie.com/watch?v=test", true},
		{"https://example.com/video.mp4", false},
		{"not-a-url", false},
		{"", false},
	}
	
	for _, test := range tests {
		result := IsYouTubeURL(test.url)
		if result != test.expected {
			t.Errorf("IsYouTubeURL(%q) = %v, expected %v", test.url, result, test.expected)
		}
	}
}

func TestCleanupManager(t *testing.T) {
	// Create temp directory for testing
	tempDir, err := os.MkdirTemp("", "fileutil_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)
	
	// Create test files
	testFile1 := filepath.Join(tempDir, "test1.txt")
	testFile2 := filepath.Join(tempDir, "test2.txt")
	
	if err := os.WriteFile(testFile1, []byte("test"), 0644); err != nil {
		t.Fatalf("Failed to create test file 1: %v", err)
	}
	if err := os.WriteFile(testFile2, []byte("test"), 0644); err != nil {
		t.Fatalf("Failed to create test file 2: %v", err)
	}
	
	// Test cleanup manager
	cm := NewCleanupManager()
	cm.Add(testFile1)
	cm.Add(testFile2)
	
	// Verify files exist
	if !FileExists(testFile1) {
		t.Error("Test file 1 should exist before cleanup")
	}
	if !FileExists(testFile2) {
		t.Error("Test file 2 should exist before cleanup")
	}
	
	// Cleanup
	if err := cm.Cleanup(); err != nil {
		t.Errorf("Cleanup failed: %v", err)
	}
	
	// Verify files are gone
	if FileExists(testFile1) {
		t.Error("Test file 1 should not exist after cleanup")
	}
	if FileExists(testFile2) {
		t.Error("Test file 2 should not exist after cleanup")
	}
}

func TestFileExists(t *testing.T) {
	// Create a temporary file
	tempDir, err := os.MkdirTemp("", "fileutil_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)
	
	existingFile := filepath.Join(tempDir, "existing.txt")
	nonExistentFile := filepath.Join(tempDir, "nonexistent.txt")
	
	if err := os.WriteFile(existingFile, []byte("test"), 0644); err != nil {
		t.Fatalf("Failed to create test file: %v", err)
	}
	
	if !FileExists(existingFile) {
		t.Error("FileExists should return true for existing file")
	}
	
	if FileExists(nonExistentFile) {
		t.Error("FileExists should return false for non-existent file")
	}
}

func TestEnsureTempFolder(t *testing.T) {
	// Remove temp folder if it exists
	os.RemoveAll("temp_assets")
	
	// Ensure it gets created
	if err := EnsureTempFolder(); err != nil {
		t.Errorf("EnsureTempFolder failed: %v", err)
	}
	
	// Verify it exists
	if !FileExists("temp_assets") {
		t.Error("Temp folder should exist after EnsureTempFolder")
	}
	
	// Should not fail if called again
	if err := EnsureTempFolder(); err != nil {
		t.Errorf("EnsureTempFolder should not fail on existing folder: %v", err)
	}
}
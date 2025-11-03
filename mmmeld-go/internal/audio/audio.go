package audio

import (
	"fmt"
	"log"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	"mmmeld/internal/config"
	"mmmeld/internal/ffmpeg"
	"mmmeld/internal/fileutil"
	"mmmeld/internal/tts"
)

type AudioSource struct {
	Path        string
	Title       string
	Description string
}

// GetAudioSource processes audio input based on configuration
func GetAudioSource(cfg *config.Config, cleanup *fileutil.CleanupManager) (*AudioSource, error) {
	switch {
	case cfg.Audio == "generate":
		if cfg.Text == "" {
			return nil, fmt.Errorf("text is required for speech generation")
		}
		
		log.Printf("Generating speech using %s provider", cfg.TTSProvider)
		result, err := tts.GenerateSpeech(cfg.Text, cfg.VoiceID, cfg.TTSProvider, cleanup, "")
		if err != nil {
			return nil, fmt.Errorf("failed to generate speech: %w", err)
		}
		
		return &AudioSource{
			Path:        result.AudioPath,
			Title:       result.Title,
			Description: result.Description,
		}, nil
		
	case fileutil.FileExists(cfg.Audio):
		title := strings.TrimSuffix(filepath.Base(cfg.Audio), filepath.Ext(cfg.Audio))
		return &AudioSource{
			Path:        cfg.Audio,
			Title:       title,
			Description: "",
		}, nil
		
	case fileutil.IsYouTubeURL(cfg.Audio):
		log.Println("Downloading audio from YouTube...")
		audioPath, err := fileutil.DownloadYouTubeAudio(cfg.Audio, cleanup)
		if err != nil {
			return nil, fmt.Errorf("failed to download YouTube audio: %w", err)
		}
		
		// Extract title from filename
		title := strings.TrimSuffix(filepath.Base(audioPath), filepath.Ext(audioPath))
		return &AudioSource{
			Path:        audioPath,
			Title:       fileutil.SanitizeFilename(title),
			Description: "",
		}, nil
		
	default:
		return nil, fmt.Errorf("invalid audio input: %s", cfg.Audio)
	}
}

// GetBackgroundMusic processes background music input
func GetBackgroundMusic(bgMusicPath string, cleanup *fileutil.CleanupManager) (string, error) {
	if bgMusicPath == "" {
		return "", nil
	}
	
	switch {
	case fileutil.FileExists(bgMusicPath):
		return bgMusicPath, nil
		
	case fileutil.IsYouTubeURL(bgMusicPath):
		log.Println("Downloading background music from YouTube...")
		return fileutil.DownloadYouTubeAudio(bgMusicPath, cleanup)
		
	default:
		return "", fmt.Errorf("invalid background music input: %s", bgMusicPath)
	}
}

// GetAudioDuration returns the duration of an audio file in seconds using ffmpeg
func GetAudioDuration(filepath string) (float64, error) {
	cmd := exec.Command("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", filepath)
	output, err := cmd.Output()
	if err != nil {
		return 0, fmt.Errorf("failed to get audio duration: %w", err)
	}
	
	durationStr := strings.TrimSpace(string(output))
	duration, err := strconv.ParseFloat(durationStr, 64)
	if err != nil {
		return 0, fmt.Errorf("failed to parse duration: %w", err)
	}
	
	log.Printf("Audio duration for %s: %.3f seconds", filepath, duration)
	return duration, nil
}

// ValidateAudioFile checks if a file is a valid audio file using ffmpeg
func ValidateAudioFile(filepath string) error {
	cmd := []string{"ffmpeg", "-v", "error", "-i", filepath, "-f", "null", "-"}
	if err := ffmpeg.RunCommandQuiet(cmd); err != nil {
		return fmt.Errorf("invalid audio file: %s", filepath)
	}
	return nil
}

// ConvertToFormat converts audio to a specific format using ffmpeg
func ConvertToFormat(inputPath, outputPath, format string, cleanup *fileutil.CleanupManager) error {
	var codec string
	switch format {
	case "mp3":
		codec = "libmp3lame"
	case "wav":
		codec = "pcm_s16le"
	case "aac":
		codec = "aac"
	default:
		return fmt.Errorf("unsupported audio format: %s", format)
	}
	
	cmd := []string{"ffmpeg", "-i", inputPath, "-c:a", codec, "-y", outputPath}
	if err := ffmpeg.RunCommand(cmd); err != nil {
		return fmt.Errorf("audio conversion failed: %w", err)
	}
	
	cleanup.Add(outputPath)
	log.Printf("Converted audio to %s: %s", format, outputPath)
	
	return nil
}

// ApplyAudioEffects applies effects like volume adjustment and fading
func ApplyAudioEffects(inputPath, outputPath string, volume float64, fadeInDuration, fadeOutDuration float64, cleanup *fileutil.CleanupManager) error {
	var filters []string
	
	// Volume adjustment
	if volume != 1.0 {
		filters = append(filters, fmt.Sprintf("volume=%.2f", volume))
	}
	
	// Fade in
	if fadeInDuration > 0 {
		filters = append(filters, fmt.Sprintf("afade=t=in:st=0:d=%.2f", fadeInDuration))
	}
	
	// Fade out
	if fadeOutDuration > 0 {
		// We'll need the total duration for fade out, get it first
		duration, err := GetAudioDuration(inputPath)
		if err != nil {
			return fmt.Errorf("failed to get duration for fade out: %w", err)
		}
		
		fadeStartTime := duration - fadeOutDuration
		if fadeStartTime > 0 {
			filters = append(filters, fmt.Sprintf("afade=t=out:st=%.2f:d=%.2f", fadeStartTime, fadeOutDuration))
		}
	}
	
	if len(filters) == 0 {
		// No effects to apply, just copy the file
		cmd := exec.Command("cp", inputPath, outputPath)
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to copy audio file: %w", err)
		}
	} else {
		filterChain := strings.Join(filters, ",")
		cmd := []string{"ffmpeg", "-i", inputPath, "-af", filterChain, "-y", outputPath}
		if err := ffmpeg.RunCommand(cmd); err != nil {
			return fmt.Errorf("audio effects failed: %w", err)
		}
	}
	
	cleanup.Add(outputPath)
	log.Printf("Applied audio effects: %s", outputPath)
	
	return nil
}

// MixAudioFiles mixes multiple audio files together
func MixAudioFiles(files []string, outputPath string, volumes []float64, cleanup *fileutil.CleanupManager) error {
	if len(files) == 0 {
		return fmt.Errorf("no audio files to mix")
	}
	
	if len(files) == 1 {
		// Single file, just copy it
		cmd := exec.Command("cp", files[0], outputPath)
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to copy single audio file: %w", err)
		}
		cleanup.Add(outputPath)
		return nil
	}
	
	// Build ffmpeg command for mixing
	args := []string{"-y"}
	
	// Add input files
	for _, file := range files {
		args = append(args, "-i", file)
	}
	
	// Build filter graph for mixing
	var inputs []string
	for i := range files {
		volume := 1.0
		if i < len(volumes) {
			volume = volumes[i]
		}
		inputs = append(inputs, fmt.Sprintf("[%d:a]volume=%.2f[a%d]", i, volume, i))
	}
	
	var mixInputs []string
	for i := range files {
		mixInputs = append(mixInputs, fmt.Sprintf("[a%d]", i))
	}
	
	filterGraph := strings.Join(inputs, ";") + ";" + strings.Join(mixInputs, "") + fmt.Sprintf("amix=inputs=%d[out]", len(files))
	
	args = append(args, "-filter_complex", filterGraph, "-map", "[out]", outputPath)
	
	if err := ffmpeg.RunCommand(args); err != nil {
		return fmt.Errorf("audio mixing failed: %w", err)
	}
	
	cleanup.Add(outputPath)
	log.Printf("Mixed %d audio files: %s", len(files), outputPath)
	
	return nil
}
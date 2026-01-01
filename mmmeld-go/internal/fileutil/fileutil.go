package fileutil

import (
	"crypto/sha256"
	"encoding/hex"
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
	"unicode"

	"mmmeld/internal/config"
)

var tempAssetRunNonce = func() string {
	sum := sha256.Sum256([]byte(fmt.Sprintf("%d:%d", os.Getpid(), time.Now().UnixNano())))
	return hex.EncodeToString(sum[:])[:8]
}()

// CleanupManager handles temporary file cleanup
type CleanupManager struct {
	files []string
}

func NewCleanupManager() *CleanupManager {
	return &CleanupManager{
		files: make([]string, 0),
	}
}

func (cm *CleanupManager) Add(filepath string) {
	cm.files = append(cm.files, filepath)
}

// Remove removes a file from the cleanup list (used to preserve files we want to keep)
func (cm *CleanupManager) Remove(filepath string) {
	for i, f := range cm.files {
		if f == filepath {
			cm.files = append(cm.files[:i], cm.files[i+1:]...)
			return
		}
	}
}

func (cm *CleanupManager) Cleanup() error {
	var errors []string
	for _, file := range cm.files {
		if err := os.Remove(file); err != nil && !os.IsNotExist(err) {
			errors = append(errors, fmt.Sprintf("failed to remove %s: %v", file, err))
		}
	}

	if len(errors) > 0 {
		return fmt.Errorf("cleanup errors: %s", strings.Join(errors, "; "))
	}
	return nil
}

// EnsureTempFolder creates the temp assets folder if it doesn't exist
func EnsureTempFolder() error {
	return os.MkdirAll(config.TempAssetsFolder, 0755)
}

// RemoveTempFolderIfEmpty removes the temp assets folder if it's empty
func RemoveTempFolderIfEmpty() error {
	entries, err := os.ReadDir(config.TempAssetsFolder)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}

	if len(entries) == 0 {
		if err := os.Remove(config.TempAssetsFolder); err != nil && !os.IsNotExist(err) {
			return err
		}
	}

	return nil
}

func tempAssetPrefixForOutputPath(outputPath string) string {
	if outputPath == "" {
		return ""
	}

	abs, err := filepath.Abs(outputPath)
	if err != nil {
		abs = outputPath
	}

	sum := sha256.Sum256([]byte(abs))
	return hex.EncodeToString(sum[:])[:12]
}

func TempAssetPath(tempFolder, plannedOutputPath, filename string) string {
	if tempFolder == "" {
		tempFolder = config.TempAssetsFolder
	}

	prefix := tempAssetPrefixForOutputPath(plannedOutputPath)
	if prefix == "" {
		prefix = fmt.Sprintf("t%d", time.Now().UnixMilli())
	}

	return filepath.Join(tempFolder, fmt.Sprintf("%s_%s_%s", prefix, tempAssetRunNonce, filename))
}

// SanitizeFilename cleans a filename for safe filesystem use
func SanitizeFilename(filename string) string {
	// Remove or replace invalid characters
	reg := regexp.MustCompile(`[<>:"/\\|?*]`)
	sanitized := reg.ReplaceAllString(filename, "_")

	// Remove control characters
	sanitized = strings.Map(func(r rune) rune {
		if unicode.IsControl(r) {
			return -1
		}
		return r
	}, sanitized)

	// Trim whitespace and dots
	sanitized = strings.Trim(sanitized, " .")

	// Limit length
	if len(sanitized) > config.MaxFilenameLength {
		sanitized = sanitized[:config.MaxFilenameLength]
	}

	// Ensure it's not empty
	if sanitized == "" {
		sanitized = "unnamed"
	}

	return sanitized
}

// GetDefaultOutputPath generates a default output filename based on audio source
func GetDefaultOutputPath(audioPath string) string {
	if audioPath == "" || audioPath == "generate" {
		return "mmmeld_output.mp4"
	}

	// Extract base name without extension
	base := filepath.Base(audioPath)
	ext := filepath.Ext(base)
	name := strings.TrimSuffix(base, ext)

	// Sanitize the name
	name = SanitizeFilename(name)

	return fmt.Sprintf("%s_mmmeld.mp4", name)
}

// IsYouTubeURL checks if a URL is a YouTube URL
func IsYouTubeURL(url string) bool {
	youtubeRegex := regexp.MustCompile(`(?i)(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/`)
	return youtubeRegex.MatchString(url)
}

// DownloadYouTubeAudio downloads audio from a YouTube URL using yt-dlp
func DownloadYouTubeAudio(url string, cleanup *CleanupManager) (string, error) {
	if err := EnsureTempFolder(); err != nil {
		return "", fmt.Errorf("failed to create temp folder: %w", err)
	}

	runPrefix := tempAssetRunNonce
	outputTemplate := filepath.Join(config.TempAssetsFolder, fmt.Sprintf("%s_%%(title)s.%%(ext)s", runPrefix))

	cmd := exec.Command("yt-dlp",
		"--format", "bestaudio/best",
		"--extract-audio",
		"--audio-format", "mp3",
		"--audio-quality", "192K",
		"--output", outputTemplate,
		url,
	)

	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("yt-dlp failed: %w\nOutput: %s", err, output)
	}

	// Find the downloaded file
	// yt-dlp outputs the filename, we need to parse it
	lines := strings.Split(string(output), "\n")
	var downloadedFile string

	for _, line := range lines {
		if strings.Contains(line, "has already been downloaded") ||
			strings.Contains(line, "Destination:") ||
			strings.Contains(line, "[download]") && strings.Contains(line, ".mp3") {
			// Extract filename from line
			parts := strings.Fields(line)
			for _, part := range parts {
				if strings.HasSuffix(part, ".mp3") && strings.Contains(part, config.TempAssetsFolder) {
					downloadedFile = part
					break
				}
			}
		}
	}

	if downloadedFile == "" {
		// Fallback: look for any .mp3 file in temp folder
		files, err := filepath.Glob(filepath.Join(config.TempAssetsFolder, fmt.Sprintf("%s_*.mp3", runPrefix)))
		if err != nil || len(files) == 0 {
			return "", fmt.Errorf("could not find downloaded audio file")
		}
		downloadedFile = files[len(files)-1] // Get the most recent
	}

	cleanup.Add(downloadedFile)
	log.Printf("Downloaded YouTube audio: %s", downloadedFile)

	return downloadedFile, nil
}

// DownloadYouTubeVideo downloads video from a YouTube URL using yt-dlp
func DownloadYouTubeVideo(url string, cleanup *CleanupManager) (string, error) {
	if err := EnsureTempFolder(); err != nil {
		return "", fmt.Errorf("failed to create temp folder: %w", err)
	}

	runPrefix := tempAssetRunNonce
	outputTemplate := filepath.Join(config.TempAssetsFolder, fmt.Sprintf("%s_%%(title)s.%%(ext)s", runPrefix))

	cmd := exec.Command("yt-dlp",
		"--format", "best[ext=mp4]/best",
		"--output", outputTemplate,
		url,
	)

	output, err := cmd.CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("yt-dlp failed for video: %w\nOutput: %s", err, output)
	}

	// Find the downloaded file
	lines := strings.Split(string(output), "\n")
	var downloadedFile string

	for _, line := range lines {
		if strings.Contains(line, "has already been downloaded") ||
			strings.Contains(line, "Destination:") ||
			strings.Contains(line, "[download]") && (strings.Contains(line, ".mp4") || strings.Contains(line, ".webm")) {
			parts := strings.Fields(line)
			for _, part := range parts {
				if (strings.HasSuffix(part, ".mp4") || strings.HasSuffix(part, ".webm")) &&
					strings.Contains(part, config.TempAssetsFolder) {
					downloadedFile = part
					break
				}
			}
		}
	}

	if downloadedFile == "" {
		// Fallback: look for video files in temp folder
		patterns := []string{
			fmt.Sprintf("%s_*.mp4", runPrefix),
			fmt.Sprintf("%s_*.webm", runPrefix),
			fmt.Sprintf("%s_*.mkv", runPrefix),
		}
		for _, pattern := range patterns {
			files, err := filepath.Glob(filepath.Join(config.TempAssetsFolder, pattern))
			if err == nil && len(files) > 0 {
				downloadedFile = files[len(files)-1]
				break
			}
		}
	}

	if downloadedFile == "" {
		return "", fmt.Errorf("could not find downloaded video file")
	}

	cleanup.Add(downloadedFile)
	log.Printf("Downloaded YouTube video: %s", downloadedFile)

	return downloadedFile, nil
}

// DownloadImage downloads an image from a URL
func DownloadImage(url string, cleanup *CleanupManager) (string, error) {
	if err := EnsureTempFolder(); err != nil {
		return "", fmt.Errorf("failed to create temp folder: %w", err)
	}

	resp, err := http.Get(url)
	if err != nil {
		return "", fmt.Errorf("failed to download image: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("failed to download image: HTTP %d", resp.StatusCode)
	}

	// Determine file extension from content type or URL
	ext := ".jpg" // default
	contentType := resp.Header.Get("Content-Type")
	switch contentType {
	case "image/png":
		ext = ".png"
	case "image/gif":
		ext = ".gif"
	case "image/webp":
		ext = ".webp"
	default:
		// Try to get extension from URL
		if urlExt := filepath.Ext(url); urlExt != "" {
			ext = urlExt
		}
	}

	filename := fmt.Sprintf("downloaded_image_%d%s", time.Now().UnixNano(), ext)
	filepath := filepath.Join(config.TempAssetsFolder, filename)

	file, err := os.Create(filepath)
	if err != nil {
		return "", fmt.Errorf("failed to create image file: %w", err)
	}
	defer file.Close()

	_, err = io.Copy(file, resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to save image: %w", err)
	}

	cleanup.Add(filepath)
	log.Printf("Downloaded image: %s", filepath)

	return filepath, nil
}

// GetMultilineInput reads multiline input from stdin (for interactive mode)
func GetMultilineInput(prompt string) string {
	fmt.Print(prompt)
	var lines []string

	for {
		var line string
		fmt.Scanln(&line)
		if line == "" {
			break
		}
		lines = append(lines, line)
	}

	return strings.Join(lines, "\n")
}

// FileExists checks if a file exists
func FileExists(filename string) bool {
	_, err := os.Stat(filename)
	return err == nil
}

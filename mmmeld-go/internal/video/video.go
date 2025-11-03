package video

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	"mmmeld/internal/config"
	"mmmeld/internal/ffmpeg"
	"mmmeld/internal/fileutil"
	"mmmeld/internal/image"
)

// Instructions (from Python original):
// 1. Review and Rewrite:
//    - Study README.md for requirements and use cases.
//    - Review all .py files for bugs and missing features, focusing on video generation.
//    - Rewrite video_utils.py to meet all requirements.
// 2. Duration Calculation:
//    - Create a function to determine total duration based on main audio, inputs, and margin.
//    - With audio: total duration = main_audio_duration + start_margin + end_margin.
//    - Without audio: total duration = 5 seconds per image + video durations.
//    - Images and videos play sequentially, and start/end margins are ignored without main audio.
// 3. Visual Sequence:
//    - Create a function to sequence and render visuals to a lossless file.
//    - Visuals sized for full expected duration; images have a natural duration of 5 seconds.
//    - Multiple videos render sequentially into one sequence.
// 4. Final Render:
//    - Loop visual elements, overlay main audio with margins and background music.
//    - Fade out background music and sequence in the tail margin window if main audio exists.
//    - No main audio: use video audio and looping background music, cut off at sequence end.
//    - Avoid overlapping video audio; background music loops and cuts off with sequence or audio end.
//    - Disable audio processing when only images are present.
// 5. Additional Notes:
//    - Use ffmpeg, not moviepy.
//    - Prioritize validation tests: single image with audio, single image without audio, etc.
//    - Embed these instructions as comments in video_utils.py and never remove them.

type Dimensions struct {
	Width  int
	Height int
}

type VideoGenParams struct {
	MediaInputs     []image.MediaInput
	AudioPath       string
	BGMusicPath     string
	OutputPath      string
	BGMusicVolume   float64
	AudioMargins    config.AudioMargins
	TempFolder      string
	TargetDimensions *Dimensions
}

// GetMediaDuration returns the duration of a media file in seconds
// For images, returns 5.0 seconds (standard duration)
func GetMediaDuration(filepath string) (float64, error) {
	if image.IsImageFile(filepath) {
		log.Printf("Using standard 5-second duration for image: %s", filepath)
		return 5.0, nil
	}
	
	cmd := exec.Command("ffprobe", "-v", "error", "-show_entries", "format=duration",
		"-of", "default=noprint_wrappers=1:nokey=1", filepath)
	
	output, err := cmd.Output()
	if err != nil {
		return 0, fmt.Errorf("failed to get media duration for %s: %w", filepath, err)
	}
	
	durationStr := strings.TrimSpace(string(output))
	if durationStr == "" {
		return 0, fmt.Errorf("ffprobe returned empty duration for %s", filepath)
	}
	
	duration, err := strconv.ParseFloat(durationStr, 64)
	if err != nil {
		return 0, fmt.Errorf("failed to parse duration '%s': %w", durationStr, err)
	}
	
	log.Printf("Media duration for %s: %.3f seconds", filepath, duration)
	return duration, nil
}

// CalculateTotalDuration determines the total output video duration
func CalculateTotalDuration(audioPath string, mediaInputs []image.MediaInput, margins config.AudioMargins) (float64, error) {
	if audioPath != "" {
		// With main audio: total = audio_duration + start_margin + end_margin
		audioDuration, err := GetMediaDuration(audioPath)
		if err != nil {
			return 0, fmt.Errorf("failed to get audio duration: %w", err)
		}
		total := audioDuration + margins.Start + margins.End
		log.Printf("Total duration (with audio): %.3f = %.3f + %.3f + %.3f", 
			total, audioDuration, margins.Start, margins.End)
		return total, nil
	}
	
	// Without main audio: sum of all media durations
	var totalDuration float64
	for _, input := range mediaInputs {
		duration, err := GetMediaDuration(input.Path)
		if err != nil {
			return 0, fmt.Errorf("failed to get duration for %s: %w", input.Path, err)
		}
		totalDuration += duration
	}
	
	// Ensure minimum 5 seconds
	if totalDuration < 5.0 {
		totalDuration = 5.0
	}
	
	log.Printf("Total duration (without audio): %.3f seconds", totalDuration)
	return totalDuration, nil
}

// CalculateMaxDimensions finds the maximum width and height from all inputs
func CalculateMaxDimensions(mediaInputs []image.MediaInput) (Dimensions, error) {
	var maxWidth, maxHeight int
	
	for _, input := range mediaInputs {
		cmd := exec.Command("ffprobe", "-v", "error", "-select_streams", "v:0",
			"-show_entries", "stream=width,height,rotation", "-of", "json", input.Path)
		
		output, err := cmd.Output()
		if err != nil {
			log.Printf("Warning: Failed to get dimensions for %s: %v", input.Path, err)
			continue
		}
		
		var data struct {
			Streams []struct {
				Width  int `json:"width"`
				Height int `json:"height"`
				Tags   struct {
					Rotate string `json:"rotate"`
				} `json:"tags"`
			} `json:"streams"`
		}
		
		if err := json.Unmarshal(output, &data); err != nil {
			log.Printf("Warning: Failed to parse dimensions for %s: %v", input.Path, err)
			continue
		}
		
		if len(data.Streams) == 0 {
			continue
		}
		
		stream := data.Streams[0]
		width, height := stream.Width, stream.Height
		
		// Handle rotation
		if stream.Tags.Rotate == "90" || stream.Tags.Rotate == "270" {
			log.Printf("Detected %s degree rotation for %s", stream.Tags.Rotate, input.Path)
			width, height = height, width
		}
		
		if width > maxWidth {
			maxWidth = width
		}
		if height > maxHeight {
			maxHeight = height
		}
	}
	
	// Default dimensions if no valid inputs found
	if maxWidth == 0 || maxHeight == 0 {
		maxWidth, maxHeight = 1920, 1080
	}
	
	log.Printf("Calculated max dimensions: %dx%d", maxWidth, maxHeight)
	return Dimensions{Width: maxWidth, Height: maxHeight}, nil
}

// CreateVisualSequence creates video and audio sequences from media inputs
func CreateVisualSequence(mediaInputs []image.MediaInput, totalDuration float64, tempFolder string, hasMainAudio bool, dimensions Dimensions) (string, string, error) {
	tempVideoSeq := filepath.Join(tempFolder, "temp_video_sequence.mkv")
	tempAudioSeq := filepath.Join(tempFolder, "temp_audio_sequence.wav")
	
	var videoFilters, audioFilters []string
	var inputs []string
	
	for i, input := range mediaInputs {
		// Ensure video has audio track
		inputWithAudio, err := ensureVideoHasAudio(input.Path, tempFolder)
		if err != nil {
			return "", "", fmt.Errorf("failed to ensure audio for %s: %w", input.Path, err)
		}
		
		inputs = append(inputs, "-i", inputWithAudio)
		
		duration, err := GetMediaDuration(input.Path)
		if err != nil {
			return "", "", fmt.Errorf("failed to get duration for %s: %w", input.Path, err)
		}
		
		var targetDuration float64
		if hasMainAudio {
			// For single media with main audio, use total duration for looping/cutting
			if len(mediaInputs) == 1 {
				targetDuration = totalDuration
			} else {
				// For multiple media with main audio, give images 5s each, rest to videos
				if image.IsImageFile(input.Path) {
					targetDuration = 5.0 // Standard duration for images
				} else {
					// Calculate remaining time after allocating 5s per image
					imageCount := 0
					for _, inp := range mediaInputs {
						if image.IsImageFile(inp.Path) {
							imageCount++
						}
					}
					videoCount := len(mediaInputs) - imageCount
					remainingTime := totalDuration - (float64(imageCount) * 5.0)
					if videoCount > 0 {
						targetDuration = remainingTime / float64(videoCount)
					} else {
						targetDuration = totalDuration / float64(len(mediaInputs))
					}
				}
			}
		} else {
			if input.IsVideo {
				targetDuration = duration // Use original duration
			} else {
				targetDuration = 5.0 // Standard image duration
			}
		}
		
		if image.IsImageFile(input.Path) {
			videoFilters = append(videoFilters, fmt.Sprintf(
				"[%d:v]loop=loop=-1:size=1:start=0,trim=duration=%.3f,scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS[v%d];",
				i, targetDuration, dimensions.Width, dimensions.Height, dimensions.Width, dimensions.Height, i))
			audioFilters = append(audioFilters, fmt.Sprintf("aevalsrc=0:duration=%.3f[a%d];", targetDuration, i))
		} else {
			// For videos, handle looping if needed
			if hasMainAudio && duration < targetDuration {
				// Video needs to loop
				loopCount := int(targetDuration/duration) + 1
				videoFilters = append(videoFilters, fmt.Sprintf(
					"[%d:v]loop=loop=%d:size=%d:start=0,trim=duration=%.3f,scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS[v%d];",
					i, loopCount, int(duration*30), targetDuration, dimensions.Width, dimensions.Height, dimensions.Width, dimensions.Height, i))
				audioFilters = append(audioFilters, fmt.Sprintf(
					"[%d:a]aloop=loop=%d:size=%d,atrim=duration=%.3f,asetpts=PTS-STARTPTS[a%d];",
					i, loopCount, int(duration*44100), targetDuration, i))
			} else {
				// Video is longer or same length, just trim
				videoFilters = append(videoFilters, fmt.Sprintf(
					"[%d:v]trim=duration=%.3f,scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS[v%d];",
					i, targetDuration, dimensions.Width, dimensions.Height, dimensions.Width, dimensions.Height, i))
				audioFilters = append(audioFilters, fmt.Sprintf("[%d:a]atrim=duration=%.3f,asetpts=PTS-STARTPTS[a%d];", i, targetDuration, i))
			}
		}
	}
	
	// Concatenate video streams
	var videoInputs []string
	for i := range mediaInputs {
		videoInputs = append(videoInputs, fmt.Sprintf("[v%d]", i))
	}
	videoFilters = append(videoFilters, fmt.Sprintf("%sconcat=n=%d:v=1:a=0[outv]", strings.Join(videoInputs, ""), len(mediaInputs)))
	
	// Concatenate audio streams
	var audioInputs []string
	for i := range mediaInputs {
		audioInputs = append(audioInputs, fmt.Sprintf("[a%d]", i))
	}
	audioFilters = append(audioFilters, fmt.Sprintf("%sconcat=n=%d:v=0:a=1[outa]", strings.Join(audioInputs, ""), len(mediaInputs)))
	
	// Create video sequence
	videoCmd := []string{"ffmpeg", "-y", "-hwaccel", "auto"}
	videoCmd = append(videoCmd, inputs...)
	videoCmd = append(videoCmd, "-filter_complex", strings.Join(videoFilters, ""),
		"-map", "[outv]", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0", tempVideoSeq)
	
	log.Printf("Creating video sequence: %s", strings.Join(videoCmd, " "))
	if err := runFFmpegCommand(videoCmd); err != nil {
		return "", "", fmt.Errorf("failed to create video sequence: %w", err)
	}
	
	// Create audio sequence
	audioCmd := []string{"ffmpeg", "-y"}
	audioCmd = append(audioCmd, inputs...)
	audioCmd = append(audioCmd, "-filter_complex", strings.Join(audioFilters, ""),
		"-map", "[outa]", "-c:a", "pcm_s16le", tempAudioSeq)
	
	log.Printf("Creating audio sequence: %s", strings.Join(audioCmd, " "))
	if err := runFFmpegCommand(audioCmd); err != nil {
		return "", "", fmt.Errorf("failed to create audio sequence: %w", err)
	}
	
	return tempVideoSeq, tempAudioSeq, nil
}

// GenerateVideo creates the final video with all effects and audio
func GenerateVideo(params VideoGenParams) error {
	if err := fileutil.EnsureTempFolder(); err != nil {
		return fmt.Errorf("failed to create temp folder: %w", err)
	}
	
	// Determine dimensions
	var dimensions Dimensions
	if params.TargetDimensions != nil {
		dimensions = *params.TargetDimensions
	} else {
		var err error
		dimensions, err = CalculateMaxDimensions(params.MediaInputs)
		if err != nil {
			return fmt.Errorf("failed to calculate dimensions: %w", err)
		}
	}
	
	// Calculate total duration
	totalDuration, err := CalculateTotalDuration(params.AudioPath, params.MediaInputs, params.AudioMargins)
	if err != nil {
		return fmt.Errorf("failed to calculate total duration: %w", err)
	}
	
	// Create visual sequence
	visualSeq, audioSeq, err := CreateVisualSequence(params.MediaInputs, totalDuration, params.TempFolder, params.AudioPath != "", dimensions)
	if err != nil {
		return fmt.Errorf("failed to create visual sequence: %w", err)
	}
	defer os.Remove(visualSeq)
	defer os.Remove(audioSeq)
	
	// Build final ffmpeg command
	var filterComplex []string
	inputs := []string{"-i", visualSeq, "-i", audioSeq}
	
	if params.AudioPath != "" {
		inputs = append(inputs, "-i", params.AudioPath)
		filterComplex = append(filterComplex, fmt.Sprintf(
			"[2:a]adelay=%d|%d,apad=pad_dur=%.3f,loudnorm=I=-16:TP=-1.5:LRA=11[main_audio];",
			int(params.AudioMargins.Start*1000), int(params.AudioMargins.Start*1000), params.AudioMargins.End))
	}
	
	// Visual sequence should already be the correct duration
	filterComplex = append(filterComplex, "[0:v]setpts=PTS-STARTPTS[trimmed_video];")
	
	// Add background music if specified
	if params.BGMusicPath != "" {
		inputs = append(inputs, "-i", params.BGMusicPath)
		bgIndex := len(inputs)/2 - 1
		filterComplex = append(filterComplex, fmt.Sprintf("[%d:a]aloop=-1:size=2e+09,volume=%.2f[bg_music];", bgIndex, params.BGMusicVolume))
	}
	
	// Apply video effects
	filterComplex = append(filterComplex, "[trimmed_video]fps=30,format=yuv420p")
	if params.AudioPath != "" {
		filterComplex = append(filterComplex, fmt.Sprintf(",fade=t=out:st=%.3f:d=%.3f", totalDuration-params.AudioMargins.End, params.AudioMargins.End))
	}
	filterComplex = append(filterComplex, "[faded_video];")
	
	// Mix audio streams
	if params.AudioPath != "" && params.BGMusicPath != "" {
		filterComplex = append(filterComplex, "[main_audio][bg_music]amix=inputs=2:duration=first:dropout_transition=2[final_audio];")
	} else if params.AudioPath != "" {
		filterComplex = append(filterComplex, "[main_audio]acopy[final_audio];")
	} else if params.BGMusicPath != "" {
		filterComplex = append(filterComplex, "[1:a][bg_music]amix=inputs=2:duration=first:dropout_transition=2[final_audio];")
	} else {
		filterComplex = append(filterComplex, "[1:a]acopy[final_audio];")
	}
	
	// Apply audio fade out
	filterComplex = append(filterComplex, fmt.Sprintf("[final_audio]afade=t=out:st=%.3f:d=%.3f[faded_audio];", totalDuration-params.AudioMargins.End, params.AudioMargins.End))
	
	// Build final command
	cmd := []string{"ffmpeg", "-y"}
	cmd = append(cmd, inputs...)
	cmd = append(cmd, "-filter_complex", strings.Join(filterComplex, ""),
		"-map", "[faded_video]", "-map", "[faded_audio]",
		"-c:v", "libx264", "-preset", "slow", "-crf", "18",
		"-c:a", "aac", "-b:a", "192k",
		"-movflags", "+faststart",
		"-t", fmt.Sprintf("%.3f", totalDuration),
		params.OutputPath)
	
	log.Printf("Generating final video: %s", strings.Join(cmd, " "))
	return runFFmpegCommand(cmd)
}

// ensureVideoHasAudio adds silent audio track to videos that don't have audio
func ensureVideoHasAudio(inputPath, tempFolder string) (string, error) {
	outputPath := filepath.Join(tempFolder, fmt.Sprintf("audio_ensured_%s", filepath.Base(inputPath)))
	
	// Check if video already has audio
	cmd := exec.Command("ffprobe", "-v", "error", "-select_streams", "a", "-count_packets",
		"-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", inputPath)
	
	output, err := cmd.Output()
	if err == nil {
		if audioPackets, parseErr := strconv.Atoi(strings.TrimSpace(string(output))); parseErr == nil && audioPackets > 0 {
			// Video already has audio
			return inputPath, nil
		}
	}
	
	// Add silent audio track
	addAudioCmd := []string{"ffmpeg", "-y", "-i", inputPath,
		"-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
		"-c:v", "copy", "-c:a", "aac", "-shortest", outputPath}
	
	log.Printf("Adding silent audio to video: %s", strings.Join(addAudioCmd, " "))
	if err := runFFmpegCommand(addAudioCmd); err != nil {
		return "", err
	}
	
	return outputPath, nil
}

// runFFmpegCommand executes ffmpeg with proper error handling and real-time output
func runFFmpegCommand(cmd []string) error {
	return ffmpeg.RunCommand(cmd)
}

// ValidateVideo checks if the generated video meets expectations
func ValidateVideo(outputPath string, expectedDuration float64, shouldHaveAudio bool) error {
	// Check duration
	actualDuration, err := GetMediaDuration(outputPath)
	if err != nil {
		return fmt.Errorf("failed to get video duration: %w", err)
	}
	
	if abs(actualDuration-expectedDuration) > 0.5 { // 0.5 second tolerance
		return fmt.Errorf("duration mismatch: expected %.3f, got %.3f", expectedDuration, actualDuration)
	}
	
	// Check audio if required
	if shouldHaveAudio {
		cmd := exec.Command("ffprobe", "-v", "error", "-select_streams", "a", "-count_packets",
			"-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", outputPath)
		
		output, err := cmd.Output()
		if err != nil {
			return fmt.Errorf("failed to check audio: %w", err)
		}
		
		audioPackets, err := strconv.Atoi(strings.TrimSpace(string(output)))
		if err != nil || audioPackets == 0 {
			return fmt.Errorf("video should have audio but none found")
		}
	}
	
	log.Printf("Video validation passed: %s", outputPath)
	return nil
}

// Helper functions
func min(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}

func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"mmmeld/internal/config"
	"mmmeld/internal/fileutil"
	"mmmeld/internal/genai"
	"mmmeld/internal/image"
)

type OutputFormat string

const (
	FormatText OutputFormat = "text"
	FormatJSON OutputFormat = "json"
)

func main() {
	// Setup logging
	config.SetupLogging()

	// Parse command line arguments
	audioFile := flag.String("file", "", "Path to the audio file (mp3, wav, aac, etc.)")
	audioFileShort := flag.String("f", "", "Path to the audio file (shorthand)")
	title := flag.String("title", "", "Title of the track")
	titleShort := flag.String("t", "", "Title of the track (shorthand)")
	notes := flag.String("notes", "", "Context notes (genre, mood, themes, lyrics)")
	notesShort := flag.String("n", "", "Context notes (shorthand)")
	style := flag.String("style", "auto", "Preferred visual style: auto, photorealistic, artistic, abstract, cinematic")
	styleShort := flag.String("s", "auto", "Preferred visual style (shorthand)")
	model := flag.String("model", genai.DefaultModel, "Gemini model to use")
	save := flag.Bool("save", false, "Save prompt to a text file alongside the audio")
	jsonOutput := flag.Bool("json", false, "Output in JSON format")
	quiet := flag.Bool("quiet", false, "Suppress progress messages")
	quietShort := flag.Bool("q", false, "Suppress progress messages (shorthand)")
	debug := flag.Bool("debug", false, "Show raw audio analysis from Gemini (for debugging)")
	debugShort := flag.Bool("d", false, "Show raw audio analysis (shorthand)")
	verify := flag.Bool("verify", false, "Generate image with Ideogram and verify with Gemini")
	verifyShort := flag.Bool("v", false, "Generate and verify image (shorthand)")
	caption := flag.String("caption", "", "Caption/title text to render on the image")
	captionShort := flag.String("c", "", "Caption text (shorthand)")
	subcaption := flag.String("subcaption", "", "Subcaption/subtitle text to render on the image")
	subcaptionShort := flag.String("sc", "", "Subcaption text (shorthand)")
	var aspectRatioVal string
	flag.StringVar(&aspectRatioVal, "aspect-ratio", "16:9", "Aspect ratio for generated image (16:9, 9:16, 1:1, etc.)")
	flag.StringVar(&aspectRatioVal, "ar", "16:9", "Aspect ratio (shorthand)")

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Audio to Image Prompt Generator\n\n")
		fmt.Fprintf(os.Stderr, "Analyzes audio files using Google Gemini to generate detailed image prompts\n")
		fmt.Fprintf(os.Stderr, "optimized for AI image generators like Ideogram.\n\n")
		fmt.Fprintf(os.Stderr, "Usage: %s [options] [audio_file]\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "Options:\n")
		flag.PrintDefaults()
		fmt.Fprintf(os.Stderr, "\nExamples:\n")
		fmt.Fprintf(os.Stderr, "  %s -file song.mp3 -title \"Midnight Drive\"\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  %s -f remix.wav -t \"Energy Burst\" -n \"Upbeat electronic dance track\"\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  %s -f audio.mp3 -t \"Peaceful Morning\" -s artistic --save\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  %s song.mp3 --json\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "\nEnvironment Variables:\n")
		fmt.Fprintf(os.Stderr, "  GEMINI_API_KEY    Required. Your Google Gemini API key.\n")
	}

	flag.Parse()

	// Handle positional argument for audio file
	audioPath := coalesce(*audioFile, *audioFileShort)
	if audioPath == "" && flag.NArg() > 0 {
		audioPath = flag.Arg(0)
	}

	if audioPath == "" {
		fmt.Fprintln(os.Stderr, "Error: Please provide an audio file using -file or as a positional argument")
		flag.Usage()
		os.Exit(1)
	}

	// Expand path (handle ~)
	audioPath = expandPath(audioPath)

	// Validate file exists
	if _, err := os.Stat(audioPath); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Error: Audio file '%s' not found.\n", audioPath)
		os.Exit(1)
	}

	// Validate it's an audio file
	if !genai.IsAudioFile(audioPath) {
		fmt.Fprintf(os.Stderr, "Warning: '%s' may not be a recognized audio format.\n", audioPath)
	}

	// Coalesce options
	titleVal := coalesce(*title, *titleShort)
	notesVal := coalesce(*notes, *notesShort)
	styleVal := coalesce(*style, *styleShort)
	quietVal := *quiet || *quietShort || *jsonOutput
	debugVal := *debug || *debugShort
	verifyVal := *verify || *verifyShort
	captionVal := coalesce(*caption, *captionShort)
	subcaptionVal := coalesce(*subcaption, *subcaptionShort)
	// aspectRatioVal is already set via StringVar

	// Map style string to StylePreference
	stylePreference := mapStylePreference(styleVal)

	// Create context
	ctx := context.Background()

	// Create client
	client, err := genai.NewClient(ctx)
	if err != nil {
		outputError(err, *jsonOutput)
		os.Exit(1)
	}

	// Generate the prompt
	opts := genai.PromptOptions{
		Title:           titleVal,
		Notes:           notesVal,
		Caption:         captionVal,
		Subcaption:      subcaptionVal,
		StylePreference: stylePreference,
		Model:           *model,
		Quiet:           quietVal,
		Debug:           debugVal,
	}

	result, err := client.GenerateImagePrompt(audioPath, opts)
	if err != nil {
		outputError(err, *jsonOutput)
		os.Exit(1)
	}

	// Output the result
	if *jsonOutput {
		outputJSON(result)
	} else {
		outputText(result)
	}

	// If verify mode, generate image and validate it
	if verifyVal {
		verifyImageGeneration(result.Prompt, titleVal, captionVal, subcaptionVal, aspectRatioVal, quietVal)
	}

	// Save to file if requested
	if *save {
		outputPath := savePromptToFile(result)
		if !quietVal {
			fmt.Printf("\nPrompt saved to: %s\n", outputPath)
		}
	}
}

func coalesce(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}

func expandPath(path string) string {
	if strings.HasPrefix(path, "~/") {
		home, err := os.UserHomeDir()
		if err == nil {
			return filepath.Join(home, path[2:])
		}
	}
	return path
}

func mapStylePreference(style string) genai.StylePreference {
	switch strings.ToLower(style) {
	case "photorealistic":
		return genai.StylePhotorealistic
	case "artistic":
		return genai.StyleArtistic
	case "abstract":
		return genai.StyleAbstract
	case "cinematic":
		return genai.StyleCinematic
	default:
		return genai.StyleAuto
	}
}

func outputText(result *genai.PromptResult) {
	fmt.Println()
	fmt.Println(strings.Repeat("=", 60))
	fmt.Println("IDEOGRAM PROMPT")
	fmt.Println(strings.Repeat("=", 60))
	fmt.Println(result.Prompt)
	fmt.Println(strings.Repeat("=", 60))
}

func outputJSON(result *genai.PromptResult) {
	output := map[string]interface{}{
		"title":      result.Title,
		"audio_file": result.AudioFile,
		"style":      string(result.Style),
		"prompt":     result.Prompt,
		"timestamp":  result.Timestamp.Format("2006-01-02 15:04:05"),
	}

	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	encoder.Encode(output)
}

func outputError(err error, jsonFormat bool) {
	if jsonFormat {
		output := map[string]interface{}{
			"error":     err.Error(),
			"timestamp": time.Now().Format("2006-01-02 15:04:05"),
		}
		encoder := json.NewEncoder(os.Stderr)
		encoder.SetIndent("", "  ")
		encoder.Encode(output)
	} else {
		log.Printf("Error: %v", err)
	}
}

func savePromptToFile(result *genai.PromptResult) string {
	baseName := strings.TrimSuffix(result.AudioFile, filepath.Ext(result.AudioFile))
	outputPath := baseName + "_ideogram_prompt.txt"

	content := fmt.Sprintf("Title: %s\nAudio: %s\nGenerated: %s\n%s\n%s",
		result.Title,
		filepath.Base(result.AudioFile),
		result.Timestamp.Format("2006-01-02 15:04:05"),
		strings.Repeat("-", 50),
		result.Prompt,
	)

	os.WriteFile(outputPath, []byte(content), 0644)
	return outputPath
}

func verifyImageGeneration(prompt, title, caption, subcaption, aspectRatioStr string, quiet bool) {
	if !quiet {
		fmt.Println()
		fmt.Println(strings.Repeat("=", 60))
		fmt.Println("VERIFICATION MODE: Generating and validating image...")
		fmt.Println(strings.Repeat("=", 60))
	}

	// Create cleanup manager
	cleanup := fileutil.NewCleanupManager()
	defer cleanup.Cleanup()

	// Ensure temp folder exists
	if err := fileutil.EnsureTempFolder(); err != nil {
		log.Printf("Error creating temp folder: %v", err)
		return
	}

	// Parse aspect ratio
	ar := parseAspectRatioString(aspectRatioStr)

	// Build image generation options
	opts := image.ImageGenOptions{
		Description:  prompt,
		Title:        title,
		Caption:      caption,
		Subcaption:   subcaption,
		AspectRatio:  ar,
		Provider:     config.ImageProviderIdeogram,
		MaxRetries:   3,
		ValidateText: caption != "" || subcaption != "",
	}

	// Generate and validate the image
	result, err := image.GenerateAndValidateImage(opts, cleanup)
	if err != nil {
		log.Printf("Image generation failed: %v", err)
		return
	}

	if !quiet {
		fmt.Printf("\n✓ Image generated: %s\n", result.Path)
	}

	// Now validate the image against the prompt using Gemini
	if !quiet {
		fmt.Println("\nValidating image matches prompt intent...")
	}

	validation, err := genai.ValidateImageAgainstPrompt(result.Path, prompt, caption, subcaption)
	if err != nil {
		log.Printf("Validation failed: %v", err)
		return
	}

	// Output validation results
	fmt.Println()
	fmt.Println(strings.Repeat("=", 60))
	fmt.Println("VALIDATION RESULTS")
	fmt.Println(strings.Repeat("=", 60))

	if validation.PromptMatch {
		fmt.Println("✓ Image matches prompt intent")
	} else {
		fmt.Println("✗ Image does NOT match prompt intent")
	}

	if caption != "" || subcaption != "" {
		if validation.TextRendered {
			fmt.Println("✓ Text rendered correctly")
		} else {
			fmt.Println("✗ Text rendering issues detected")
		}

		if validation.CasingCorrect {
			fmt.Println("✓ Text casing is appropriate")
		} else {
			fmt.Printf("⚠ Text casing may differ from expected (style-appropriate: %v)\n", validation.CasingAppropriate)
		}
	}

	if len(validation.Issues) > 0 {
		fmt.Println("\nIssues found:")
		for _, issue := range validation.Issues {
			fmt.Printf("  - %s\n", issue)
		}
	}

	if len(validation.Suggestions) > 0 {
		fmt.Println("\nSuggestions:")
		for _, suggestion := range validation.Suggestions {
			fmt.Printf("  • %s\n", suggestion)
		}
	}

	fmt.Println(strings.Repeat("=", 60))
}

func parseAspectRatioString(s string) config.AspectRatio {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case "16:9", "16x9":
		return config.AspectRatio16x9
	case "9:16", "9x16":
		return config.AspectRatio9x16
	case "1:1", "1x1", "square":
		return config.AspectRatio1x1
	case "4:3", "4x3":
		return config.AspectRatio4x3
	case "3:4", "3x4":
		return config.AspectRatio3x4
	case "3:2", "3x2":
		return config.AspectRatio3x2
	case "2:3", "2x3":
		return config.AspectRatio2x3
	default:
		return config.AspectRatio16x9
	}
}

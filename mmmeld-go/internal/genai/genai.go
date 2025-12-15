// Package genai provides integration with Google's Gemini API for audio analysis
// and image prompt generation.
package genai

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"google.golang.org/genai"
)

const (
	// DefaultModel is the default Gemini model for audio analysis
	// Use gemini-3-pro-preview for best quality analysis
	DefaultModel = "models/gemini-3-pro-preview"
)

// ANSI color codes for terminal output
const (
	colorReset  = "\033[0m"
	colorYellow = "\033[33m"
	colorRed    = "\033[31m"
)

// logWarning logs a warning message in yellow
func logWarning(format string, v ...interface{}) {
	msg := fmt.Sprintf(format, v...)
	log.Printf("%sWarning: %s%s", colorYellow, msg, colorReset)
}

// StylePreference represents the preferred visual style for generated prompts
type StylePreference string

const (
	StyleAuto           StylePreference = "auto"
	StylePhotorealistic StylePreference = "photorealistic"
	StyleArtistic       StylePreference = "artistic"
	StyleAbstract       StylePreference = "abstract"
	StyleCinematic      StylePreference = "cinematic"
)

// PromptOptions contains options for generating an image prompt from audio
type PromptOptions struct {
	Title           string
	Notes           string
	Caption         string // Text to render as title/caption on the image
	Subcaption      string // Text to render as subtitle/subcaption on the image
	StylePreference StylePreference
	Model           string
	Quiet           bool
	Debug           bool // Enable verbose debug output
}

// PromptResult contains the result of prompt generation
type PromptResult struct {
	Prompt        string
	Title         string
	AudioFile     string
	Style         StylePreference
	Timestamp     time.Time
	AudioAnalysis string // Raw audio analysis (when debug mode)
}

// Client wraps the Google GenAI client
type Client struct {
	client *genai.Client
	ctx    context.Context
}

// NewClient creates a new Gemini API client
func NewClient(ctx context.Context) (*Client, error) {
	apiKey := os.Getenv("GEMINI_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("GEMINI_API_KEY environment variable not set")
	}

	client, err := genai.NewClient(ctx, &genai.ClientConfig{
		APIKey:  apiKey,
		Backend: genai.BackendGeminiAPI,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create Gemini client: %w", err)
	}

	return &Client{
		client: client,
		ctx:    ctx,
	}, nil
}

// AudioBrief contains structured analysis of audio for image prompt generation
type AudioBrief struct {
	Genre                string   `json:"genre"`
	BPM                  int      `json:"bpm"`
	Energy               int      `json:"energy"` // 1-10
	MoodAdjectives       []string `json:"mood_adjectives"`
	ProminentInstruments []string `json:"prominent_instruments"`
	VisualNouns          []string `json:"visual_nouns"`
	Textures             []string `json:"textures"`
	PaletteColors        []string `json:"palette_colors"`
	CentralMetaphor      string   `json:"central_metaphor"`
	Avoid                []string `json:"avoid"`
	LyricThemes          string   `json:"lyric_themes"`
}

// GenerateImagePrompt analyzes an audio file and generates an image prompt using 2-pass pipeline
func (c *Client) GenerateImagePrompt(audioPath string, opts PromptOptions) (*PromptResult, error) {
	// Set defaults
	if opts.Model == "" {
		opts.Model = DefaultModel
	}
	if opts.StylePreference == "" {
		opts.StylePreference = StyleAuto
	}
	if opts.Title == "" {
		opts.Title = strings.TrimSuffix(filepath.Base(audioPath), filepath.Ext(audioPath))
	}

	// Upload the audio file
	if !opts.Quiet {
		log.Printf("Uploading %s...", audioPath)
	}

	mimeType := getMimeType(audioPath)
	uploadResult, err := c.client.Files.UploadFromPath(c.ctx, audioPath, &genai.UploadFileConfig{
		MIMEType: mimeType,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to upload audio file: %w", err)
	}

	// Ensure cleanup of the uploaded file
	defer func() {
		if _, err := c.client.Files.Delete(c.ctx, uploadResult.Name, nil); err != nil {
			logWarning("Failed to delete remote file: %v", err)
		}
	}()

	// Poll for file to be ready with timeout
	if !opts.Quiet {
		log.Print("Processing audio...")
	}

	pollCtx, cancel := context.WithTimeout(c.ctx, 2*time.Minute)
	defer cancel()

	for {
		select {
		case <-pollCtx.Done():
			return nil, fmt.Errorf("timeout waiting for file processing")
		default:
		}

		fileInfo, err := c.client.Files.Get(c.ctx, uploadResult.Name, nil)
		if err != nil {
			return nil, fmt.Errorf("failed to get file status: %w", err)
		}

		if fileInfo.State == genai.FileStateActive {
			if !opts.Quiet {
				log.Println(" ready.")
			}
			break
		} else if fileInfo.State == genai.FileStateFailed {
			return nil, fmt.Errorf("file processing failed")
		}

		if !opts.Quiet {
			fmt.Print(".")
		}
		time.Sleep(2 * time.Second)
	}

	// === PASS 1: Audio → Creative Brief (structured JSON) ===
	if !opts.Quiet {
		log.Println("Pass 1: Analyzing audio for creative brief...")
	}

	brief, briefJSON, err := c.generateAudioBrief(uploadResult.URI, mimeType, opts)
	if err != nil {
		// Check if this is a quota error - if so, fall back to OpenAI
		if strings.Contains(err.Error(), "429") || strings.Contains(err.Error(), "quota") || strings.Contains(err.Error(), "RESOURCE_EXHAUSTED") {
			logWarning("Gemini quota exceeded, falling back to OpenAI for prompt generation")
			return generatePromptWithOpenAIFallback(audioPath, opts)
		}
		return nil, fmt.Errorf("failed to generate audio brief: %w", err)
	}

	if opts.Debug {
		log.Printf("\n============================================================")
		log.Printf("DEBUG: CREATIVE BRIEF (JSON)")
		log.Printf("============================================================")
		log.Printf("%s", briefJSON)
		log.Printf("============================================================\n")
	}

	// === PASS 2: Brief → Ideogram Prompt ===
	if !opts.Quiet {
		log.Println("Pass 2: Generating Ideogram prompt from brief...")
	}

	promptText, err := c.generatePromptFromBrief(brief, opts)
	if err != nil {
		return nil, fmt.Errorf("failed to generate prompt: %w", err)
	}

	// Clean up the prompt (remove quotes, newlines, preambles)
	promptText = cleanPromptOutput(promptText)

	// === PASS 3: Second Opinion Review (OpenAI) ===
	if !opts.Quiet {
		log.Println("Pass 3: Getting second opinion from OpenAI...")
	}

	promptText, err = reviewPromptWithOpenAI(promptText, brief, opts)
	if err != nil {
		// Non-fatal - if second opinion fails, we still have the original prompt
		logWarning("Second opinion review failed: %v", err)
	}

	return &PromptResult{
		Prompt:        promptText,
		Title:         opts.Title,
		AudioFile:     audioPath,
		Style:         opts.StylePreference,
		Timestamp:     time.Now(),
		AudioAnalysis: briefJSON,
	}, nil
}

// generateAudioBrief produces a structured creative brief from audio analysis
func (c *Client) generateAudioBrief(fileURI, mimeType string, opts PromptOptions) (*AudioBrief, string, error) {
	systemInstruction := &genai.Content{
		Parts: []*genai.Part{
			{Text: `You are an audio analyst creating a creative brief for an image generator.
Output ONLY valid JSON matching this exact schema, no other text:
{
  "genre": "specific genre/subgenre",
  "bpm": 120,
  "energy": 7,
  "mood_adjectives": ["adjective1", "adjective2", "adjective3"],
	"prominent_instruments": ["instrument1", "instrument2"],
  "visual_nouns": ["concrete_noun1", "concrete_noun2", "concrete_noun3", "concrete_noun4", "concrete_noun5"],
  "textures": ["texture1", "texture2", "texture3"],
  "palette_colors": ["#hex1", "#hex2", "#hex3"],
  "central_metaphor": "One sentence describing the core visual metaphor",
  "avoid": ["cliche1", "cliche2", "cliche3"],
  "lyric_themes": "Brief summary of lyric themes if present, or empty string"
}

RULES:
- visual_nouns: 5 CONCRETE, SPECIFIC objects (not abstract concepts). NO: "ethereal wisps", "cosmic energy". YES: "brass telescope", "cracked leather journal", "rain-streaked window"
- prominent_instruments: list ONLY instruments that are clearly and prominently audible in the audio (e.g., "piano", "electric guitar", "acoustic guitar", "synth", "strings", "choir", "drums"). If unsure, use [].
- instrument realism: Do NOT include instruments as visual objects unless they are listed in prominent_instruments OR explicitly requested by user notes/title. Avoid hallucinating guitars, drums, microphones, etc.
- textures: physical materials you could touch (brushed steel, worn velvet, weathered wood)
- palette_colors: actual hex codes derived from the music's emotional color
- central_metaphor: ONE coherent visual story, not a collage
- era coherence: Visual objects/wardrobe/architecture/props MUST match the implied era/culture of the genre + production. If the music feels modern (e.g., contemporary worship/CCM, modern pop, EDM), avoid ancient/medieval/biblical props unless the user notes or lyrics explicitly demand it.
- era examples: Modern worship/CCM → keep materials and context contemporary without defaulting to a literal "worship stage" scene. Use present-day spaces/materials (modern architecture lines, contemporary typography cues, current-day clothing silhouettes, everyday objects) expressed through the song’s metaphor. Avoid explicitly ancient/biblical props like "ancient tent", "oil lantern", "scroll", "parchment", "stone tablets" unless explicitly requested.
- avoid: 3 specific visual clichés to avoid for THIS song's themes (e.g., if about struggle: "cracked earth, chains, storm clouds"; if about hope: "sunrise, dove, rainbow"; if about love: "heart shapes, red roses, intertwined hands")
- OVERUSED BIBLICAL IMAGERY (use ONLY if lyrics/title explicitly demand it): wheat field, grain, harvest table, communion table, wooden table setting, bread and wine still life, shepherd with sheep, olive branch, vineyard, dove, lions, crown of thorns, empty tomb, cross silhouette. These are valid but exhausted - find fresh visual metaphors unless the specific text absolutely requires them.
- Do NOT use: lone figure, silhouette against sky, god rays, oversized moon, portal/doorway, solitary tree, person at cliff edge, floating in space, hands reaching toward light, minimalist object on white/cream background, floating object with no environment`},
		},
	}

	userPrompt := fmt.Sprintf(`Analyze this audio and create a creative brief.
Title: %s
User notes: %s
Style preference: %s

Listen carefully and output ONLY the JSON brief.`, opts.Title, opts.Notes, opts.StylePreference)

	contents := []*genai.Content{
		{
			Role: "user",
			Parts: []*genai.Part{
				{Text: userPrompt},
				{FileData: &genai.FileData{
					FileURI:  fileURI,
					MIMEType: mimeType,
				}},
			},
		},
	}

	config := &genai.GenerateContentConfig{
		SystemInstruction: systemInstruction,
		Temperature:       ptr(float32(0.7)),
	}

	resp, err := c.client.Models.GenerateContent(c.ctx, opts.Model, contents, config)
	if err != nil {
		return nil, "", fmt.Errorf("brief generation failed: %w", err)
	}

	briefJSON := extractResponseText(resp)
	briefJSON = cleanJSONResponse(briefJSON)

	var brief AudioBrief
	if err := json.Unmarshal([]byte(briefJSON), &brief); err != nil {
		// If JSON parsing fails, return raw text for debugging
		return nil, briefJSON, fmt.Errorf("failed to parse brief JSON: %w\nRaw response: %s", err, briefJSON)
	}

	return &brief, briefJSON, nil
}

// generatePromptFromBrief creates the final Ideogram prompt from the structured brief
func (c *Client) generatePromptFromBrief(brief *AudioBrief, opts PromptOptions) (string, error) {
	styleConstraints := getStyleConstraints(opts.StylePreference)

	systemInstruction := &genai.Content{
		Parts: []*genai.Part{
			{Text: fmt.Sprintf(`You are an Ideogram prompt writer. Create ONE paragraph prompt.

STYLE: %s

OUTPUT FORMAT:
- Single paragraph, no line breaks
- No quotes around the output
- No preamble like "Here is the prompt:"
- Do not use these words: epic, ethereal, mystical, awe-inspiring, breathtaking

STRUCTURE (include in this order):
1. Text overlay (if provided) - EXACT format required
2. Subject (one primary element)
3. Scene/environment (one location)
4. Composition (camera angle, framing - avoid dead center)
5. Lighting (specific, motivated)
6. Color palette (use the provided hex colors)
7. Style/texture details

CONSTRAINTS:
- ONE focal point, ONE secondary detail only
- Prefer 2-4 interacting elements over lone subjects
- Use specific mundane details (worn paint, dented brass) over cosmic scale
- Reserve negative space behind any text
- Typography: clean, bold, high contrast, no curved/warped text`, styleConstraints)},
		},
	}

	// Build the user prompt with the brief data
	var userPrompt strings.Builder
	userPrompt.WriteString("Create an Ideogram prompt from this brief:\n\n")

	// Add text overlay requirements first
	if opts.Caption != "" && opts.Subcaption != "" {
		userPrompt.WriteString(fmt.Sprintf(`TEXT OVERLAY (START PROMPT WITH THIS EXACT FORMAT):
Title/caption "%s", subcaption "%s", is prominently displayed.

`, opts.Caption, opts.Subcaption))
	} else if opts.Caption != "" {
		userPrompt.WriteString(fmt.Sprintf(`TEXT OVERLAY (START PROMPT WITH THIS EXACT FORMAT):
Title/caption "%s" is prominently displayed.

`, opts.Caption))
	} else if opts.Subcaption != "" {
		userPrompt.WriteString(fmt.Sprintf(`TEXT OVERLAY (START PROMPT WITH THIS EXACT FORMAT):
Text "%s" is prominently displayed.

`, opts.Subcaption))
	}

	userPrompt.WriteString(fmt.Sprintf(`CREATIVE BRIEF:
- Genre: %s
- Energy: %d/10
- Mood: %s
	- Prominent instruments: %s
- Visual elements: %s
- Textures: %s
- Palette: %s
- Central metaphor: %s
- Lyric themes: %s

MUST AVOID: %s

Title context: %s
User notes: %s`,
		brief.Genre,
		brief.Energy,
		strings.Join(brief.MoodAdjectives, ", "),
		strings.Join(brief.ProminentInstruments, ", "),
		strings.Join(brief.VisualNouns, ", "),
		strings.Join(brief.Textures, ", "),
		strings.Join(brief.PaletteColors, ", "),
		brief.CentralMetaphor,
		brief.LyricThemes,
		strings.Join(brief.Avoid, ", "),
		opts.Title,
		opts.Notes,
	))

	userPrompt.WriteString("\n\nERA / CULTURAL FIT:\n- Keep props/wardrobe/architecture aligned to the genre's implied era. For modern genres (e.g., CCM live worship), prefer contemporary objects and environments; do not drift into ancient/medieval/biblical props unless explicitly indicated by user notes or prominent lyric themes.\n")

	contents := []*genai.Content{
		{
			Role: "user",
			Parts: []*genai.Part{
				{Text: userPrompt.String()},
			},
		},
	}

	config := &genai.GenerateContentConfig{
		SystemInstruction: systemInstruction,
		Temperature:       ptr(float32(0.8)),
	}

	resp, err := c.client.Models.GenerateContent(c.ctx, opts.Model, contents, config)
	if err != nil {
		return "", fmt.Errorf("prompt generation failed: %w", err)
	}

	return extractResponseText(resp), nil
}

func getStyleConstraints(style StylePreference) string {
	switch style {
	case StylePhotorealistic:
		return "PHOTOREALISTIC: Cinematic photography, real lens characteristics, shallow depth of field, film grain, natural materials, motivated practical lighting"
	case StyleArtistic:
		return "ARTISTIC: Painterly qualities, visible brush texture, stylized shapes, intentional color choices, fine art sensibility"
	case StyleAbstract:
		return "ABSTRACT: Non-literal forms, symbolic geometry, controlled negative space, color field relationships, minimal figurative elements"
	case StyleCinematic:
		return "CINEMATIC: Anamorphic lens feel, strong key light with fill, motivated practicals, dramatic composition, widescreen framing, production design focus"
	default:
		return "AUTO: Choose the most appropriate style based on the music's character. Lean toward artistic photography with intentional composition."
	}
}

// SecondOpinionResult contains the result of the OpenAI second-opinion review
type SecondOpinionResult struct {
	Approved       bool   `json:"approved"`
	ImprovedPrompt string `json:"improved_prompt,omitempty"`
	Reason         string `json:"reason,omitempty"`
}

// reviewPromptWithOpenAI gets a second opinion from OpenAI on the generated prompt
// It checks if the prompt makes sense given the audio analysis and original request
// generatePromptWithOpenAIFallback creates an image prompt using OpenAI when Gemini is unavailable
// This skips audio analysis and works only with the available metadata (title, notes, caption, subcaption)
func generatePromptWithOpenAIFallback(audioPath string, opts PromptOptions) (*PromptResult, error) {
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("OPENAI_API_KEY not set - cannot fall back to OpenAI")
	}

	if !opts.Quiet {
		log.Printf("Generating image prompt with OpenAI (no audio analysis)...")
	}

	// Build the prompt for OpenAI
	systemPrompt := `You are an Ideogram prompt writer creating image prompts for music cover art.
You do NOT have access to the audio file - work only with the provided metadata.

OUTPUT FORMAT:
- Single paragraph, no line breaks
- No quotes around the output
- No preamble like "Here is the prompt:"
- Do not use these words: epic, ethereal, mystical, awe-inspiring, breathtaking

STRUCTURE (include in this order):
1. Text overlay (if provided) - EXACT format required
2. Subject (one primary element based on title/notes)
3. Scene/environment (one location)
4. Composition (camera angle, framing - avoid dead center)
5. Lighting (specific, motivated)
6. Color palette (infer from mood/genre)
7. Style/texture details

CONSTRAINTS:
- ONE focal point, ONE secondary detail only
- Prefer 2-4 interacting elements over lone subjects
- Use specific mundane details (worn paint, dented brass) over cosmic scale
- Reserve negative space behind any text
- Typography: clean, bold, high contrast, no curved/warped text
- Do NOT use: lone figure, silhouette against sky, god rays, oversized moon, portal/doorway, solitary tree, person at cliff edge, floating in space, hands reaching toward light, minimalist object on white/cream background
- AVOID overused biblical imagery unless explicitly requested: wheat field, harvest table, communion table, bread and wine, shepherd with sheep, olive branch, vineyard, dove, lions, crown of thorns, empty tomb, cross silhouette`

	var userPrompt strings.Builder
	userPrompt.WriteString("Create an Ideogram prompt for music cover art.\n\n")

	// Add text overlay requirements first
	if opts.Caption != "" && opts.Subcaption != "" {
		userPrompt.WriteString(fmt.Sprintf(`TEXT OVERLAY (START PROMPT WITH THIS EXACT FORMAT):
Title/caption "%s", subcaption "%s", is prominently displayed.

`, opts.Caption, opts.Subcaption))
	} else if opts.Caption != "" {
		userPrompt.WriteString(fmt.Sprintf(`TEXT OVERLAY (START PROMPT WITH THIS EXACT FORMAT):
Title/caption "%s" is prominently displayed.

`, opts.Caption))
	} else if opts.Subcaption != "" {
		userPrompt.WriteString(fmt.Sprintf(`TEXT OVERLAY (START PROMPT WITH THIS EXACT FORMAT):
Text "%s" is prominently displayed.

`, opts.Subcaption))
	}

	userPrompt.WriteString(fmt.Sprintf(`AVAILABLE CONTEXT:
- Title: %s
- User notes/direction: %s
- Style preference: %s

Based on this context, create a compelling visual that would work as cover art for this music. Infer the mood, genre, and appropriate imagery from the title and notes.`,
		opts.Title,
		opts.Notes,
		opts.StylePreference,
	))

	combinedPrompt := fmt.Sprintf("%s\n\n---\n\n%s", systemPrompt, userPrompt.String())

	// Make the OpenAI API call
	requestBody := map[string]interface{}{
		"model": "gpt-5.2-pro",
		"input": []map[string]interface{}{
			{
				"role": "user",
				"content": []map[string]string{
					{"type": "input_text", "text": combinedPrompt},
				},
			},
		},
		"text": map[string]interface{}{
			"format": map[string]string{"type": "text"},
		},
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal OpenAI request: %w", err)
	}

	req, err := http.NewRequest("POST", "https://api.openai.com/v1/responses", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create OpenAI request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("OpenAI request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("OpenAI API error %d: %s", resp.StatusCode, string(body))
	}

	// Parse the responses API format
	var responsesResp struct {
		Output []struct {
			Content []struct {
				Type string `json:"type"`
				Text string `json:"text"`
			} `json:"content"`
		} `json:"output"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&responsesResp); err != nil {
		return nil, fmt.Errorf("failed to decode OpenAI response: %w", err)
	}

	// Extract text from the response
	var promptText string
	for _, output := range responsesResp.Output {
		for _, content := range output.Content {
			if content.Type == "output_text" {
				promptText = content.Text
				break
			}
		}
		if promptText != "" {
			break
		}
	}

	if promptText == "" {
		return nil, fmt.Errorf("no text response from OpenAI")
	}

	promptText = cleanPromptOutput(promptText)

	logWarning("Image prompt generated via OpenAI fallback (no audio analysis performed)")

	return &PromptResult{
		Prompt:        promptText,
		Title:         opts.Title,
		AudioFile:     audioPath,
		Style:         opts.StylePreference,
		Timestamp:     time.Now(),
		AudioAnalysis: "", // No audio analysis in fallback mode
	}, nil
}

func reviewPromptWithOpenAI(prompt string, brief *AudioBrief, opts PromptOptions) (string, error) {
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		// If no OpenAI key, skip second opinion and return original prompt
		logWarning("OPENAI_API_KEY not set, skipping second-opinion review")
		return prompt, nil
	}

	// Build the review request
	briefSummary := fmt.Sprintf(`Audio Analysis:
- Genre: %s
- Energy: %d/10
- Mood: %s
- Prominent instruments: %s
- Lyric themes: %s
- Central metaphor: %s
- Visual elements suggested: %s`,
		brief.Genre,
		brief.Energy,
		strings.Join(brief.MoodAdjectives, ", "),
		strings.Join(brief.ProminentInstruments, ", "),
		brief.LyricThemes,
		brief.CentralMetaphor,
		strings.Join(brief.VisualNouns, ", "),
	)

	requestContext := fmt.Sprintf(`Original Request:
- Title: %s
- User notes: %s
- Caption text: %s
- Subcaption text: %s
- Style preference: %s`,
		opts.Title,
		opts.Notes,
		opts.Caption,
		opts.Subcaption,
		opts.StylePreference,
	)

	systemPrompt := `You are a quality reviewer for AI image prompts. Your job is to catch prompts that would produce weird, off-putting, or inappropriate images that don't resonate with the source material.

You will receive:
1. An audio analysis (genre, mood, themes, etc.)
2. The original request context (title, notes, caption)
3. A generated image prompt

Your task: Determine if the image prompt makes intuitive sense for the audio/request, or if it's "weird" in a way that would confuse viewers.

EXAMPLES OF PROBLEMS TO CATCH:
- Abstract/surreal imagery that doesn't connect to the theme (e.g., "glass sphere hovering over desert" for a worship song about God's love)
- Jarring juxtapositions that feel random rather than meaningful
- Imagery that's technically "artistic" but emotionally disconnected from the music
- Visual metaphors that are too obscure or would require explanation
- Anything that could be unintentionally humorous, inappropriate, or offensive

AI IMAGE GENERATION LIMITATIONS - REJECT PROMPTS THAT INCLUDE:
- Fabric/cloth being torn, ripped, shattered, or pierced (AI renders this with ugly glass-like fracture effects)
- Objects penetrating or breaking through soft materials (curtains, drapes, veils, etc.)
- Any destruction/damage to textiles - AI cannot render realistic fabric tearing
- Complex physical interactions like arrows piercing cloth, hands tearing fabric, etc.
- Shattering/cracking effects on non-rigid materials
Instead, suggest alternatives: fabric billowing aside, parting naturally, being pulled back, or simply showing the object near/against the fabric without destruction

GOOD prompts:
- Have clear emotional resonance with the music's themes
- Use visual metaphors that feel intuitive (viewers "get it" without explanation)
- Match the energy/mood of the audio
- Feel cohesive rather than random
- Avoid physical interactions that AI generators handle poorly

Output ONLY valid JSON:
{
  "approved": true/false,
  "improved_prompt": "your improved version if not approved, empty string if approved",
  "reason": "brief explanation of why you approved or what was wrong"
}

If approved, improved_prompt should be empty string "".
If not approved, provide an improved prompt that fixes the issues while preserving the good elements and any required text overlays.`

	// Combine system and user prompt for the responses API
	combinedPrompt := fmt.Sprintf(`%s

---

%s

%s

Generated Image Prompt:
%s

Review this prompt. Does it make intuitive sense for this audio/request, or is it weird/disconnected? Output JSON only.`,
		systemPrompt,
		briefSummary,
		requestContext,
		prompt,
	)

	// Make the OpenAI API call using the /v1/responses endpoint for gpt-5.2-pro
	requestBody := map[string]interface{}{
		"model": "gpt-5.2-pro",
		"input": []map[string]interface{}{
			{
				"role": "user",
				"content": []map[string]string{
					{"type": "input_text", "text": combinedPrompt},
				},
			},
		},
		"text": map[string]interface{}{
			"format": map[string]string{"type": "text"},
		},
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		logWarning("Failed to marshal OpenAI request, using original prompt: %v", err)
		return prompt, nil
	}

	req, err := http.NewRequest("POST", "https://api.openai.com/v1/responses", bytes.NewBuffer(jsonData))
	if err != nil {
		logWarning("Failed to create OpenAI request, using original prompt: %v", err)
		return prompt, nil
	}

	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		logWarning("OpenAI request failed, using original prompt: %v", err)
		return prompt, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		logWarning("OpenAI API error %d: %s, using original prompt", resp.StatusCode, string(body))
		return prompt, nil
	}

	// Parse the responses API format
	var responsesResp struct {
		Output []struct {
			Content []struct {
				Type string `json:"type"`
				Text string `json:"text"`
			} `json:"content"`
		} `json:"output"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&responsesResp); err != nil {
		logWarning("Failed to decode OpenAI response, using original prompt: %v", err)
		return prompt, nil
	}

	// Extract text from the response
	var responseText string
	for _, output := range responsesResp.Output {
		for _, content := range output.Content {
			if content.Type == "output_text" {
				responseText = content.Text
				break
			}
		}
		if responseText != "" {
			break
		}
	}

	if responseText == "" {
		logWarning("No text response from OpenAI, using original prompt")
		return prompt, nil
	}

	// Parse the JSON response
	responseText = cleanJSONResponse(responseText)
	var result SecondOpinionResult
	if err := json.Unmarshal([]byte(responseText), &result); err != nil {
		logWarning("Failed to parse OpenAI review JSON, using original prompt: %v", err)
		return prompt, nil
	}

	if result.Approved {
		log.Printf("✓ Second opinion: Prompt approved - %s", result.Reason)
		return prompt, nil
	}

	// Prompt was flagged - use the improved version
	if result.ImprovedPrompt == "" {
		logWarning("Prompt flagged but no improvement provided, using original")
		return prompt, nil
	}

	log.Printf("⚡ Second opinion: Prompt improved - %s", result.Reason)
	return cleanPromptOutput(result.ImprovedPrompt), nil
}

func cleanPromptOutput(s string) string {
	s = strings.TrimSpace(s)
	// Remove surrounding quotes
	if (strings.HasPrefix(s, "\"") && strings.HasSuffix(s, "\"")) ||
		(strings.HasPrefix(s, "'") && strings.HasSuffix(s, "'")) {
		s = s[1 : len(s)-1]
	}
	// Remove common preambles
	preambles := []string{
		"Here is the prompt:",
		"Here's the prompt:",
		"Prompt:",
		"Here is your Ideogram prompt:",
	}
	for _, p := range preambles {
		if strings.HasPrefix(s, p) {
			s = strings.TrimPrefix(s, p)
			s = strings.TrimSpace(s)
		}
	}
	// Remove newlines (make it one paragraph)
	s = strings.ReplaceAll(s, "\n", " ")
	s = strings.ReplaceAll(s, "  ", " ")
	return strings.TrimSpace(s)
}

func cleanJSONResponse(s string) string {
	s = strings.TrimSpace(s)
	// Remove markdown code blocks if present
	if strings.HasPrefix(s, "```json") {
		s = strings.TrimPrefix(s, "```json")
	}
	if strings.HasPrefix(s, "```") {
		s = strings.TrimPrefix(s, "```")
	}
	if strings.HasSuffix(s, "```") {
		s = strings.TrimSuffix(s, "```")
	}
	return strings.TrimSpace(s)
}

func ptr[T any](v T) *T {
	return &v
}

func extractResponseText(resp *genai.GenerateContentResponse) string {
	if resp == nil || len(resp.Candidates) == 0 {
		return ""
	}

	var result strings.Builder
	for _, part := range resp.Candidates[0].Content.Parts {
		if part.Text != "" {
			result.WriteString(part.Text)
		}
	}
	return strings.TrimSpace(result.String())
}

func getMimeType(path string) string {
	ext := strings.ToLower(filepath.Ext(path))
	switch ext {
	case ".mp3":
		return "audio/mpeg"
	case ".wav":
		return "audio/wav"
	case ".aac":
		return "audio/aac"
	case ".flac":
		return "audio/flac"
	case ".ogg":
		return "audio/ogg"
	case ".m4a":
		return "audio/mp4"
	case ".webm":
		return "audio/webm"
	default:
		return "application/octet-stream"
	}
}

// IsAudioFile checks if a file is an audio file based on extension
func IsAudioFile(path string) bool {
	ext := strings.ToLower(filepath.Ext(path))
	audioExts := []string{".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".webm", ".wma"}
	for _, audioExt := range audioExts {
		if ext == audioExt {
			return true
		}
	}
	return false
}

// ImageValidationResult contains the result of image validation
type ImageValidationResult struct {
	IsAcceptable bool
	Score        float64 // Overall quality score 1.0-10.0
	Issues       []string
	Suggestions  []string
	Caption      string // What caption was found (if any)
	Subcaption   string // What subcaption was found (if any)
}

// PromptValidationResult contains the result of validating an image against its prompt
type PromptValidationResult struct {
	PromptMatch       bool     // Does the image match the prompt's intent?
	TextRendered      bool     // Is the text rendered correctly?
	CasingCorrect     bool     // Is the text casing as expected?
	CasingAppropriate bool     // Is the casing stylistically appropriate even if different?
	Issues            []string // List of issues found
	Suggestions       []string // Suggestions for improvement
}

// ValidateGeneratedImage is a convenience function that creates a client and validates an image
func ValidateGeneratedImage(imagePath, expectedCaption, expectedSubcaption string) (*ImageValidationResult, error) {
	ctx := context.Background()
	client, err := NewClient(ctx)
	if err != nil {
		return nil, err
	}
	return client.ValidateImage(imagePath, expectedCaption, expectedSubcaption)
}

// ValidateImageAgainstPrompt validates that a generated image matches the prompt intent
func ValidateImageAgainstPrompt(imagePath, prompt, expectedCaption, expectedSubcaption string) (*PromptValidationResult, error) {
	ctx := context.Background()
	client, err := NewClient(ctx)
	if err != nil {
		return nil, err
	}
	return client.ValidateImageAgainstPrompt(imagePath, prompt, expectedCaption, expectedSubcaption)
}

// ValidateImageAgainstPrompt validates that an image matches its generation prompt
func (c *Client) ValidateImageAgainstPrompt(imagePath, prompt, expectedCaption, expectedSubcaption string) (*PromptValidationResult, error) {
	log.Printf("Validating image against prompt with Gemini...")

	// Read the image file
	imageData, err := os.ReadFile(imagePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read image file: %w", err)
	}

	// Determine MIME type
	mimeType := getImageMimeType(imagePath)

	// Build the comprehensive validation prompt
	validationPrompt := buildPromptValidationPrompt(prompt, expectedCaption, expectedSubcaption)

	// Build the content with image
	contents := []*genai.Content{
		{
			Role: "user",
			Parts: []*genai.Part{
				{Text: validationPrompt},
				{InlineData: &genai.Blob{
					MIMEType: mimeType,
					Data:     imageData,
				}},
			},
		},
	}

	resp, err := c.client.Models.GenerateContent(c.ctx, DefaultModel, contents, nil)
	if err != nil {
		// Check if this is a quota error - if so, fall back to OpenAI
		if strings.Contains(err.Error(), "429") || strings.Contains(err.Error(), "quota") || strings.Contains(err.Error(), "RESOURCE_EXHAUSTED") {
			logWarning("Gemini quota exceeded, falling back to OpenAI for prompt validation")
			return validateImageAgainstPromptWithOpenAI(imagePath, imageData, mimeType, prompt, expectedCaption, expectedSubcaption)
		}
		return nil, fmt.Errorf("failed to validate image: %w", err)
	}

	responseText := extractResponseText(resp)
	return parsePromptValidationResponse(responseText, expectedCaption, expectedSubcaption), nil
}

func buildPromptValidationPrompt(originalPrompt, expectedCaption, expectedSubcaption string) string {
	prompt := fmt.Sprintf(`You are a quality control reviewer for AI-generated images. Analyze this image against its generation prompt and provide a detailed assessment.

ORIGINAL PROMPT:
%s

VALIDATION CRITERIA:

1. PROMPT MATCH: Does the image faithfully represent the key elements described in the prompt?
   - Check for: subject matter, style, lighting, color palette, composition, atmosphere
   - Minor creative interpretations are acceptable
   - Answer: MATCH or NO_MATCH

2. OVERALL QUALITY: Is this a well-executed image that serves its purpose?
   - Professional quality, clear subject, good composition
   - Answer: GOOD or POOR

3. INSTRUMENT CHECK (CRITICAL):
   - List ALL musical instruments visible in the image
   - Compare against instruments mentioned in the prompt
   - If ANY instrument is shown that was NOT mentioned in the prompt, this is a FAIL
   - Common hallucinated instruments to watch for: trumpet, saxophone, violin, acoustic guitar (when electric was specified), drums, microphone, piano
   - If the prompt mentions "rhythm guitar" or "electric guitar", an acoustic guitar is WRONG
   - If NO instruments were mentioned in the prompt, ANY visible instrument is a FAIL
   - Answer: INSTRUMENTS_CORRECT or INSTRUMENTS_WRONG
`, originalPrompt)

	if expectedCaption != "" || expectedSubcaption != "" {
		prompt += `
4. TEXT RENDERING:`

		if expectedCaption != "" {
			prompt += fmt.Sprintf(`
   - CAPTION: Is "%s" visible and readable?
     * Is it spelled correctly (exact or acceptable variation)?
     * Is it legible and not distorted?
     * Answer: RENDERED or MISSING or DISTORTED`, expectedCaption)
		}

		if expectedSubcaption != "" {
			prompt += fmt.Sprintf(`
   - SUBCAPTION: Is "%s" visible and readable?
     * Is it spelled correctly (exact or acceptable variation)?
     * Is it legible and not distorted?
     * Answer: RENDERED or MISSING or DISTORTED`, expectedSubcaption)
		}

		prompt += `

5. TEXT CASING:
   - Acceptable casing: exact match, ALL CAPS, or all lowercase
   - Mixed case that differs from expected is NOT acceptable
   - For example: "BETTER THAN MY BREATH" or "better than my breath" are OK for "Better Than My Breath"
   - But "Better than my Breath" is NOT OK for "Better Than My Breath"
   - Answer: EXACT_MATCH, ALL_CAPS, ALL_LOWER, or UNACCEPTABLE`
	}

	prompt += `

RESPOND IN THIS EXACT FORMAT:
PROMPT_MATCH: MATCH or NO_MATCH
QUALITY: GOOD or POOR
INSTRUMENTS_STATUS: INSTRUMENTS_CORRECT or INSTRUMENTS_WRONG
INSTRUMENTS_SEEN: [list any instruments visible in image, or "none"]`

	if expectedCaption != "" {
		prompt += `
CAPTION_STATUS: RENDERED or MISSING or DISTORTED`
	}
	if expectedSubcaption != "" {
		prompt += `
SUBCAPTION_STATUS: RENDERED or MISSING or DISTORTED`
	}
	if expectedCaption != "" || expectedSubcaption != "" {
		prompt += `
TEXT_CASING: EXACT_MATCH or ALL_CAPS or ALL_LOWER or UNACCEPTABLE`
	}

	prompt += `
ISSUES: List any specific issues found (or "None")
SUGGESTIONS: List any suggestions for improvement (or "None")

Be constructive but honest. The goal is to identify images that need regeneration.`

	return prompt
}

func parsePromptValidationResponse(response, expectedCaption, expectedSubcaption string) *PromptValidationResult {
	result := &PromptValidationResult{
		PromptMatch:       true,
		TextRendered:      true,
		CasingCorrect:     true,
		CasingAppropriate: true,
		Issues:            []string{},
		Suggestions:       []string{},
	}

	lines := strings.Split(response, "\n")
	var inIssues, inSuggestions bool

	for _, line := range lines {
		line = strings.TrimSpace(line)
		upperLine := strings.ToUpper(line)

		if strings.HasPrefix(upperLine, "PROMPT_MATCH:") {
			if strings.Contains(upperLine, "NO_MATCH") {
				result.PromptMatch = false
			}
		} else if strings.HasPrefix(upperLine, "INSTRUMENTS_STATUS:") {
			if strings.Contains(upperLine, "WRONG") {
				result.PromptMatch = false
				result.Issues = append(result.Issues, "Image contains instruments not specified in prompt")
			}
		} else if strings.HasPrefix(upperLine, "INSTRUMENTS_SEEN:") {
			instruments := strings.TrimPrefix(line, "INSTRUMENTS_SEEN:")
			instruments = strings.TrimPrefix(instruments, "Instruments_seen:")
			instruments = strings.TrimSpace(instruments)
			if instruments != "" && !strings.EqualFold(instruments, "none") && !strings.EqualFold(instruments, "[none]") {
				// Check if this was already flagged as wrong
				for _, issue := range result.Issues {
					if strings.Contains(issue, "instruments") {
						// Update the issue with specific instruments
						for i, iss := range result.Issues {
							if strings.Contains(iss, "instruments not specified") {
								result.Issues[i] = fmt.Sprintf("Hallucinated instruments in image: %s", instruments)
								break
							}
						}
						break
					}
				}
			}
		} else if strings.HasPrefix(upperLine, "CAPTION_STATUS:") || strings.HasPrefix(upperLine, "SUBCAPTION_STATUS:") {
			if strings.Contains(upperLine, "MISSING") || strings.Contains(upperLine, "DISTORTED") {
				result.TextRendered = false
			}
		} else if strings.HasPrefix(upperLine, "TEXT_CASING:") {
			if strings.Contains(upperLine, "EXACT_MATCH") || strings.Contains(upperLine, "ALL_CAPS") || strings.Contains(upperLine, "ALL_LOWER") {
				result.CasingCorrect = true
				result.CasingAppropriate = true
			} else if strings.Contains(upperLine, "UNACCEPTABLE") {
				result.CasingCorrect = false
				result.CasingAppropriate = false
			}
		} else if strings.HasPrefix(upperLine, "ISSUES:") {
			inIssues = true
			inSuggestions = false
			issueText := strings.TrimPrefix(line, "ISSUES:")
			issueText = strings.TrimPrefix(issueText, "Issues:")
			issueText = strings.TrimSpace(issueText)
			if issueText != "" && !strings.EqualFold(issueText, "None") {
				result.Issues = append(result.Issues, issueText)
			}
		} else if strings.HasPrefix(upperLine, "SUGGESTIONS:") {
			inSuggestions = true
			inIssues = false
			suggText := strings.TrimPrefix(line, "SUGGESTIONS:")
			suggText = strings.TrimPrefix(suggText, "Suggestions:")
			suggText = strings.TrimSpace(suggText)
			if suggText != "" && !strings.EqualFold(suggText, "None") {
				result.Suggestions = append(result.Suggestions, suggText)
			}
		} else if inIssues && line != "" && !strings.HasPrefix(line, "-") {
			inIssues = false
		} else if inSuggestions && line != "" && !strings.HasPrefix(line, "-") {
			inSuggestions = false
		} else if inIssues && strings.HasPrefix(line, "-") {
			issue := strings.TrimPrefix(line, "-")
			issue = strings.TrimSpace(issue)
			if issue != "" && !strings.EqualFold(issue, "None") {
				result.Issues = append(result.Issues, issue)
			}
		} else if inSuggestions && strings.HasPrefix(line, "-") {
			sugg := strings.TrimPrefix(line, "-")
			sugg = strings.TrimSpace(sugg)
			if sugg != "" && !strings.EqualFold(sugg, "None") {
				result.Suggestions = append(result.Suggestions, sugg)
			}
		}
	}

	return result
}

// TextValidationJSON is the expected JSON output structure for text validation
type TextValidationJSON struct {
	CaptionOK        bool     `json:"caption_ok"`
	SubcaptionOK     bool     `json:"subcaption_ok"`
	CaptionSeen      string   `json:"caption_seen"`
	SubcaptionSeen   string   `json:"subcaption_seen"`
	Score            float64  `json:"score"`
	Verdict          string   `json:"verdict"`
	Reason           string   `json:"reason"`
	InstrumentsSeen  []string `json:"instruments_seen"`
	InstrumentsWrong bool     `json:"instruments_wrong"`
}

// ValidateImage uses Gemini to check if the generated image has the expected text rendered correctly
func (c *Client) ValidateImage(imagePath string, expectedCaption, expectedSubcaption string) (*ImageValidationResult, error) {
	if expectedCaption == "" && expectedSubcaption == "" {
		return &ImageValidationResult{IsAcceptable: true}, nil
	}

	log.Printf("Validating generated image with Gemini...")

	imageData, err := os.ReadFile(imagePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read image file: %w", err)
	}

	mimeType := getImageMimeType(imagePath)

	// Build JSON-output validation prompt
	validationPrompt := buildJSONValidationPrompt(expectedCaption, expectedSubcaption)

	systemInstruction := &genai.Content{
		Parts: []*genai.Part{
			{Text: "You are a strict QA reviewer for AI-generated images. Output ONLY valid JSON, no other text."},
		},
	}

	contents := []*genai.Content{
		{
			Role: "user",
			Parts: []*genai.Part{
				{Text: validationPrompt},
				{InlineData: &genai.Blob{
					MIMEType: mimeType,
					Data:     imageData,
				}},
			},
		},
	}

	config := &genai.GenerateContentConfig{
		SystemInstruction: systemInstruction,
		Temperature:       ptr(float32(0.1)), // Low temperature for consistent output
	}

	resp, err := c.client.Models.GenerateContent(c.ctx, DefaultModel, contents, config)
	if err != nil {
		// Check if this is a quota error - if so, fall back to OpenAI
		if strings.Contains(err.Error(), "429") || strings.Contains(err.Error(), "quota") || strings.Contains(err.Error(), "RESOURCE_EXHAUSTED") {
			logWarning("Gemini quota exceeded, falling back to OpenAI for image validation")
			return validateImageWithOpenAI(imagePath, imageData, mimeType, expectedCaption, expectedSubcaption)
		}
		return nil, fmt.Errorf("failed to validate image: %w", err)
	}

	responseText := extractResponseText(resp)
	return parseJSONValidationResponse(responseText, expectedCaption, expectedSubcaption)
}

func buildJSONValidationPrompt(expectedCaption, expectedSubcaption string) string {
	prompt := `Examine this image and validate the text rendering.

Expected text to find:`

	hasCaption := expectedCaption != ""
	hasSubcaption := expectedSubcaption != ""

	if hasCaption {
		prompt += fmt.Sprintf(`
- Caption: "%s"`, expectedCaption)
	}
	if hasSubcaption {
		prompt += fmt.Sprintf(`
- Subcaption: "%s"`, expectedSubcaption)
	}

	prompt += `

Output ONLY this JSON (no markdown, no explanation):
{`

	if hasCaption {
		prompt += `
  "caption_ok": true/false,
  "caption_seen": "exact text you see for caption, or empty if none",`
	}
	if hasSubcaption {
		prompt += `
  "subcaption_ok": true/false,
  "subcaption_seen": "exact text you see for subcaption, or empty if none",`
	}

	prompt += `
  "score": 1.0-10.0,
  "verdict": "PASS" or "FAIL",
  "reason": "brief explanation if FAIL, or empty if PASS"
}

SCORING (score field) - evaluate how well the image meets quality standards:
- 10.0: Perfect - text correct with exact or acceptable casing, image looks professional and realistic
- 8.0-9.9: Excellent - text correct, image high quality with no major artifacts
- 6.0-7.9: Good - text readable and correctly spelled but casing differs, OR minor image quality issues
- 4.0-5.9: Fair - text has spelling errors OR noticeable visual artifacts/unrealistic elements
- 1.0-3.9: Poor - text missing/illegible OR major visual problems (AI artifacts)

IMPORTANT SCORING NOTES:
- If text is correctly SPELLED and READABLE but has wrong casing (e.g., all caps when mixed case expected), score should be 6.0-7.9, NOT lower
- Casing issues alone should NOT drop score below 6.0
- Only spelling errors, missing text, or visual artifacts should drop score below 6.0

Primary factors (in order): text spelling accuracy, visual realism, text casing.

AI GENERATION ARTIFACTS TO CHECK FOR (FAIL if present):
- Glass/crystal shatter effects on soft materials (fabric, cloth, curtains, skin)
- Fabric that looks cracked, shattered, or broken like glass instead of torn naturally
- Unrealistic material rendering (cloth behaving like rigid materials)
- Objects penetrating soft materials with hard-edge fracture patterns
- Melted, distorted, or fused body parts/objects
- Extra fingers, limbs, or body parts
- Text that appears warped, melted, or partially formed
- Unnatural lighting inconsistencies (shadows going wrong directions)
- Background elements that make no physical sense
- HALLUCINATED INSTRUMENTS: Any musical instrument (guitar, trumpet, saxophone, violin, drums, piano, etc.) that appears in the image but wasn't explicitly requested. AI generators commonly add random instruments to music-related images.

INSTRUMENT VALIDATION RULES:
- instruments_seen: List ALL musical instruments visible in the image (guitar, trumpet, piano, drums, violin, saxophone, microphone, etc.)
- instruments_wrong: true if ANY instrument is visible that was NOT in the expected list above
- If expected instruments is "NONE", then ANY visible instrument means instruments_wrong=true
- Be specific: distinguish "electric guitar" from "acoustic guitar" - they are different instruments
- Common hallucinations to watch for: trumpet, saxophone, violin appearing in rock/pop images; acoustic guitar when electric was specified

RULES:`

	if hasCaption {
		prompt += `
- caption_ok: true ONLY if the caption text is visible, correctly spelled, and legible`
	}
	if hasSubcaption {
		prompt += `
- subcaption_ok: true ONLY if the subcaption text is visible, correctly spelled, and legible`
	}

	prompt += `
- Minor stylistic differences (tilde vs hyphen) are acceptable
- Casing must match EXACTLY, OR be ALL CAPS, OR be all lowercase (these are the only acceptable casing variations)
- Mixed case that differs from the expected input is NOT acceptable (e.g., "Better than my Breath" when expecting "Better Than My Breath")
- FAIL if the image contains anything offensive or inappropriate BEYOND what was requested in the prompt (e.g., unintentional shapes resembling body parts, crude imagery, or unfortunate visual double-meanings)
- verdict: "PASS" if all expected text is rendered correctly with acceptable casing AND image is appropriate, "FAIL" otherwise`

	return prompt
}

func parseJSONValidationResponse(response, expectedCaption, expectedSubcaption string) (*ImageValidationResult, error) {
	result := &ImageValidationResult{
		IsAcceptable: true,
		Issues:       []string{},
		Suggestions:  []string{},
	}

	// Clean up response (remove markdown code blocks if present)
	response = cleanJSONResponse(response)

	var validation TextValidationJSON
	if err := json.Unmarshal([]byte(response), &validation); err != nil {
		// Fallback to old parsing method if JSON fails
		logWarning("Failed to parse validation JSON, using fallback: %v", err)
		return parseValidationResponseFallback(response, expectedCaption, expectedSubcaption), nil
	}

	// Extract score
	result.Score = validation.Score
	if result.Score < 1.0 {
		result.Score = 1.0
	} else if result.Score > 10.0 {
		result.Score = 10.0
	}

	// Check for hallucinated instruments
	if validation.InstrumentsWrong && len(validation.InstrumentsSeen) > 0 {
		result.IsAcceptable = false
		result.Issues = append(result.Issues, fmt.Sprintf("Hallucinated instruments in image: %s", strings.Join(validation.InstrumentsSeen, ", ")))
		result.Suggestions = append(result.Suggestions, "Regenerate without musical instruments or specify correct instruments in prompt")
	}

	// Populate result from JSON
	if expectedCaption != "" && !validation.CaptionOK {
		result.IsAcceptable = false
		if validation.CaptionSeen != "" {
			result.Issues = append(result.Issues, fmt.Sprintf("Caption mismatch: expected '%s', saw '%s'", expectedCaption, validation.CaptionSeen))
		} else {
			result.Issues = append(result.Issues, fmt.Sprintf("Caption '%s' not found", expectedCaption))
		}
		result.Caption = validation.CaptionSeen
	}

	if expectedSubcaption != "" && !validation.SubcaptionOK {
		result.IsAcceptable = false
		if validation.SubcaptionSeen != "" {
			result.Issues = append(result.Issues, fmt.Sprintf("Subcaption mismatch: expected '%s', saw '%s'", expectedSubcaption, validation.SubcaptionSeen))
		} else {
			result.Issues = append(result.Issues, fmt.Sprintf("Subcaption '%s' not found", expectedSubcaption))
		}
		result.Subcaption = validation.SubcaptionSeen
	}

	if validation.Verdict == "FAIL" {
		result.IsAcceptable = false
		if validation.Reason != "" && !containsIssue(result.Issues, validation.Reason) {
			result.Issues = append(result.Issues, validation.Reason)
		}
	}

	if !result.IsAcceptable {
		result.Suggestions = append(result.Suggestions, "Try regenerating with clearer text placement")
		result.Suggestions = append(result.Suggestions, "Ensure high contrast background behind text")
	}

	return result, nil
}

func containsIssue(issues []string, needle string) bool {
	for _, issue := range issues {
		if strings.Contains(issue, needle) {
			return true
		}
	}
	return false
}

func parseValidationResponseFallback(response, expectedCaption, expectedSubcaption string) *ImageValidationResult {
	result := &ImageValidationResult{
		IsAcceptable: true,
		Score:        5.0, // Default score for fallback
		Issues:       []string{},
		Suggestions:  []string{},
	}

	upperResponse := strings.ToUpper(response)

	// Check for hallucinated instruments
	if strings.Contains(upperResponse, "INSTRUMENTS_WRONG") && strings.Contains(upperResponse, "TRUE") {
		result.IsAcceptable = false
		result.Score = 4.0
		result.Issues = append(result.Issues, "Hallucinated instruments detected in image")
	}

	// Simple keyword detection as fallback
	if expectedCaption != "" {
		if strings.Contains(upperResponse, "CAPTION") && (strings.Contains(upperResponse, "NO") || strings.Contains(upperResponse, "MISSING") || strings.Contains(upperResponse, "FAIL")) {
			result.IsAcceptable = false
			result.Score = 3.0
			result.Issues = append(result.Issues, fmt.Sprintf("Caption '%s' validation failed", expectedCaption))
		}
	}

	if expectedSubcaption != "" {
		if strings.Contains(upperResponse, "SUBCAPTION") && (strings.Contains(upperResponse, "NO") || strings.Contains(upperResponse, "MISSING") || strings.Contains(upperResponse, "FAIL")) {
			result.IsAcceptable = false
			result.Score = 3.0
			result.Issues = append(result.Issues, fmt.Sprintf("Subcaption '%s' validation failed", expectedSubcaption))
		}
	}

	if strings.Contains(upperResponse, "VERDICT") && strings.Contains(upperResponse, "FAIL") {
		result.IsAcceptable = false
		result.Score = 3.0
	}

	if !result.IsAcceptable {
		result.Suggestions = append(result.Suggestions, "Try regenerating the image")
	}

	return result
}

// validateImageAgainstPromptWithOpenAI validates an image against its prompt using OpenAI when Gemini is unavailable
func validateImageAgainstPromptWithOpenAI(imagePath string, imageData []byte, mimeType, prompt, expectedCaption, expectedSubcaption string) (*PromptValidationResult, error) {
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("OPENAI_API_KEY not set - cannot fall back to OpenAI for validation")
	}

	log.Printf("Validating image against prompt with OpenAI...")

	validationPrompt := buildPromptValidationPrompt(prompt, expectedCaption, expectedSubcaption)

	// Encode image to base64
	imageBase64 := base64.StdEncoding.EncodeToString(imageData)

	// Build OpenAI request with vision
	requestBody := map[string]interface{}{
		"model": "gpt-5.2-pro",
		"messages": []map[string]interface{}{
			{
				"role": "user",
				"content": []map[string]interface{}{
					{
						"type": "text",
						"text": validationPrompt,
					},
					{
						"type": "image_url",
						"image_url": map[string]string{
							"url": fmt.Sprintf("data:%s;base64,%s", mimeType, imageBase64),
						},
					},
				},
			},
		},
		"max_tokens": 1000,
	} 

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal OpenAI request: %w", err)
	}

	req, err := http.NewRequest("POST", "https://api.openai.com/v1/chat/completions", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create OpenAI request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("OpenAI request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("OpenAI API error %d: %s", resp.StatusCode, string(body))
	}

	var chatResp struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&chatResp); err != nil {
		return nil, fmt.Errorf("failed to decode OpenAI response: %w", err)
	}

	if len(chatResp.Choices) == 0 {
		return nil, fmt.Errorf("no response from OpenAI")
	}

	responseText := chatResp.Choices[0].Message.Content
	logWarning("Image validated via OpenAI fallback")
	return parsePromptValidationResponse(responseText, expectedCaption, expectedSubcaption), nil
}

// validateImageWithOpenAI validates image text rendering using OpenAI when Gemini is unavailable
func validateImageWithOpenAI(imagePath string, imageData []byte, mimeType, expectedCaption, expectedSubcaption string) (*ImageValidationResult, error) {
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("OPENAI_API_KEY not set - cannot fall back to OpenAI for validation")
	}

	log.Printf("Validating image text with OpenAI...")

	validationPrompt := buildJSONValidationPrompt(expectedCaption, expectedSubcaption)
	systemPrompt := "You are a strict QA reviewer for AI-generated images. Output ONLY valid JSON, no other text."

	// Encode image to base64
	imageBase64 := base64.StdEncoding.EncodeToString(imageData)

	// Build OpenAI request with vision
	requestBody := map[string]interface{}{
		"model": "gpt-5.2-pro",
		"messages": []map[string]interface{}{
			{
				"role":    "system",
				"content": systemPrompt,
			},
			{
				"role": "user",
				"content": []map[string]interface{}{
					{
						"type": "text",
						"text": validationPrompt,
					},
					{
						"type": "image_url",
						"image_url": map[string]string{
							"url": fmt.Sprintf("data:%s;base64,%s", mimeType, imageBase64),
						},
					},
				},
			},
		},
		"max_tokens": 1000,
	}

	jsonData, err := json.Marshal(requestBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal OpenAI request: %w", err)
	}

	req, err := http.NewRequest("POST", "https://api.openai.com/v1/chat/completions", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create OpenAI request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("OpenAI request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("OpenAI API error %d: %s", resp.StatusCode, string(body))
	}

	var chatResp struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&chatResp); err != nil {
		return nil, fmt.Errorf("failed to decode OpenAI response: %w", err)
	}

	if len(chatResp.Choices) == 0 {
		return nil, fmt.Errorf("no response from OpenAI")
	}

	responseText := chatResp.Choices[0].Message.Content
	logWarning("Image validated via OpenAI fallback")
	return parseJSONValidationResponse(responseText, expectedCaption, expectedSubcaption)
}

func getImageMimeType(path string) string {
	ext := strings.ToLower(filepath.Ext(path))
	switch ext {
	case ".png":
		return "image/png"
	case ".jpg", ".jpeg":
		return "image/jpeg"
	case ".gif":
		return "image/gif"
	case ".webp":
		return "image/webp"
	case ".bmp":
		return "image/bmp"
	default:
		return "image/png"
	}
}

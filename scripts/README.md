# mmmeld Scripts

Helper scripts and utilities for the mmmeld multimedia video generator.

## audio_to_image_prompt.py

Analyzes audio files using Google Gemini to extract musical characteristics (tempo, mood, instrumentation, genre) and generates detailed image prompts optimized for AI image generators like Ideogram.

### Prerequisites

1. **Install the Google Generative AI SDK:**
   ```bash
   pip install google-generativeai
   ```

2. **Set up your Gemini API Key:**
   ```bash
   export GEMINI_API_KEY="your_gemini_api_key_here"
   ```
   
   Get your API key from: https://aistudio.google.com/app/api-keys

### Usage

Basic usage:
```bash
python scripts/audio_to_image_prompt.py "path/to/audio.mp3" --title "Song Title"
```

With additional context:
```bash
python scripts/audio_to_image_prompt.py "~/Google Drive/My Drive/PsalmsRemixed/psalm23.mp3" \
  --title "Psalm 23 Remix" \
  --notes "Electronic worship music with ambient textures" \
  --style artistic \
  --save
```

### Options

- `audio_file` - Path to the audio file (required)
- `--title` - Title of the track (default: "Untitled")
- `--notes` - Context notes about genre, mood, themes
- `--style` - Visual style preference: auto, photorealistic, artistic, abstract, cinematic
- `--save` - Save the prompt to a text file alongside the audio
- `--json` - Output in JSON format for programmatic use

### Examples

**Simple analysis:**
```bash
python scripts/audio_to_image_prompt.py "remix.mp3" --title "Energy Burst"
```

**With context and save:**
```bash
python scripts/audio_to_image_prompt.py "meditation.wav" \
  --title "Morning Meditation" \
  --notes "Peaceful ambient music with nature sounds" \
  --style abstract \
  --save
```

**JSON output for integration:**
```bash
python scripts/audio_to_image_prompt.py "track.mp3" --title "Track Name" --json
```

### How it Works

1. **Audio Upload:** The script uploads your audio file to Google's Gemini API
2. **Analysis:** Gemini analyzes the audio for:
   - Genre and tempo
   - Instrumentation and timbre
   - Mood and emotional atmosphere
   - Energy level and dynamics
   - Lyrical themes (if present)
3. **Prompt Generation:** Creates a detailed visual prompt using:
   - Synesthesia to map audio qualities to visual elements
   - Genre-appropriate visual motifs
   - Specific details about art style, lighting, colors, composition
4. **Cleanup:** Automatically deletes the uploaded file from Google's servers

### Visual Style Mappings

The script intelligently maps musical genres to visual styles:

- **Electronic/EDM** → Neon cities, digital landscapes, geometric patterns
- **Classical** → Grand halls, nature scenes, abstract emotional landscapes
- **Jazz** → Smoky lounges, urban nights, impressionistic scenes
- **Rock** → Raw energy, industrial elements, dramatic landscapes
- **Ambient** → Ethereal spaces, abstract flows, cosmic vistas
- **Hip-hop** → Urban environments, bold graphics, street art aesthetics

### Integration with mmmeld

This script is designed to enhance mmmeld's image generation capabilities. Future integration will allow mmmeld to:

1. Analyze audio content directly instead of just using filenames
2. Generate more contextually appropriate images
3. Support multiple image generation services (Ideogram, DALL-E, etc.)

### Troubleshooting

**"GEMINI_API_KEY environment variable not found"**
- Make sure you've set the environment variable: `export GEMINI_API_KEY="your_key"`

**"File upload failed"**
- Check your internet connection
- Verify the audio file is not corrupted
- Ensure the file format is supported (mp3, wav, aac, m4a, etc.)

**Timeout errors**
- Large audio files may take longer to process
- The script has a 600-second timeout which should handle most files

### Supported Audio Formats

- MP3
- WAV
- AAC/M4A
- FLAC
- OGG
- Most common audio formats supported by Google Gemini

### Privacy Note

The audio file is temporarily uploaded to Google's servers for analysis and is automatically deleted after processing. Be mindful of any sensitive or copyrighted content.
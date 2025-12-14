# mmmeld-go

A high-performance Go rewrite of the mmmeld multimedia tool for creating videos from audio and image/video sources with AI-powered features.

## Features

- **Text-to-Speech**: Multiple providers (ElevenLabs, OpenAI, DeepGram)
- **Image Generation**: AI-powered image creation using Ideogram v3
- **Audio-to-Image AI**: Gemini analyzes audio to generate contextually-aware image prompts
- **Text Overlay**: Add captions and subcaptions to generated images
- **Image Validation**: Gemini validates generated images and retries if text is incorrect
- **Video Processing**: Complex video sequencing with ffmpeg
- **YouTube Integration**: Download audio/video from YouTube URLs
- **Background Music**: Support for background music with volume control
- **Audio Margins**: Configurable lead-in and fade-out timing
- **Aspect Ratio Control**: Generate images in various aspect ratios (16:9, 9:16, 1:1, etc.)
- **Interactive Mode**: Command-line prompts for easy usage
- **Batch Processing**: Handle multiple images/videos in sequence

## Installation

### Prerequisites

1. **Go 1.21 or later**
2. **ffmpeg** - Must be in your system PATH
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg
   
   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

3. **yt-dlp** - For YouTube downloads
   ```bash
   # macOS
   brew install yt-dlp
   
   # Ubuntu/Debian
   sudo apt install yt-dlp
   
   # Or via pip
   pip install yt-dlp
   ```

### Build from Source

```bash
git clone <repository-url>
cd mmmeld-go
make build
```

Or manually:
```bash
go build -o bin/mmmeld ./cmd/mmmeld
go build -o bin/tts ./cmd/tts
```

### Install System-wide

```bash
make install
```

This installs binaries to `/usr/local/bin/`.

## Usage

### mmmeld - Main Video Generator

#### Basic Usage

```bash
# Interactive mode
./bin/mmmeld

# Generate video from text with AI image
./bin/mmmeld --audio generate --text "Hello world" --image generate

# Use local files
./bin/mmmeld --audio audio.mp3 --image image.jpg

# YouTube audio with local images
./bin/mmmeld --audio "https://youtube.com/watch?v=..." --image image1.jpg,image2.jpg
```

#### Command Line Options

```bash
./bin/mmmeld [options]

Audio Options:
  --audio, -a          Audio source (file, YouTube URL, or 'generate')
  --text, -t           Text for TTS generation
  --voice-id           Voice ID for TTS (default: WWr4C8ld745zI3BiA8n7)
  --tts-provider       TTS provider: elevenlabs, openai, deepgram

Image/Video Options:
  --image, -i          Image/video files, URLs, or 'generate' (comma-separated)
  --image-description  Description for AI image generation
  --analyze-audio, -aa Use Gemini to analyze audio and generate image prompt
  --audio-image-notes  Additional context/constraints for audio analysis
  --image-caption, -ic Caption text to render on the generated image
  --image-subcaption, -isc  Subcaption/subtitle text to render on the image
  --aspect-ratio, -ar  Aspect ratio for generated images (default: 16:9)
                       Options: 16:9, 9:16, 1:1, 4:3, 3:4, 3:2, 2:3

Background Music:
  --bg-music, -bm      Background music file or YouTube URL  
  --bg-music-volume    Volume (0.0-1.0, default: 0.2)

Output Options:
  --output, -o         Output video file path
  --audiomargin        Start,end margins in seconds (default: 0.5,2.0)

Behavior:
  --autofill, -af      Use defaults, no prompts
  --showprompts, -sp   Show prompts even with args provided
  --nocleanup, -nc     Keep temporary files
  --cleanup, -c        Clean temporary files (default)

API Keys:
  --openai-key         OpenAI API key
  --elevenlabs-key     ElevenLabs API key  
  --deepgram-key       DeepGram API key
  --gemini-key         Google Gemini API key
  --ideogram-key       Ideogram API key
```

#### Environment Variables

Set API keys via environment variables:

```bash
export OPENAI_API_KEY="your-openai-key"
export ELEVENLABS_API_KEY="your-elevenlabs-key"
export DEEPGRAM_API_KEY="your-deepgram-key"
export GEMINI_API_KEY="your-gemini-key"
export IDEOGRAM_API_KEY="your-ideogram-key"
```

### prompt - Standalone Audio-to-Prompt Tool

Generate image prompts from audio files using Gemini's audio analysis:

```bash
# Basic usage - analyze audio and generate prompt
./bin/prompt -file song.mp3 -title "Song Title"

# With captions for text overlay
./bin/prompt -file song.mp3 -title "Song Title" \
  -caption "Main Title" \
  -subcaption "Subtitle Text"

# With style preference
./bin/prompt -file song.mp3 -title "Song Title" -style cinematic

# With additional notes/constraints
./bin/prompt -file song.mp3 -title "Song Title" \
  -notes "exclude AI cliches like lone figures; prefer unique camera angles"

# Generate and verify image (with validation)
./bin/prompt -file song.mp3 -title "Song Title" \
  -caption "Title" -subcaption "Subtitle" \
  --verify

# Show debug output (raw audio analysis)
./bin/prompt -file song.mp3 -title "Song Title" --debug

# Specify aspect ratio
./bin/prompt -file song.mp3 -title "Song Title" -ar 1:1
```

#### prompt Options

```bash
./bin/prompt [options]

Required:
  -file, -f            Path to audio file to analyze
  -title               Title/name of the audio (provides context)

Optional:
  -notes, -n           Additional context or constraints for analysis
  -style, -s           Style preference: photorealistic, cinematic, 
                       illustrated, abstract, minimalist (default: cinematic)
  -caption, -c         Caption text for image overlay
  -subcaption, -sc     Subcaption text for image overlay
  -aspect-ratio, -ar   Aspect ratio (default: 16:9)
  --verify, -v         Generate image and validate with Gemini
  --debug              Show raw audio analysis JSON
```

### tts - Standalone Text-to-Speech

```bash
# Basic usage
./bin/tts --text "Hello world" --provider elevenlabs --voiceid WWr4C8ld745zI3BiA8n7

# From file
./bin/tts --textfile input.txt --provider openai --voiceid onyx --output speech.mp3

# From stdin
echo "Hello world" | ./bin/tts --provider deepgram --voiceid aura-zeus-en
```

## Examples

### 1. Simple Text-to-Video with AI Image

```bash
./bin/mmmeld --audio generate --text "Welcome to our presentation" --image generate --image-description "Professional presentation slide with modern design"
```

### 2. Music Video with Audio-Analyzed Image

```bash
./bin/mmmeld --audio song.mp3 \
  --image generate \
  --analyze-audio \
  --audio-image-notes "worship song; exclude AI cliches like lone figures" \
  --image-caption "Song Title" \
  --image-subcaption "Artist Name" \
  -ar 16:9 \
  -o output.mp4
```

### 3. Square Image for Social Media

```bash
./bin/mmmeld --audio track.wav \
  --image generate \
  --analyze-audio \
  --image-caption "Track Name" \
  -ar 1:1 \
  -o square_output.mp4
```

### 4. Music Video from YouTube Audio

```bash
./bin/mmmeld --audio "https://youtube.com/watch?v=dQw4w9WgXcQ" --image image1.jpg,image2.jpg,image3.jpg
```

### 5. Podcast Episode with Background Music

```bash
./bin/mmmeld --audio podcast.mp3 --image cover.jpg --bg-music background.mp3 --bg-music-volume 0.1 --audiomargin 1.0,3.0
```

### 6. Multiple Videos Sequence

```bash
./bin/mmmeld --audio narration.mp3 --image video1.mp4,image1.jpg,video2.mp4
```

### 7. Standalone Prompt Generation

```bash
# Just generate a prompt (no image)
./bin/prompt -file song.mp3 -title "My Song" -style cinematic

# Generate prompt + image + validate text rendering
./bin/prompt -file song.mp3 -title "My Song" \
  -caption "MY SONG" -subcaption "Album Name" \
  --verify
```

## Video Generation Rules

The tool follows complex sequencing rules based on whether main audio is present:

### With Main Audio
- **Total duration** = audio_duration + start_margin + end_margin
- **Images**: Displayed for entire duration or distributed equally
- **Videos**: Looped if shorter than audio, cut if longer
- **Multiple media**: Sequential playback, looped to fill audio duration

### Without Main Audio  
- **Total duration** = sum of all media durations (minimum 5 seconds)
- **Images**: 5 seconds each
- **Videos**: Play at original duration
- **Multiple media**: Sequential playback once

### Background Music
- Loops to match total duration
- Fades out during tail margin
- Volume adjustable (0.0-1.0)

## Development

### Running Tests

```bash
# All tests
make test

# With coverage
make test-coverage

# Specific package
go test ./internal/config
```

### Code Quality

```bash
# Format code
make fmt

# Run vet
make vet

# Full check (fmt + vet + test)
make check
```

### Project Structure

```
cmd/
  mmmeld/     - Main video generator
  prompt/     - Standalone audio-to-prompt tool
  tts/        - Standalone TTS tool
internal/
  config/     - Configuration and CLI parsing
  audio/      - Audio processing utilities
  video/      - Video generation (core logic)
  image/      - Image processing and Ideogram generation
  genai/      - Gemini AI integration (audio analysis, validation)
  tts/        - Text-to-speech providers
  fileutil/   - File operations and cleanup
  ffmpeg/     - FFmpeg wrapper utilities
```

## API Integration

### Text-to-Speech Providers

1. **ElevenLabs** (Default)
   - High-quality voices
   - Requires: `ELEVENLABS_API_KEY`
   - Voice ID format: `WWr4C8ld745zI3BiA8n7`

2. **OpenAI**
   - Good quality, cost-effective  
   - Requires: `OPENAI_API_KEY`
   - Voice options: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

3. **DeepGram**
   - Fast processing
   - Requires: `DEEPGRAM_API_KEY`
   - Voice format: `aura-zeus-en`

### Image Generation

- **Ideogram v3** API for high-quality image generation
- Requires: `IDEOGRAM_API_KEY`
- Supports aspect ratios: 16:9, 9:16, 1:1, 4:3, 3:4, 3:2, 2:3
- Text overlay with caption and subcaption support

### Audio Analysis (Gemini)

- **Gemini Pro** analyzes audio to generate contextual image prompts
- Requires: `GEMINI_API_KEY`
- Two-pass pipeline:
  1. **Pass A**: Audio → Structured brief (genre, mood, visual elements)
  2. **Pass B**: Brief → Optimized Ideogram prompt
- Validates generated images for correct text rendering
- Retries on validation failure (up to 3 attempts)

## Performance Considerations

- **Concurrency**: Go's goroutines enable efficient parallel processing
- **Memory**: Efficient handling of large media files
- **FFmpeg**: Hardware acceleration enabled when available
- **Temporary Files**: Automatic cleanup prevents disk bloat

## Migration from Python Version

This Go version provides:

- **Better Performance**: 5-10x faster video generation
- **Lower Memory Usage**: Efficient memory management
- **Single Binary**: No Python dependencies
- **Better Error Handling**: Clear error messages and recovery
- **Type Safety**: Compile-time validation prevents runtime errors

All command-line arguments and functionality remain compatible with the Python version.

## Troubleshooting

### Common Issues

1. **ffmpeg not found**
   ```bash
   # Verify installation
   ffmpeg -version
   # Add to PATH if needed
   ```

2. **yt-dlp errors**
   ```bash
   # Update yt-dlp
   pip install --upgrade yt-dlp
   ```

3. **API key errors**
   ```bash
   # Verify environment variables
   echo $OPENAI_API_KEY
   ```

4. **Memory issues with large files**
   - Use smaller input files
   - Ensure adequate system RAM
   - Check available disk space

### Debug Mode

Enable verbose logging:
```bash
export MMMELD_DEBUG=1
./bin/mmmeld [options]
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run `make check` 
5. Submit a pull request

## License

[Same as original Python version]

## Acknowledgments

- Original Python implementation
- ffmpeg project
- Go community for excellent tooling
- AI providers for TTS and image generation APIs
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the Go version of mmmeld.

## Commands

### Core Usage
- **Build and run interactively**: `make run-mmmeld` or `./bin/mmmeld`
- **Run with all defaults**: `./bin/mmmeld --autofill`
- **Generate TTS standalone**: `./bin/tts --text "your text" --provider elevenlabs --voiceid WWr4C8ld745zI3BiA8n7`
- **Generate image prompt from audio**: `./bin/prompt -file song.mp3 -title "Song Title"`
- **With audio analysis**: `./bin/mmmeld -a song.mp3 --image generate --analyze-audio -ic "Caption" -isc "Subcaption"`

### Development Commands
- **Build all binaries**: `make build` or `make`
- **Build specific binary**: `make build-mmmeld` or `make build-tts`
- **Run tests**: `make test`
- **Run tests with coverage**: `make test-coverage`
- **Code quality check**: `make check` (runs fmt + vet + lint + test)
- **Format code**: `make fmt`
- **Run linter**: `make vet`
- **Clean artifacts**: `make clean`
- **Install system-wide**: `make install`

### Dependencies Installation
- **Go 1.21+**: Required for building
- **ffmpeg**: Must be in PATH for video processing
- **yt-dlp**: Required for YouTube downloads

## Architecture Overview

### Project Structure
- **cmd/mmmeld/**: Main video generator application
- **cmd/prompt/**: Standalone audio-to-image-prompt tool
- **cmd/tts/**: Standalone text-to-speech tool
- **internal/config/**: Configuration and CLI argument parsing
- **internal/audio/**: Audio processing utilities
- **internal/video/**: Video generation engine (core logic)
- **internal/image/**: Image processing and Ideogram v3 generation
- **internal/genai/**: Gemini AI integration (audio analysis, image validation)
- **internal/tts/**: Multi-provider text-to-speech integration
- **internal/fileutil/**: File operations, downloads, and cleanup
- **internal/ffmpeg/**: FFmpeg wrapper utilities

### Processing Flow
1. **Config Parsing**: Parse CLI args and validate API keys
2. **Media Acquisition**: Download/generate audio and visual content
3. **Duration Calculation**: Determine video length based on audio + margins
4. **Video Sequencing**: Apply complex timing rules for visual media
5. **FFmpeg Composition**: Combine all elements into final video

### Key Differences from Python Version
- **Performance**: 5-10x faster video generation
- **Memory**: More efficient handling of large files
- **Dependencies**: Single binary, no Python runtime needed
- **Error Handling**: Better error messages and recovery
- **Concurrency**: Native goroutine support for parallel processing

## Configuration

### Environment Variables
```bash
export OPENAI_API_KEY="your-openai-key"
export ELEVENLABS_API_KEY="your-elevenlabs-key" 
export DEEPGRAM_API_KEY="your-deepgram-key"
export GEMINI_API_KEY="your-gemini-key"
export IDEOGRAM_API_KEY="your-ideogram-key"
export MMMELD_DEBUG=1  # Enable verbose logging
```

### Default Settings
- **ElevenLabs Voice**: WWr4C8ld745zI3BiA8n7
- **OpenAI Voice**: onyx
- **DeepGram Voice**: aura-zeus-en
- **Background Music Volume**: 0.2
- **Audio Margins**: 0.5s lead-in, 2.0s tail
- **Temp Directory**: temp_assets/

## Video Generation Rules (Critical Logic)

### With Main Audio Present
- Total duration = audio_duration + start_margin + end_margin
- Videos loop if shorter than audio, cut if longer
- Images display for full duration or distributed equally
- Background music loops to match duration, fades during tail

### Without Main Audio
- Duration = sum of all media (minimum 5 seconds per image)
- Videos play at original duration
- Images get 5 seconds each
- Sequential playback, no looping

### Multiple Media Handling
- Videos play first, then images
- Sequential order maintained
- Looping applied only when main audio present

## Testing Strategy

### Unit Tests
```bash
make test                 # All tests
go test ./internal/config # Specific package
make test-coverage        # With HTML coverage report
```

### Integration Testing
Use test media files in `test_media/` directory:
- Various audio formats (.mp3, .wav, .webm)
- Video files (.mp4) of different lengths
- Image files (.png, .jpg) in different aspect ratios

## API Integration

### Text-to-Speech Providers
1. **ElevenLabs**: Primary, high-quality voices
2. **OpenAI**: Cost-effective, good quality
3. **DeepGram**: Fast processing

### Image Generation
- **Ideogram v3**: Primary image generator
- **Aspect ratios**: 16:9 (default), 9:16, 1:1, 4:3, 3:4, 3:2, 2:3
- **Text overlay**: Caption and subcaption support
- **Validation**: Gemini validates text rendering, retries on failure

### Audio Analysis (Gemini)
- **Model**: gemini-3-pro-preview
- **Two-pass pipeline**:
  1. Pass A: Audio → Structured JSON brief (genre, mood, visual elements)
  2. Pass B: Brief → Optimized Ideogram prompt
- **Style preferences**: photorealistic, cinematic, illustrated, abstract, minimalist
- **AI cliché avoidance**: Built-in constraints against common AI image clichés

## Build and Deployment

### Local Development
```bash
git clone <repo-url>
cd mmmeld-go
make build    # Creates bin/mmmeld and bin/tts
make test     # Verify functionality
```

### Production Build
```bash
make check    # Full validation
make clean    # Clean artifacts
make build    # Release build
make install  # System-wide install
```

### Cross-compilation (if needed)
```bash
GOOS=linux GOARCH=amd64 go build -o bin/mmmeld-linux ./cmd/mmmeld
GOOS=windows GOARCH=amd64 go build -o bin/mmmeld.exe ./cmd/mmmeld
```

## Troubleshooting

### Build Issues
- Ensure Go 1.21+ is installed: `go version`
- Dependencies automatically fetched: `go mod tidy`
- Clean build: `make clean && make build`

### Runtime Issues
- Check PATH for ffmpeg: `ffmpeg -version`
- Verify yt-dlp: `yt-dlp --version`
- API keys set: `echo $OPENAI_API_KEY`
- Enable debug: `export MMMELD_DEBUG=1`

### Performance
- Use `--nocleanup` to inspect temp files
- Monitor memory with large files
- Check disk space for temp assets

## Migration Notes

### From Python Version
- All CLI arguments remain compatible
- Same configuration files and environment variables
- Same output quality and video generation rules
- Significantly better performance and resource usage

### Key Benefits
- **No Python runtime dependency**
- **Single binary deployment**
- **Better error messages**
- **Faster processing**
- **Lower memory footprint**
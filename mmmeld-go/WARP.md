# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

`mmmeld-go` is a high-performance Go rewrite of the Python mmmeld multimedia tool. It creates videos from audio and image/video sources with AI-powered features, optimized for platforms like YouTube. This Go version provides 5-10x better performance, lower memory usage, and single binary deployment compared to the Python version.

## Common Commands

### Build and Development
```bash
# Build all binaries
make build
# or just
make

# Build specific binary
make build-mmmeld
make build-tts

# Run with build
make run-mmmeld
make run-tts

# Development workflow
make check         # Full validation: fmt + vet + lint + test
make fmt          # Format code  
make vet          # Run go vet
make test         # Run tests
make test-coverage # Run tests with HTML coverage report

# Clean artifacts and temp files
make clean

# Install system-wide
make install      # Installs to /usr/local/bin/
```

### Core Usage Commands
```bash
# Interactive mode (recommended for first-time users)
./bin/mmmeld

# Generate video from text with AI image
./bin/mmmeld --audio generate --text "Hello world" --image generate --image-description "A futuristic scene"

# Use local files
./bin/mmmeld --audio audio.mp3 --image image.jpg,video.mp4

# YouTube audio with generated images
./bin/mmmeld --audio "https://youtube.com/watch?v=..." --image generate

# Standalone TTS utility
./bin/tts --text "Hello world" --provider elevenlabs --voiceid WWr4C8ld745zI3BiA8n7

# Run with all defaults (no prompts)
./bin/mmmeld --autofill
```

### Testing Commands
```bash
# All tests
make test

# Test specific package
go test ./internal/config
go test ./internal/video -v

# Test with coverage
make test-coverage

# Run specific test
go test -run TestConfigParsing ./internal/config
```

## Architecture Overview

### Core Pipeline Flow
1. **Config Parsing** (`internal/config/`) - CLI argument parsing, API key management, validation
2. **Media Acquisition** - Download/generate audio and visual content via specialized modules
3. **Duration Calculation** (`internal/video/`) - Determines video length based on audio + margins
4. **Visual Sequencing** - Complex timing rules for sequential/looping media playback
5. **FFmpeg Composition** - Combines all elements with audio mixing and effects

### Key Modules

**Entry Points**:
- `cmd/mmmeld/main.go` - Main video generator with interactive mode support
- `cmd/tts/main.go` - Standalone text-to-speech utility

**Core Processing**:
- `internal/video/video.go` - Video generation engine with complex duration/sequencing logic
- `internal/audio/audio.go` - Audio processing, YouTube downloads, TTS integration  
- `internal/image/image.go` - Image processing and AI generation via DALL-E
- `internal/tts/tts.go` - Multi-provider TTS (ElevenLabs, OpenAI, DeepGram)
- `internal/fileutil/fileutil.go` - File operations, downloads, cleanup management
- `internal/config/config.go` - Configuration management with extensive validation

### Critical Video Generation Logic

**Duration Rules** (in `internal/video/video.go`):
- **With Main Audio**: `total_duration = audio_duration + start_margin + end_margin`
  - Single media: loops/cuts to fit audio + margins
  - Multiple media: images get 5s each, videos share remaining time
  - All media loops to fill audio duration
- **Without Main Audio**: `total_duration = sum_of_media_durations` (min 5s per image)  
  - Sequential playback, no looping
  - Images: 5 seconds each, Videos: original duration

**Media Sequencing**:
- Videos processed first, then images
- Complex ffmpeg filter chains handle looping, trimming, scaling
- Hardware acceleration enabled when available
- Lossless intermediate files for quality preservation

**Audio Composition**:
- Main audio delayed by start margin, padded with end margin
- Background music loops to match total duration, fades during tail
- Multiple audio streams mixed with configurable volumes
- Comprehensive fade-out effects applied

## Development Patterns

### Error Handling
- Extensive error wrapping with context using `fmt.Errorf`
- ffmpeg operations include full output logging for debugging
- API failures gracefully degrade with retry logic (especially image generation)
- File validation prevents runtime crashes

### Concurrency and Performance
- Leverages Go's goroutines for efficient parallel processing
- Efficient handling of large media files with streaming
- Hardware-accelerated video processing when available
- Memory-conscious design with cleanup management

### Configuration Architecture
The config system uses a layered approach:
1. Default values in `config.New()`
2. Environment variable override in `loadAPIKeysFromEnv()`  
3. Command-line flag override in `LoadFromFlags()`
4. Extensive validation in `validate()`

### Testing Strategy
- Unit tests for config parsing, file utilities, and video calculations
- Integration testing covers various audio/visual input combinations
- Test media files should be placed in `test_media/` directory
- Coverage reports generated via `make test-coverage`

## API Integration

### Text-to-Speech Providers
All implemented in `internal/tts/tts.go`:
1. **ElevenLabs** (default): High-quality voices, requires `ELEVENLABS_API_KEY`
2. **OpenAI**: Cost-effective, requires `OPENAI_API_KEY`  
3. **DeepGram**: Fast processing, requires `DEEPGRAM_API_KEY`

### Image Generation
- **DALL-E 3**: Via OpenAI API with prompt enhancement using gpt-5.2-pro
- Automatic retry on content policy violations with safer prompts
- 1024x1024 resolution with quality optimization

## Environment Setup

### Required System Dependencies
```bash
# Go 1.21+ for building
go version

# ffmpeg must be in PATH for video/audio processing  
ffmpeg -version

# yt-dlp for YouTube downloads
yt-dlp --version
```

### Required Environment Variables
```bash
export OPENAI_API_KEY="your-key"        # For DALL-E and OpenAI TTS
export ELEVENLABS_API_KEY="your-key"    # For premium TTS
export DEEPGRAM_API_KEY="your-key"      # For alternative TTS
export MMMELD_DEBUG=1                   # Enable verbose logging
```

### Default Configuration
- **TTS Provider**: ElevenLabs with voice `WWr4C8ld745zI3BiA8n7`
- **Audio Margins**: 0.5s start, 2.0s end
- **Background Music Volume**: 0.2 (20%)
- **Temp Directory**: `temp_assets/` (auto-created, gitignored)
- **Cleanup**: Enabled by default, disable with `--nocleanup`

## Migration from Python Version

This Go implementation maintains full CLI compatibility with the Python version while providing:
- **5-10x performance improvement** in video generation
- **Single binary deployment** with no Python dependencies
- **Better error handling** with clear messages and recovery
- **Lower memory footprint** for large file processing
- **Type safety** with compile-time validation
- **Same video generation rules** and output quality

All command-line arguments, environment variables, and functionality remain compatible.

## Key Architecture Insights

### Video Processing Complexity
The `internal/video/video.go` file contains the most complex logic in the codebase, handling:
- Dynamic duration calculations based on audio presence
- Complex ffmpeg filter graph generation for sequential media
- Hardware acceleration detection and utilization
- Multi-stream audio mixing with precise timing control
- Comprehensive validation of output media

### File Management Strategy  
Implemented in `internal/fileutil/fileutil.go`:
- Centralized cleanup management prevents disk bloat
- YouTube downloads handled via yt-dlp with robust parsing
- Filename sanitization ensures cross-platform compatibility
- Automatic temp folder creation and management

### Configuration Flexibility
The config system supports:
- Multiple input methods (CLI flags, environment variables, interactive prompts)
- Extensive validation with helpful error messages  
- Provider-specific settings for TTS and image generation
- Margin and volume controls with sensible defaults

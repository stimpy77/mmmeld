# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Structure

This repository contains **mmmeld**, a multimedia tool for creating videos from audio and images with AI-powered features.

- **mmmeld-go/**: **Active development** - Go rewrite (preferred)
- **mmmeld-python/**: Legacy Python version (deprecated)
- **scripts/**: Utility scripts
- **test_media/**: Test files for development

## Primary Development: mmmeld-go

All active development should be done in the `mmmeld-go/` directory. See `mmmeld-go/CLAUDE.md` for detailed guidance.

### Quick Commands
```bash
cd mmmeld-go
make build                    # Build all binaries
./bin/mmmeld --help           # Main video generator
./bin/prompt --help           # Audio-to-prompt tool  
./bin/tts --help              # Text-to-speech tool
```

### Key Features
- **Image Generation**: Ideogram v3 API
- **Audio Analysis**: Gemini analyzes audio to generate contextual image prompts
- **Text Overlay**: Caption and subcaption support on generated images
- **Image Validation**: Gemini validates text rendering, retries on failure
- **TTS Providers**: ElevenLabs, OpenAI, DeepGram
- **Video Processing**: FFmpeg-based composition

### Environment Variables
```bash
export GEMINI_API_KEY="your-key"
export IDEOGRAM_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export ELEVENLABS_API_KEY="your-key"
export DEEPGRAM_API_KEY="your-key"
```

### Example Usage
```bash
# Generate video with AI-analyzed image from audio
./bin/mmmeld -a song.mp3 --image generate --analyze-audio \
  --image-caption "Song Title" --image-subcaption "Artist" \
  -ar 16:9 -o output.mp4

# Generate image prompt from audio (standalone)
./bin/prompt -file song.mp3 -title "Song Title" --verify
```

## Legacy: mmmeld-python

The Python version in `mmmeld-python/` is deprecated but retained for reference. Do not add new features to the Python version.
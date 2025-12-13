# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

`mmmeld` is a multimedia video generator that creates videos from audio and visual inputs. The primary purpose is to "video-ize" audio content for platforms like YouTube. The tool supports text-to-speech generation, AI-powered image creation, YouTube downloads, and complex video composition with background music and fade effects.

## Common Commands

### Setup and Installation
```bash
# Install dependencies (after installing ffmpeg system-wide)
pip install openai pillow requests tqdm pytube elevenlabs yt-dlp deepgram-sdk aiohttp

# Set up command-line access (Mac/Linux)
chmod +x setup_mmmeld.sh
./setup_mmmeld.sh

# After setup, restart terminal or source shell config
source ~/.bashrc  # or ~/.zshrc
```

### Running mmmeld
```bash
# Interactive mode (recommended for first-time users)
python mmmeld.py
# or after setup:
mmmeld

# Generate video from local audio and images
mmmeld --audio path/to/audio.mp3 --image path/to/image1.png,path/to/video1.mp4

# Text-to-speech with AI-generated image
mmmeld --audio generate --text "Hello, world!" --image generate --image-description "A futuristic cityscape"

# Use YouTube sources
mmmeld --audio https://www.youtube.com/watch?v=example --image generate --bg-music path/to/music.mp3

# Multiple TTS providers
mmmeld --audio generate --text "Hello" --tts-provider elevenlabs  # or openai, deepgram

# Standalone TTS utility
python tts.py --text "Hello world" --provider elevenlabs --voiceid WWr4C8ld745zI3BiA8n7
```

### Testing and Validation
```bash
# Run validation tests (Jupyter notebook)
jupyter notebook validation_tests.ipynb

# Quick validation test with test media
mmmeld --audio test_media/5_minutes.mp3 --image test_media/16_9.png --output test_output.mp4
```

### Debugging and Development
```bash
# Run with verbose logging
python mmmeld.py --audio generate --text "test" --image generate --nocleanup

# Check ffmpeg installation
ffmpeg -version

# Test individual components
python tts.py --text "test speech" --provider openai --voiceid alloy --output test.mp3
```

## Architecture

### Core Components

**Main Entry Point**: `mmmeld.py`
- Orchestrates the entire video generation pipeline
- Handles argument parsing and interactive prompts
- Manages temporary file cleanup

**Modular Utilities**:
- `config.py`: Argument parsing, API key management, constants
- `audio_utils.py`: Audio processing, YouTube downloads, TTS integration
- `video_utils.py`: Video composition, ffmpeg operations, duration calculations  
- `image_utils.py`: Image generation via DALL-E, image processing
- `file_utils.py`: File I/O, downloads, cleanup, path handling
- `tts_utils.py`: Text-to-speech integration (ElevenLabs, OpenAI, DeepGram)
- `tts.py`: Standalone TTS command-line utility

### Video Generation Pipeline

1. **Input Processing**: Parse audio (file/URL/TTS), images/videos (files/URLs/generated), background music
2. **Duration Calculation**: Main audio + margins OR sum of visual durations  
3. **Visual Sequence Creation**: Images (5s each), videos (original duration), sequential composition
4. **Audio Composition**: Main audio + margins, background music looping/fading
5. **Final Render**: Combine visuals and audio with proper fade-outs and margins

### Key Design Patterns

**Duration Rules**: With main audio, visuals are cut/looped to fit audio + margins. Without main audio, visual duration determines total length.

**Margin System**: Configurable lead-in (default 0.5s) and fade-out (default 2s) margins only apply when main audio exists.

**File Management**: Temporary assets stored in `temp_assets/` folder, cleaned up unless `--nocleanup` specified.

**ffmpeg Integration**: All video/audio processing uses ffmpeg with hardware acceleration, real-time output logging, and lossless intermediate files.

## Dependencies

### System Requirements
- **ffmpeg**: Must be installed and in system PATH
- **Python 3.x**: Core runtime
- **API Keys**: Set as environment variables:
  - `OPENAI_API_KEY` (for DALL-E image generation and TTS)
  - `ELEVENLABS_API_KEY` (for premium TTS)
  - `DEEPGRAM_API_KEY` (for alternative TTS)

### Python Packages
- `openai`: DALL-E image generation, GPT text processing, TTS
- `elevenlabs`: High-quality text-to-speech
- `deepgram-sdk`: Alternative TTS provider
- `yt-dlp`: YouTube media downloads
- `pillow`: Image processing
- `requests`, `aiohttp`: HTTP operations
- `tqdm`: Progress bars

## Project Structure

### Source Files
```
├── mmmeld.py          # Main application entry point
├── config.py          # Configuration and argument parsing  
├── audio_utils.py     # Audio processing and downloads
├── video_utils.py     # Video composition and ffmpeg ops
├── image_utils.py     # Image generation and processing
├── file_utils.py      # File operations and utilities
├── tts_utils.py       # Text-to-speech implementations
├── tts.py             # Standalone TTS utility
├── setup_mmmeld.sh    # Unix setup script
├── Setup-Mmmeld.ps1   # Windows setup script
└── validation_tests.ipynb  # Test scenarios and validation
```

### Supporting Files
```
├── test_media/        # Sample media files for testing
├── temp_assets/       # Temporary files (auto-created, gitignored)
└── .gitignore         # Excludes media files and temp assets
```

## Development Notes

### Video Processing Rules
Complex logic in `video_utils.py` handles various input combinations:
- Single/multiple images with/without main audio
- Single/multiple videos with different duration relationships
- Mixed image+video sequences with proper timing distribution
- Background music looping and fade-out synchronization

### Error Handling
- ffmpeg operations include comprehensive error logging
- API failures gracefully degrade (e.g., fallback to default images)
- File validation prevents runtime crashes
- Interactive prompts validate user input

### Performance Considerations
- Hardware-accelerated video processing when available
- Lossless intermediate files for quality preservation
- Real-time ffmpeg output for progress monitoring
- Efficient temporary file management

### Testing Strategy
Use `validation_tests.ipynb` for comprehensive scenario testing. The notebook covers edge cases like single images, multiple videos, margin effects, and various audio/visual combinations.

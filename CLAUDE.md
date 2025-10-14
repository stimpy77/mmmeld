# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Core Usage
- **Run mmmeld interactively**: `python mmmeld.py`
- **Run with all defaults**: `python mmmeld.py --autofill`
- **Generate TTS standalone**: `python tts.py --text "your text" --provider elevenlabs --voiceid WWr4C8ld745zI3BiA8n7`

### Common Development Commands
- **Run validation tests**: Open `validation_tests.ipynb` in Jupyter/VS Code to execute parameterized test scenarios
- **Setup command aliases** (Mac/Linux): `./setup_mmmeld.sh`
- **Setup command aliases** (Windows): `.\Setup-Mmmeld.ps1`
- **Clean temp files**: Use `--cleanup` flag (default behavior) or `--nocleanup` to preserve

### Dependencies Installation
```bash
pip install openai pillow requests tqdm pytube elevenlabs yt-dlp deepgram-sdk aiohttp pydub
```

## Architecture Overview

### Core Components
- **mmmeld.py**: Main orchestrator that coordinates all components
- **config.py**: Configuration, argument parsing, and API key management
- **audio_utils.py**: Audio source handling (local files, YouTube, TTS generation)
- **video_utils.py**: Video generation engine using ffmpeg with complex sequencing logic
- **image_utils.py**: Image processing, AI generation via DALL-E, and media downloads
- **tts_utils.py**: Multi-provider text-to-speech (ElevenLabs, OpenAI, DeepGram)
- **file_utils.py**: File operations, YouTube downloads, cleanup management

### Processing Flow
1. **Input Processing**: Parse audio/image sources (local files, URLs, or "generate")
2. **Media Acquisition**: Download from YouTube, generate via AI, or validate local files
3. **Duration Calculation**: Determine total video duration based on main audio + margins
4. **Visual Sequencing**: Create video sequence with complex timing rules
5. **Final Composition**: Combine visuals, main audio, and background music with ffmpeg

### Video Generation Rules (Critical Logic)
The application follows complex sequencing rules defined in README.md lines 216-266:

- **With main audio**: Total duration = audio_duration + lead_in + tail (default: 0.5s + 2s)
- **Without main audio**: Duration determined by visual sequence (5s per image + video durations)
- **Multiple videos**: Sequential playback, looping if needed to fill audio duration
- **Mixed media**: Videos play first, then images fill remaining time
- **Audio margins**: Only applied when main audio present; tail serves as fade-out duration

### AI Integration
- **Image Generation**: DALL-E via OpenAI API
- **Text-to-Speech**: ElevenLabs (primary), OpenAI, or DeepGram
- **Content Enhancement**: GPT for title shortening and descriptions

## Key Configuration
- **Default voice IDs**: ElevenLabs (WWr4C8ld745zI3BiA8n7), OpenAI (onyx), DeepGram (aura-zeus-en)
- **Temp folder**: `temp_assets/` (configurable)
- **Background music volume**: 0.2 (configurable)
- **Max filename length**: 100 characters

## Testing Strategy
Use `validation_tests.ipynb` for comprehensive scenario testing:
- Single/multiple images with/without audio
- Video looping and cutting scenarios
- YouTube content integration
- TTS and AI image generation
- Background music and custom margins

## Dependencies
- **ffmpeg**: Required for all video/audio processing
- **AI APIs**: OpenAI (images + TTS), ElevenLabs (TTS), DeepGram (TTS)
- **Python packages**: See requirements in README.md installation section
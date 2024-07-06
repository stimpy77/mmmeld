import argparse
import logging
import os
import sys

TEMP_ASSETS_FOLDER = "temp_assets"
MAX_FILENAME_LENGTH = 100
ELEVENLABS_VOICE_ID = "WWr4C8ld745zI3BiA8n7"
OPENAI_VOICE_ID = "onyx"
DEEPGRAM_VOICE_ID = "aura-zeus-en"
DEFAULT_BG_MUSIC_VOLUME = 0.2

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

def set_api_keys(args):
    if args.openai_key:
        os.environ["OPENAI_API_KEY"] = args.openai_key
    if args.elevenlabs_key:
        os.environ["ELEVENLABS_API_KEY"] = args.elevenlabs_key
    if args.deepgram_key:
        os.environ["DEEPGRAM_API_KEY"] = args.deepgram_key

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate a video from audio and image/video, with options for text-to-speech, image generation, and background music.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate video from local audio and multiple image/video files:
    python mmmeld.py --audio path/to/audio.mp3 --image path/to/image1.png,path/to/video1.mp4,path/to/image2.jpg

  Generate video with text-to-speech, generated image, additional images/videos, and background music:
    python mmmeld.py --audio generate --text "Hello, world!" --image generate,path/to/video1.mp4,https://example.com/image.jpg --bg-music path/to/music.mp3

  Download YouTube audio, use multiple images/videos, and add background music from YouTube:
    python mmmeld.py --audio https://www.youtube.com/watch?v=dQw4w9WgXcQ --image path/to/image1.png,https://example.com/video.mp4 --bg-music https://www.youtube.com/watch?v=background_music_id

  Generate video with specific ElevenLabs voice ID:
    python mmmeld.py --audio generate --text "Hello, world!" --voice-id your_voice_id_here

  Run interactively (no arguments):
    python mmmeld.py
        """
    )
    
    parser.add_argument("--audio", help="Path to audio file, YouTube URL, or 'generate' for text-to-speech.")
    parser.add_argument("--text", help="Text for speech generation (used if audio is 'generate').")
    parser.add_argument("--voice-id", default=ELEVENLABS_VOICE_ID, help=f"ElevenLabs voice ID. Default: {ELEVENLABS_VOICE_ID}")
    parser.add_argument("--tts-provider", choices=["elevenlabs", "openai", "deepgram"], default="elevenlabs", help="Text-to-speech provider (default: elevenlabs)")
    
    parser.add_argument("--image", help="Path to image/video file(s), URL(s), or 'generate'. Use comma-separated list for multiple inputs.")
    parser.add_argument("--image_description", help="Description for image generation (used if image is 'generate').")
    
    parser.add_argument("--bg-music", help="Path to background music file or YouTube URL.")
    parser.add_argument("--bg-music-volume", type=float, default=DEFAULT_BG_MUSIC_VOLUME, help=f"Volume of background music (0.0 to 1.0). Default: {DEFAULT_BG_MUSIC_VOLUME}")
    
    parser.add_argument("--cleanup", action="store_true", help="Clean up temporary files after video generation.")
    parser.add_argument("--autofill", action="store_true", help="Use defaults for all unspecified options, no prompts.")
    
    # Add argument group for API keys
    api_group = parser.add_argument_group('API Keys')
    api_group.add_argument("--openai-key", help="OpenAI API key. Default: Use OPENAI_API_KEY environment variable.")
    api_group.add_argument("--elevenlabs-key", help="ElevenLabs API key. Default: Use ELEVENLABS_API_KEY environment variable.")
    api_group.add_argument("--deepgram-key", help="DeepGram API key. Default: Use DEEPGRAM_API_KEY environment variable.")
    
    parser.add_argument("--output", help="Path for the output video file. Default is based on audio filename.")
    parser.add_argument("--audiomargin", default="0.5,2.0", help="Start and end audio margins in seconds, comma-separated. Default: 0.5,2.0")
    
    if len(sys.argv) == 1:
        return parser.parse_args([])  # Return empty Namespace if no args provided
    return parser.parse_args()


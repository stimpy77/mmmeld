import sys
import os
import re
from tts_utils import generate_speech
from file_utils import download_youtube_audio, get_multiline_input

import re

# Add this function at the top of the file
def is_youtube_url(url):
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    return re.match(youtube_regex, url) is not None

def get_audio_source(args, files_to_cleanup):
    audio_path = ""
    title = ""
    description = ""

    if files_to_cleanup is None:
        files_to_cleanup = []

    if args.audio:
        if args.audio == "generate":
            text = args.text or get_multiline_input("Enter the text to generate audio from (press Enter to skip): ")
            if not text:
                print("No text provided. Skipping audio generation.")
                return audio_path, title, description, files_to_cleanup
            audio_path, title, description = generate_speech(text, args.voice_id, args.tts_provider, files_to_cleanup)
        elif is_youtube_url(args.audio):
            audio_path, title, description = download_youtube_audio(args.audio, files_to_cleanup)
        else:
            audio_path = args.audio
            title = os.path.splitext(os.path.basename(audio_path))[0]
            description = ""
    else:
        audio_path = input("Enter the path to the audio file (or press Enter to generate from text): ")
        if not audio_path:
            text = get_multiline_input("Enter the text to generate audio from (press Enter to skip): ")
            if text:
                audio_path, title, description = generate_speech(text, args.voice_id, args.tts_provider, files_to_cleanup)
            else:
                print("No audio source provided. Exiting.")
                sys.exit(1)
        else:
            title = os.path.splitext(os.path.basename(audio_path))[0]
            description = ""

    return audio_path, title, description, files_to_cleanup

def get_background_music(args, files_to_cleanup):
    bg_music_path = ""
    bg_music_volume = args.bg_music_volume

    if args.bg_music:
        if is_youtube_url(args.bg_music):
            bg_music_path, _, _ = download_youtube_audio(args.bg_music, files_to_cleanup)
        else:
            bg_music_path = args.bg_music
    else:
        bg_music_path = input("Enter the path to the background music file (or press Enter to skip): ")

    return bg_music_path, bg_music_volume
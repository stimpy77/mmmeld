import sys
import os
import re
from tts_utils import generate_speech
from file_utils import download_youtube_audio, get_multiline_input
import yt_dlp
import logging
from config import TEMP_ASSETS_FOLDER 

# Add this function at the top of the file
def is_youtube_url(url):
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    return re.match(youtube_regex, url) is not None

def download_youtube_audio(url, files_to_cleanup):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(TEMP_ASSETS_FOLDER, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        output_path = ydl.prepare_filename(info)
        output_path = os.path.splitext(output_path)[0] + ".mp3"
    
    files_to_cleanup.append(output_path)
    return output_path, info.get('title', 'Unknown Title'), info.get('description', '')

def get_audio_source(args, files_to_cleanup, tts_provider):
    if args.audio == "generate":
        print(f"Getting audio source with TTS provider: {tts_provider}")
        audio_path, title, description = generate_speech(args.text, args.voice_id, args.autofill, tts_provider, files_to_cleanup)
        return audio_path, title, description, files_to_cleanup
    elif os.path.isfile(args.audio):
        return args.audio, os.path.splitext(os.path.basename(args.audio))[0], "", files_to_cleanup
    elif "youtube.com" in args.audio or "youtu.be" in args.audio:
        print("Downloading audio from YouTube...")
        audio_path, title, description = download_youtube_audio(args.audio, files_to_cleanup)
        return audio_path, title, description, files_to_cleanup
    else:
        raise ValueError("Invalid audio input")

def get_text_input():
    while True:
        file_path = input("Enter the path to a text file, or press Enter to input text directly: ")
        if not file_path:
            return get_multiline_input("Enter the text to generate audio from (press Enter twice to finish): ")
        
        try:
            with open(file_path, 'r') as file:
                return file.read()
        except IOError as e:
            print(f"Error reading text file: {e}")
            print("Please try again or press Enter to input text directly.")

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

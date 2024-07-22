#!/usr/bin/env python3

import sys
import logging
import os
import re
import math
import subprocess
from urllib.parse import urlparse
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from config import setup_logging, parse_arguments, set_api_keys
from audio_utils import get_audio_source, get_background_music
from video_utils import generate_video, get_media_duration, is_video
from image_utils import get_image_inputs, generate_image
from file_utils import (
    cleanup_files, get_default_output_path, get_multiline_input, 
    download_youtube_audio, download_image, 
    ensure_temp_folder, sanitize_filename
)
from tts_utils import generate_speech

# Constants
DEFAULT_BG_MUSIC_VOLUME = 0.2
TEMP_ASSETS_FOLDER = Path("temp_assets")

def validate_input(input_type, value):
    if input_type == "audio":
        if value.lower() == "generate" or os.path.isfile(value) or "youtube.com" in value or "youtu.be" in value:
            return True
    elif input_type == "image":
        if value.lower() == "generate" or os.path.isfile(value) or value.startswith("http"):
            return True
    return False

def get_valid_input(prompt, validator, error_message):
    while True:
        user_input = input(prompt)
        if validator(user_input):
            return user_input
        print(error_message)

def process_image_input(image_input, image_description=None, files_to_cleanup=[]):
    if image_input.lower() == 'generate':
        if not image_description:
            image_description = input("Enter a description for the image to generate (or press Enter to use default): ")
        if not image_description:
            image_description = "A visual representation of audio"
        generated_image = generate_image(image_description, "generated_image")
        if generated_image:
            files_to_cleanup.append(generated_image)
            return [generated_image]
        else:
            logging.error("Failed to generate image")
            return []
    
    image_inputs = [input.strip() for input in image_input.split(',') if input.strip()]
    
    processed_inputs = []
    
    for input in image_inputs:
        if input.lower() == 'generate':
            generated_image = generate_image(image_description or "A visual representation of audio", "generated_audio")
            if generated_image:
                files_to_cleanup.append(generated_image)
                processed_inputs.append(generated_image)
            else:
                logging.error("Failed to generate image")
        elif os.path.isfile(input):
            processed_inputs.append(input)
        elif input.startswith(('http://', 'https://')):
            if "youtube.com" in input or "youtu.be" in input:
                print(f"Downloading video from YouTube: {input}")
                downloaded_video = download_youtube_video(input, files_to_cleanup)
                if downloaded_video:
                    processed_inputs.append(downloaded_video)
                else:
                    logging.error(f"Failed to download video: {input}")
            else:
                downloaded_file = download_image(input)
                if downloaded_file:
                    processed_inputs.append(downloaded_file)
                    files_to_cleanup.append(downloaded_file)
                else:
                    logging.error(f"Failed to download: {input}")
        else:
            logging.error(f"Invalid input: {input}")
    
    return processed_inputs
    
def supports_hyperlinks():
    return sys.stdout.isatty() and 'WT_SESSION' in os.environ

def print_clickable_path(path):
    abs_path = os.path.abspath(path)
    if supports_hyperlinks():
        print(f"\033]8;;file://{abs_path}\033\\{path}\033]8;;\033\\")
    else:
        print(path)

def main():
    args = parse_arguments()
    setup_logging()
    set_api_keys(args)

    # Infer "generate" audio if text is provided
    if args.text and not args.audio:
        args.audio = "generate"

    # Infer autofill if both --audio and --image are provided
    if args.audio and args.image and not args.showprompts:
        args.autofill = True
    
    # Infer "generate" image if image description is provided but no image is provided
    if args.image_description is not None and not args.image:
        args.image = "generate"

    # Check for mutually exclusive autofill and showprompts
    if args.autofill and args.showprompts:
        print("Error: --autofill and --showprompts are mutually exclusive.")
        sys.exit(1)

    start_margin, end_margin = map(float, args.audiomargin.split(','))

    title = ""
    description = ""
    audio_path = ""
    files_to_cleanup = []

    try:
        # Ensure temp folder exists
        TEMP_ASSETS_FOLDER.mkdir(exist_ok=True)

        # Handle audio source
        if args.text:
            args.audio = 'generate'  # Force audio generation when text is provided
        if args.audio or args.text:
            # Convert relative audio path to absolute path
            if args.audio and not args.audio.lower() == 'generate':
                args.audio = os.path.abspath(args.audio)
            audio_path, title, description, files_to_cleanup = get_audio_source(args, files_to_cleanup)
        elif not args.autofill:
            audio_input = get_valid_input(
                "Enter the path to the audio file, YouTube URL, 'generate' for text-to-speech, or press Enter to skip: ",
                lambda x: not x or validate_input("audio", x),
                "Invalid input. Please try again."
            )
            if audio_input:
                if audio_input.lower() == 'generate':
                    text = get_multiline_input("Enter the text you want to convert to speech (press Enter twice to finish):")
                    if text:
                        audio_path, title, description = generate_speech(text, args.voice_id, False, args.tts_provider, files_to_cleanup)
                    else:
                        print("No text provided. Skipping audio generation.")
                elif os.path.isfile(audio_input):
                    audio_path = audio_input
                    title = os.path.splitext(os.path.basename(audio_input))[0]
                elif "youtube.com" in audio_input or "youtu.be" in audio_input:
                    print("Downloading audio from YouTube...")
                    audio_path, title, description = download_youtube_audio(audio_input)
                    files_to_cleanup.append(audio_path)
                else:
                    print("Invalid input. Please try again.")

        # Handle image/video inputs
        image_inputs = get_image_inputs(args, title, description, files_to_cleanup)
        
        # Convert relative image paths to absolute paths
        image_inputs = [os.path.abspath(path) if os.path.exists(path) else path for path in image_inputs]

        if not image_inputs:
            print("No valid image inputs provided. Using a default image.")
            default_image = generate_image("A default visual representation for audio", title)
            if default_image:
                image_inputs = [default_image]
                files_to_cleanup.append(default_image)
            else:
                print("Failed to generate a default image. Exiting.")
                sys.exit(1)

        # Handle background music
        if args.bg_music:
            bg_music_path, bg_music_volume = get_background_music(args, files_to_cleanup)
        else:
            bg_music_path = None
            bg_music_volume = args.bg_music_volume if args.bg_music_volume is not None else DEFAULT_BG_MUSIC_VOLUME

        # Handle output path
        default_output = get_default_output_path(audio_path, title, image_inputs)
        output_path = args.output or (default_output if args.autofill else 
                                      input(f"Enter the path for the output video file (press Enter for default: {default_output}): ") or default_output)

        # Ensure output_path is not in TEMP_ASSETS_FOLDER
        if Path(output_path).parent == TEMP_ASSETS_FOLDER:
            output_path = Path.cwd() / Path(output_path).name

        # Check if either audio or images/videos are provided
        if not audio_path and not image_inputs:
            print("Error: You must provide either audio or images/videos.")
            sys.exit(1)

        if generate_video(image_inputs, audio_path, bg_music_path, output_path, bg_music_volume, start_margin, end_margin, TEMP_ASSETS_FOLDER):
            print(f"Video created successfully at {output_path}")
            if audio_path:
                print(f"The length of the video is the main audio length plus {start_margin + end_margin} seconds.")
            else:
                print("The length of the video is determined by the input images and videos.")
        else:
            print("Video creation failed.")
            sys.exit(1)

        # Cleanup temporary files if not explicitly disabled
        if not args.nocleanup:
            print("Cleaning up temporary files...")
            cleanup_files(files_to_cleanup)
            if TEMP_ASSETS_FOLDER.exists():
                for file in TEMP_ASSETS_FOLDER.iterdir():
                    file.unlink()
                TEMP_ASSETS_FOLDER.rmdir()
        else:
            print("Temporary files were not cleaned up. Use --cleanup flag to remove them in future runs.")
            print("Files that would be cleaned up:")
            for file in files_to_cleanup:
                print(f"  {file}")
            for file in TEMP_ASSETS_FOLDER.iterdir():
                print(f"  {file}")
        print_clickable_path(output_path)

    except Exception as e:
        logging.exception("An error occurred during video generation")
        print(f"An error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3

import sys
import logging
from config import setup_logging, parse_arguments, set_api_keys
from audio_utils import get_audio_source
from video_utils import generate_video
from image_utils import get_image_inputs
from file_utils import cleanup_files, get_default_output_path

# Add this line
DEFAULT_BG_MUSIC_VOLUME = 0.2  # You can adjust this value as needed

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

def main():
    args = parse_arguments()
    setup_logging()
    set_api_keys(args)

    start_margin, end_margin = map(float, args.audiomargin.split(','))

    title = ""
    description = ""
    audio_path = ""
    files_to_cleanup = []

    try:
        # Handle audio source
        if args.audio or args.text:
            audio_path, title, description = get_audio_source(args, files_to_cleanup)
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
        if args.image:
            image_inputs = get_image_inputs(args, title, description, files_to_cleanup)
        else:
            image_inputs = []
            while True:
                image_input = input("Enter path/URL to image/video file, 'generate' for AI image, or press Enter to finish: ")
                if not image_input:
                    break
                new_inputs = process_image_input(image_input, description, files_to_cleanup)
                if new_inputs:
                    image_inputs.extend(new_inputs)
                else:
                    print("Invalid input. Please try again.")

        # Handle background music
        if args.bg_music:
            bg_music_path, bg_music_volume = get_background_music(args, files_to_cleanup)
        else:
            bg_music_path = None
            bg_music_volume = args.bg_music_volume if args.bg_music_volume is not None else DEFAULT_BG_MUSIC_VOLUME

        # Handle output path
        output_path = args.output or (get_default_output_path(audio_path, title, image_inputs) if args.autofill else 
                                      input(f"Enter the path for the output video file (press Enter for default: {get_default_output_path(audio_path, title, image_inputs)}): "))

        # Check if either audio or images/videos are provided
        if not audio_path and not image_inputs:
            print("Error: You must provide either audio or images/videos.")
            sys.exit(1)

        if generate_video(image_inputs, audio_path, bg_music_path, output_path, bg_music_volume, start_margin, end_margin):
            print(f"Video created successfully at {output_path}")
            if audio_path:
                print(f"The length of the video is the main audio length plus {start_margin + end_margin} seconds.")
            else:
                print("The length of the video is determined by the input images and videos.")
        else:
            print("Video creation failed.")
            sys.exit(1)

        # Cleanup temporary files if requested
        if args.cleanup:
            print("Cleaning up temporary files...")
            cleanup_files(files_to_cleanup)
        else:
            print("Temporary files were not cleaned up. Use --cleanup flag to remove them in future runs.")
            print("Files that would be cleaned up:")
            for file in files_to_cleanup:
                print(f"  {file}")

    except Exception as e:
        logging.exception("An error occurred during video generation")
        print(f"An error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
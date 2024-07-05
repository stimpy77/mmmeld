#!/usr/bin/env python3

import sys
import logging
from config import setup_logging, parse_arguments, set_api_keys
from audio_utils import get_audio_source
from video_utils import generate_video
from image_utils import get_image_inputs
from file_utils import cleanup_files, get_default_output_path

def main():
    args = parse_arguments()
    setup_logging()
    set_api_keys(args)

    title = ""
    description = ""
    audio_path = ""
    files_to_cleanup = []

    try:
        # Handle audio source
        if args.audio or args.text:
            audio_path, title, description = get_audio_source(args, files_to_cleanup)
        else:
            while not audio_path:
                audio_input = input("Enter the path to the audio file, YouTube URL, or 'generate' for text-to-speech (or press Enter to skip): ")
                if not audio_input:
                    break
                if audio_input.lower() == 'generate':
                    text = get_multiline_input("Enter the text you want to convert to speech (press Enter twice to finish):")
                    audio_path, title, description = generate_speech(text, args.voice_id, False, args.tts_provider, files_to_cleanup)
                elif os.path.isfile(audio_input):
                    audio_path, title, description = audio_input, os.path.splitext(os.path.basename(audio_input))[0], None
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
            bg_music_volume = DEFAULT_BG_MUSIC_VOLUME

        # Handle output path
        output_path = args.output or (get_default_output_path(audio_path, title) if args.autofill else 
                                      input(f"Enter the path for the output video file (press Enter for default: {get_default_output_path(audio_path, title)}): "))

        if generate_video(image_inputs, audio_path, bg_music_path, output_path, bg_music_volume):
            print(f"Video created successfully at {output_path}")
            print("The length of the video is the main audio length plus 2.5 seconds.")
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
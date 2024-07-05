import sys
from tts_utils import generate_speech
from file_utils import download_youtube_audio, get_multiline_input

def get_audio_source(args, files_to_cleanup):
    audio_path = ""
    title = ""
    description = ""

    if args.audio:
        if args.audio == "generate":
            text = args.text or get_multiline_input("Enter the text to generate audio from (press Enter to skip): ")
            if not text:
                print("No text provided. Skipping audio generation.")
                return audio_path, title, description
            audio_path, title, description = generate_speech(text, args.voice_id, args.language, args.speaker_id, files_to_cleanup)
        elif args.audio.startswith("https://www.youtube.com/"):
            audio_path, title, description = download_youtube_audio(args.audio, files_to_cleanup)
        else:
            audio_path = args.audio
            title = args.title or input(f"Enter the title for the audio file {audio_path} (press Enter to skip): ")
            description = args.description or input(f"Enter the description for the audio file {audio_path} (press Enter to skip): ")
    else:
        audio_path = input("Enter the path to the audio file (or press Enter to generate from text): ")
        if not audio_path:
            text = get_multiline_input("Enter the text to generate audio from (press Enter to skip): ")
            if text:
                audio_path, title, description = generate_speech(text, args.voice_id, args.language, args.speaker_id, files_to_cleanup)
            else:
                print("No audio source provided. Exiting.")
                sys.exit(1)
        else:
            title = args.title or input(f"Enter the title for the audio file {audio_path} (press Enter to skip): ")
            description = args.description or input(f"Enter the description for the audio file {audio_path} (press Enter to skip): ")

    return audio_path, title, description

def get_background_music(args, files_to_cleanup):
    bg_music_path = ""
    bg_music_volume = args.bg_music_volume

    if args.bg_music:
        if args.bg_music.startswith("https://www.youtube.com/"):
            bg_music_path, _, _ = download_youtube_audio(args.bg_music, files_to_cleanup)
        else:
            bg_music_path = args.bg_music
    else:
        bg_music_path = input("Enter the path to the background music file (or press Enter to skip): ")

    return bg_music_path, bg_music_volume

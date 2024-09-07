import argparse
import os
import sys
from tts_utils import generate_speech

def text_to_speech(text, provider, voice_id, output_filename=None):
    try:
        output_path, title, _ = generate_speech(text, voice_id=voice_id, tts_provider=provider, output_filename=output_filename)
        print(f"Generated speech saved to: {output_path}")
    except Exception as e:
        print(f"Error generating speech: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Text to Speech Command Line Tool")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--text', '-t', type=str, help="Text to convert to speech")
    group.add_argument('--textfile', '-tf', type=str, help="File containing text to convert to speech")
    parser.add_argument('--provider', '-p', type=str, required=True, choices=['openai', 'elevenlabs', 'deepgram'], help="TTS provider (openai, elevenlabs, deepgram)")
    parser.add_argument('--voiceid', '-v', type=str, required=True, help="Voice ID for the TTS provider")
    parser.add_argument('--output', '-o', type=str, help="Output filename or file path")
    parser.add_argument('default_textfile', nargs='?', help="Default text file to convert to speech")

    args = parser.parse_args()

    if args.text:
        text = args.text
        output_filename = args.output
    elif args.textfile:
        textfile = args.textfile
        output_filename = args.output or textfile
    elif args.default_textfile:
        textfile = args.default_textfile
        output_filename = args.output or textfile
    else:
        print("Either --text or --textfile must be provided.")
        sys.exit(1)

    if textfile:
        if not os.path.isfile(textfile):
            print(f"File not found: {textfile}")
            sys.exit(1)
        with open(textfile, 'r') as file:
            text = file.read()

    provider = args.provider.lower()
    voice_id = args.voiceid

    text_to_speech(text, provider, voice_id, output_filename)

if __name__ == "__main__":
    main()
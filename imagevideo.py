import os
import subprocess
import time
import re
import argparse
from openai import OpenAI
from PIL import Image
import requests
from io import BytesIO
from tqdm import tqdm
from yt_dlp import YoutubeDL

MAX_FILENAME_LENGTH = 100
ELEVENLABS_VOICE_ID = "WWr4C8ld745zI3BiA8n7"
DEFAULT_BG_MUSIC_VOLUME = 0.2  # 20% volume

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate a video from audio and image, with options for text-to-speech, image generation, and background music.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate video from local audio and image files:
    python imagevideo.py --audio path/to/audio.mp3 --image path/to/image.png

  Generate video with text-to-speech, generated image, and background music:
    python imagevideo.py --audio generate --text "Hello, world!" --image generate --image_description "A sunny day" --bg-music path/to/music.mp3

  Download YouTube audio, generate image, and add background music from YouTube:
    python imagevideo.py --audio https://www.youtube.com/watch?v=dQw4w9WgXcQ --image generate --bg-music https://www.youtube.com/watch?v=background_music_id

  Run interactively (no arguments):
    python imagevideo.py
        """
    )
    
    parser.add_argument("--audio", help="Path to audio file, YouTube URL, or 'generate' for text-to-speech.")
    parser.add_argument("--image", help="Path to image file or 'generate' to create one.")
    parser.add_argument("--output", help="Path for the output video file. Default is based on audio filename.")
    parser.add_argument("--text", help="Text for speech generation (used if audio is 'generate').")
    parser.add_argument("--image_description", help="Description for image generation (used if image is 'generate').")
    parser.add_argument("--bg-music", help="Path to background music file or YouTube URL.")
    parser.add_argument("--bg-music-volume", type=float, default=DEFAULT_BG_MUSIC_VOLUME,
                        help=f"Volume of background music (0.0 to 1.0). Default: {DEFAULT_BG_MUSIC_VOLUME}")
    
    # Add argument group for API keys
    api_group = parser.add_argument_group('API Keys')
    api_group.add_argument("--openai-key", help="OpenAI API key. Default: Use OPENAI_API_KEY environment variable.")
    api_group.add_argument("--elevenlabs-key", help="ElevenLabs API key. Default: Use ELEVENLABS_API_KEY environment variable.")
    
    args = parser.parse_args()

    # If no arguments are provided, print help and exit
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    return args

def get_multiline_input(prompt):
    print(prompt)
    lines = []
    while True:
        line = input()
        if line:
            lines.append(line)
        else:
            break
    return "\n".join(lines)

def generate_image_prompt(description, is_retry=False):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    system_content = "You are a helpful assistant that creates high-quality image prompts for DALL-E based on user descriptions."
    if is_retry:
        system_content += " The previous prompt violated content policy. Please create a new prompt that avoids potentially sensitive or controversial topics."
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Create a detailed, high-quality image prompt for DALL-E based on this description, and do not include any captions or text unless quotation marks are used in the description: {description}"}
        ]
    )
    return response.choices[0].message.content

def generate_image(prompt, max_retries=3):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    for attempt in range(max_retries):
        print(f"Generating image (Attempt {attempt + 1}/{max_retries})", end="", flush=True)
        start_time = time.time()
        
        try:
            response = client.images.generate(
                prompt=prompt,
                model="dall-e-3",
                n=1,
                quality="hd",
                size="1024x1024"
            )
            
            while time.time() - start_time < 60:
                print(".", end="", flush=True)
                time.sleep(0.5)
                if response is not None:
                    break
            
            if response is None:
                print("\nImage generation timed out. Retrying...")
                continue
            
            print("\nImage generated successfully!")
            
            image_url = response.data[0].url
            
            # Download and save the image
            img_response = requests.get(image_url)
            img = Image.open(BytesIO(img_response.content))
            img_path = "generated_image.png"
            img.save(img_path)
            
            return img_path
        except Exception as e:
            if "content_policy_violation" in str(e):
                print(f"\nContent policy violation. Regenerating prompt...")
                prompt = generate_image_prompt(prompt, is_retry=True)
            else:
                print(f"\nError generating image: {e}")
            
            if attempt == max_retries - 1:
                print("Max retries reached. Image generation failed.")
                return None
    
    return None

def shorten_title(title):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that shortens titles while maintaining their core meaning."},
            {"role": "user", "content": f"Shorten this title to a concise version, maintaining its core meaning and key words. The result should be suitable for use as a filename (no special characters): {title}"}
        ]
    )
    shortened_title = response.choices[0].message.content.strip()
    # Remove any remaining special characters
    shortened_title = re.sub(r'[^\w\s-]', '', shortened_title)
    # Replace spaces with underscores
    shortened_title = re.sub(r'\s+', '_', shortened_title)
    return shortened_title[:MAX_FILENAME_LENGTH]

def download_youtube_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'outtmpl': {'default': '%(title)s.%(ext)s'},
        'progress_hooks': [lambda d: print(f"Downloading: {d['_percent_str']}", end='\r')],
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info['title']
        description = info.get('description', '')
        
        if len(title) > MAX_FILENAME_LENGTH:
            title = shorten_title(title)
        
        filename = f"{title}.%(ext)s"
        ydl_opts['outtmpl']['default'] = filename
        ydl.download([url])
    
    return f"{title}.wav", title, description

def generate_speech_with_elevenlabs(text):
    print("Generating speech with ElevenLabs...")
    api_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if not api_key:
        raise ValueError("ElevenLabs API key is not set.")
    
    voice_id = input(f"Enter ElevenLabs voice ID, or press ENTER for default [{ELEVENLABS_VOICE_ID}]: ") or ELEVENLABS_VOICE_ID
    print(f"Using voice ID: {voice_id}")
    tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "Accept": "application/json",
        "xi-api-key": api_key
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }
    response = requests.post(tts_url, headers=headers, json=data, stream=True)
    if response.ok:
        title = generate_title_from_text(text)
        audio_filename = f"{title}.mp3"
        with open(audio_filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        print("Audio stream saved successfully.")
        return audio_filename, title, text
    else:
        print(response.text)
        raise Exception("Failed to generate speech with ElevenLabs.")

def generate_speech_with_openai(text):
    print("Generating speech with OpenAI...")
    title = generate_title_from_text(text)
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice="onyx",
        input=text
    )
    
    audio_filename = f"{title}.wav"
    response.stream_to_file(audio_filename)
    
    return audio_filename, title, text

def generate_speech(text):
    tts_provider = os.environ.get("TTS_PROVIDER", "elevenlabs").lower()
    
    if tts_provider == "elevenlabs":
        try:
            return generate_speech_with_elevenlabs(text)
        except Exception as e:
            print(f"ElevenLabs TTS failed: {e}")
            print("Falling back to OpenAI TTS...")
            return generate_speech_with_openai(text)
    else:
        return generate_speech_with_openai(text)

def get_audio_source():
    while True:
        audio_source = input("Enter the path to the audio file, YouTube video URL, or press Enter to generate speech: ")
        
        if not audio_source:
            text_to_speak = get_multiline_input("Enter the text you want to convert to speech (press Enter twice to finish):")
            return generate_speech(text_to_speak)
        elif os.path.isfile(audio_source):
            return audio_source, os.path.splitext(os.path.basename(audio_source))[0], None
        elif "youtube.com" in audio_source or "youtu.be" in audio_source:
            print("Downloading audio from YouTube...")
            return download_youtube_audio(audio_source)
        else:
            print("Invalid input. Please enter a valid file path, YouTube URL, or press Enter to generate speech.")

def infer_image_description(title, description=None):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    # Check if the title is short or potentially meaningless
    if len(title.split()) <= 3 and not description:
        title += " audio music"  # Add keywords for context
    
    if description:
        prompt = f"Based on the title '{title}' and description '{description}', describe an image that would be suitable for a video thumbnail or cover art for this audio content. The description should be detailed and visually rich."
    else:
        prompt = f"Based on the title or filename '{title}', describe an image that would be suitable for a video thumbnail or cover art for this audio content. The description should be detailed and visually rich."
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a creative assistant that generates detailed image descriptions based on titles and descriptions for audio content."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def generate_video(image_path, audio_path, output_path):
    # Get the dimensions of the input image
    with Image.open(image_path) as img:
        width, height = img.size

    # Set the resolution based on the image dimensions
    resolution = f"{width}x{height}"
    video_bitrate = "5M"
    audio_bitrate = "320k"
    
    ffmpeg_command = [
        "ffmpeg",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-vf", f"scale={resolution}",
        "-b:v", video_bitrate,
        "-y", output_path
    ]
    
    try:
        subprocess.run(ffmpeg_command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error generating video: {e}")
        return False

def get_default_output_path(audio_path, title=None):
    if title:
        base_name = title.replace(' ', '_')
    else:
        base_name = os.path.splitext(audio_path)[0]
    if base_name.lower().endswith('audio'):
        base_name = base_name[:-5] + 'video'
    output = f"{base_name}.mp4"
    return output

def generate_title_from_text(text):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates concise and descriptive titles for audio files based on their text content."},
            {"role": "user", "content": f"Generate a concise and descriptive title for an audio file based on this text: {text}"}
        ]
    )
    title = response.choices[0].message.content.strip()
    # Remove any special characters
    title = re.sub(r'[^\w\s-]', '', title)
    # Replace spaces with underscores
    title = re.sub(r'\s+', '_', title)
    return title[:MAX_FILENAME_LENGTH]

def get_background_music(bg_music_source):
    if os.path.isfile(bg_music_source):
        return bg_music_source
    elif "youtube.com" in bg_music_source or "youtu.be" in bg_music_source:
        print("Downloading background music from YouTube...")
        return download_youtube_audio(bg_music_source)[0]  # Return only the file path
    else:
        print("Invalid background music input. Please provide a valid file path or YouTube URL.")
        return None

def generate_video_with_background(main_audio_path, image_path, bg_music_path, output_path, bg_music_volume):
    # Get the dimensions of the input image
    with Image.open(image_path) as img:
        width, height = img.size

    # Set the resolution based on the image dimensions
    resolution = f"{width}x{height}"
    video_bitrate = "5M"
    audio_bitrate = "320k"
    
    ffmpeg_command = [
        "ffmpeg",
        "-loop", "1",
        "-i", image_path,
        "-i", main_audio_path,
        "-i", bg_music_path,
        "-filter_complex", 
        f"[1:a]aformat=fltp:44100:stereo,adelay=500|500[a1];"
        f"[2:a]aformat=fltp:44100:stereo,volume={bg_music_volume}[a2];"
        f"[a2]aloop=loop=-1:size=2e+09[a2looped];"
        f"[a1]apad=pad_dur=2[a1pad];"
        f"[a1pad][a2looped]amix=inputs=2:duration=first[amixed];"
        f"[amixed]afade=t=out:st=-2:d=2[afaded]",
        "-map", "0:v",
        "-map", "[afaded]",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-vf", f"scale={resolution}",
        "-b:v", video_bitrate,
        "-y", output_path
    ]
    
    try:
        subprocess.run(ffmpeg_command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error generating video: {e}")
        return False

def main():
    args = parse_arguments()

    # Set API keys if provided
    if args.openai_key:
        os.environ["OPENAI_API_KEY"] = args.openai_key
    if args.elevenlabs_key:
        os.environ["ELEVENLABS_API_KEY"] = args.elevenlabs_key

    # Handle audio source
    if args.audio:
        if args.audio == "generate":
            text_to_speak = args.text or get_multiline_input("Enter the text you want to convert to speech (press Enter twice to finish):")
            audio_path, title, description = generate_speech(text_to_speak)
        elif os.path.isfile(args.audio):
            audio_path, title, description = args.audio, os.path.splitext(os.path.basename(args.audio))[0], None
        elif "youtube.com" in args.audio or "youtu.be" in args.audio:
            print("Downloading audio from YouTube...")
            audio_path, title, description = download_youtube_audio(args.audio)
        else:
            print("Invalid audio input. Please provide a valid file path, YouTube URL, or 'generate'.")
            return
    else:
        audio_path, title, description = get_audio_source()

    # Handle image source
    if args.image:
        if args.image == "generate":
            user_description = args.image_description
            if not user_description:
                user_description = get_multiline_input("Please describe the image you want to generate (press Enter twice to finish, or just press Enter twice to infer from audio):")
                if not user_description:
                    print("Inferring image description from audio source...")
                    user_description = infer_image_description(title, description)
                    print(f"Inferred description: {user_description}")
            image_prompt = generate_image_prompt(user_description)
            print(f"Generated image prompt: {image_prompt}")
            image_path = generate_image(image_prompt)
        else:
            image_path = args.image
    else:
        image_path = input("Enter the path to the image (or press Enter to generate one): ")
        if not image_path:
            user_description = get_multiline_input("Please describe the image you want to generate (press Enter twice to finish, or just press Enter twice to infer from audio):")
            if not user_description:
                print("Inferring image description from audio source...")
                user_description = infer_image_description(title, description)
                print(f"Inferred description: {user_description}")
            image_prompt = generate_image_prompt(user_description)
            print(f"Generated image prompt: {image_prompt}")
            image_path = generate_image(image_prompt)

    # Handle background music
    bg_music_path = None
    if args.bg_music:
        bg_music_path = get_background_music(args.bg_music)
    else:
        bg_music_input = input("Enter the path to background music file or YouTube URL (or press Enter to skip): ")
        if bg_music_input:
            bg_music_path = get_background_music(bg_music_input)

    # Handle background music volume
    if bg_music_path:
        if args.bg_music_volume is not None:
            bg_music_volume = args.bg_music_volume
        else:
            volume_input = input(f"Enter the volume for background music (0.0 to 1.0, default {DEFAULT_BG_MUSIC_VOLUME}): ")
            bg_music_volume = float(volume_input) if volume_input else DEFAULT_BG_MUSIC_VOLUME
    else:
        bg_music_volume = None

    # Handle output path
    if args.output:
        output_path = args.output
    else:
        default_output_path = get_default_output_path(audio_path, title)
        output_path = input(f"Enter the path for the output video file (press Enter for default: {default_output_path}): ")
        if not output_path:
            output_path = default_output_path

    if bg_music_path:
        if generate_video_with_background(audio_path, image_path, bg_music_path, output_path, bg_music_volume):
            print(f"Video created successfully with background music at {output_path}")
            print("The length of the video is the main audio length plus 2.5 seconds.")
        else:
            print("Video creation failed.")
    else:
        if generate_video(image_path, audio_path, output_path):
            print(f"Video created successfully at {output_path}")
        else:
            print("Video creation failed.")

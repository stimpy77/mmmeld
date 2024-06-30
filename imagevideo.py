import os
import sys
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
from urllib.parse import urlparse

TEMP_ASSETS_FOLDER = "temp_assets"
MAX_FILENAME_LENGTH = 100
ELEVENLABS_VOICE_ID = "WWr4C8ld745zI3BiA8n7"
DEFAULT_BG_MUSIC_VOLUME = 0.2  # 20% volume

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate a video from audio and image/video, with options for text-to-speech, image generation, and background music.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate video from local audio and multiple image/video files:
    python imagevideo.py --audio path/to/audio.mp3 --image path/to/image1.png,path/to/video1.mp4,path/to/image2.jpg

  Generate video with text-to-speech, generated image, additional images/videos, and background music:
    python imagevideo.py --audio generate --text "Hello, world!" --image generate,path/to/video1.mp4,https://example.com/image.jpg --bg-music path/to/music.mp3

  Download YouTube audio, use multiple images/videos, and add background music from YouTube:
    python imagevideo.py --audio https://www.youtube.com/watch?v=dQw4w9WgXcQ --image path/to/image1.png,https://example.com/video.mp4 --bg-music https://www.youtube.com/watch?v=background_music_id

  Generate video with specific ElevenLabs voice ID:
    python imagevideo.py --audio generate --text "Hello, world!" --voice-id your_voice_id_here

  Run interactively (no arguments):
    python imagevideo.py
        """
    )
    
    parser.add_argument("--image", help="Path to image/video file(s), URL(s), or 'generate'. Use comma-separated list for multiple inputs.")
    parser.add_argument("--audio", help="Path to audio file, YouTube URL, or 'generate' for text-to-speech.")
    parser.add_argument("--output", help="Path for the output video file. Default is based on audio filename.")
    parser.add_argument("--text", help="Text for speech generation (used if audio is 'generate').")
    parser.add_argument("--image_description", help="Description for image generation (used if image is 'generate').")
    parser.add_argument("--bg-music", help="Path to background music file or YouTube URL.")
    parser.add_argument("--bg-music-volume", type=float,
                        help=f"Volume of background music (0.0 to 1.0). Default: {DEFAULT_BG_MUSIC_VOLUME}")
    parser.add_argument("--cleanup", action="store_true", help="Clean up temporary files after video generation.")
    parser.add_argument("--autofill", action="store_true", help="Use defaults for all unspecified options, no prompts.")
    parser.add_argument("--voice-id", help=f"ElevenLabs voice ID. Default: {ELEVENLABS_VOICE_ID}")
    
    # Add argument group for API keys
    api_group = parser.add_argument_group('API Keys')
    api_group.add_argument("--openai-key", help="OpenAI API key. Default: Use OPENAI_API_KEY environment variable.")
    api_group.add_argument("--elevenlabs-key", help="ElevenLabs API key. Default: Use ELEVENLABS_API_KEY environment variable.")
    
    args = parser.parse_args()
    
    # If --help is in sys.argv, print help and exit
    if "--help" in sys.argv or "-h" in sys.argv:
        parser.print_help()
        sys.exit(0)
    
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

def sanitize_filename(filename):
    # Replace any character that's not a word character, hyphen, underscore, or space with a hyphen
    sanitized = re.sub(r'[^\w\-_ ]', '-', filename)
    # Replace multiple hyphens with a single hyphen
    sanitized = re.sub(r'-+', '-', sanitized)
    # Remove leading and trailing hyphens
    sanitized = sanitized.strip('-')
    return sanitized

def generate_image_prompt(description, is_retry=False):
    client = OpenAI(api_key=os.environ.get("OPENAI_PERSONAL_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    system_content = "You are a helpful assistant that creates high-quality image prompts for DALL-E based on user descriptions."
    if len(description) < 15:
        system_content += " Always include visual elements that represent music or audio in your prompts, even if not explicitly mentioned in the description."
    if is_retry:
        system_content += " The previous prompt violated content policy. Please create a new prompt that avoids potentially sensitive or controversial topics."
    
    user_content = f"Create a detailed, high-quality image prompt for DALL-E based on this description: {description}"
    if len(description) < 15:
        user_content += " Ensure to include visual elements representing music or audio."

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]
    )
    return response.choices[0].message.content

def ensure_temp_folder():
    if not os.path.exists(TEMP_ASSETS_FOLDER):
        os.makedirs(TEMP_ASSETS_FOLDER)

def generate_image(prompt, audio_filename, max_retries=3):
    
    ensure_temp_folder()

    client = OpenAI(api_key=os.environ.get("OPENAI_PERSONAL_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    
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
            
            # Use the audio filename (without extension) for the image
            audio_name = os.path.splitext(os.path.basename(audio_filename))[0]
            img_path = os.path.join(TEMP_ASSETS_FOLDER, f"{audio_name}_image.png")
            img.save(img_path)
            print(f"Image saved: {img_path}")
            
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
    ensure_temp_folder()
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'outtmpl': {'default': os.path.join(TEMP_ASSETS_FOLDER, '%(title)s.%(ext)s')},
        'progress_hooks': [lambda d: print(f"Downloading: {d['_percent_str']}", end='\r')],
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info['title']
        description = info.get('description', '')
        
        # Sanitize the title for use as a filename
        sanitized_title = sanitize_filename(title)
        
        if len(sanitized_title) > MAX_FILENAME_LENGTH:
            sanitized_title = shorten_title(sanitized_title)
        
        filename = f"{sanitized_title}.%(ext)s"
        ydl_opts['outtmpl']['default'] = filename
        ydl.download([url])
    
    output_filename = f"{sanitized_title}.wav"
    print(f"Audio downloaded: {output_filename}")
    return output_filename, sanitized_title, description

def generate_speech_with_elevenlabs(text, voice_id=None):
    ensure_temp_folder()
    print("Generating speech with ElevenLabs...")
    api_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if not api_key:
        raise ValueError("ElevenLabs API key is not set.")
    
    if not voice_id:
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
        audio_filename = os.path.join(TEMP_ASSETS_FOLDER, f"{title}.mp3")
        with open(audio_filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        print(f"Audio generated: {audio_filename}")
        return audio_filename, title, text
    else:
        print(response.text)
        raise Exception("Failed to generate speech with ElevenLabs.")

def generate_speech_with_openai(text):
    ensure_temp_folder()
    print("Generating speech with OpenAI...")
    title = generate_title_from_text(text)
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice="onyx",
        input=text
    )
    
    audio_filename = os.path.join(TEMP_ASSETS_FOLDER, f"{title}.wav")
    response.stream_to_file(audio_filename)
    print(f"Audio generated: {audio_filename}")
    
    return audio_filename, title, text

def generate_speech(text, voice_id=None):
    tts_provider = os.environ.get("TTS_PROVIDER", "elevenlabs").lower()
    
    if tts_provider == "elevenlabs":
        try:
            return generate_speech_with_elevenlabs(text, voice_id)
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
    
    # Check if the title is short
    is_short = len(title.split()) <= 3

    if description:
        prompt = f"Based on the title '{title}' and description '{description}', describe an image that would be suitable for a video thumbnail or cover art for this audio content. The description should be detailed and visually rich."
    else:
        prompt = f"Based on the title '{title}', describe an image that would be suitable for a video thumbnail or cover art for this audio content. The description should be detailed and visually rich."

    if is_short:
        prompt += f" Since the title is short, make sure to include visual elements that represent audio or music in your description, even if not directly mentioned in the title."
    
    system_content = "You are a creative assistant that generates detailed image descriptions based on titles and descriptions for audio content."
    if is_short:
        system_content += " For short titles, always include visual elements that represent music or audio in your descriptions."

    print(" > " + prompt)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

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

def download_file(url, prefix="downloaded"):
    ensure_temp_folder()
    response = requests.get(url)
    if response.status_code == 200:
        content_type = response.headers.get('content-type')
        if 'image' in content_type:
            ext = '.jpg'
        elif 'video' in content_type:
            ext = '.mp4'
        else:
            ext = ''
        filename = os.path.join(TEMP_ASSETS_FOLDER, f"{prefix}_{os.path.basename(urlparse(url).path)}{ext}")
        with open(filename, 'wb') as f:
            f.write(response.content)
        return filename
    return None

def process_image_input(image_input):
    if image_input.lower() == 'generate':
        return [generate_image(args.image_description or "A visual representation of audio", "generated_audio")]
    
    image_inputs = image_input.split(',')
    processed_inputs = []
    
    for input in image_inputs:
        input = input.strip()
        if os.path.isfile(input):
            processed_inputs.append(input)
        elif input.startswith(('http://', 'https://')):
            downloaded_file = download_file(input)
            if downloaded_file:
                processed_inputs.append(downloaded_file)
            else:
                print(f"Failed to download: {input}")
        else:
            print(f"Invalid input: {input}")
    
    return processed_inputs

def get_image_inputs(args):
    if args.image:
        if args.image.strip() == "":
            if args.autofill:
                raise ValueError("Empty --image argument provided with --autofill. Please provide valid image input(s).")
            return []  # Will trigger interactive prompt later
        
        inputs = process_image_input(args.image)
        if not inputs:
            if args.autofill:
                raise ValueError("No valid image inputs found with --autofill. Please provide valid image input(s).")
            return []  # Will trigger interactive prompt later
        return inputs
    
    if args.autofill:
        raise ValueError("No --image argument provided with --autofill. Please provide image input(s).")
    
    inputs = []
    first_input = True
    while True:
        if first_input:
            prompt = "Enter path/URL to image/video file (press Enter to generate): "
        else:
            prompt = "Enter path/URL to additional image/video file (press Enter to finish): "
        
        file_path = input(prompt).strip()
        
        if not file_path and first_input:
            print("Generating initial image...")
            inputs.append(generate_image(args.image_description or "A visual representation of audio", "generated_audio"))
            first_input = False
        elif not file_path and not first_input:
            break
        else:
            new_inputs = process_image_input(file_path)
            if new_inputs:
                inputs.extend(new_inputs)
                first_input = False
            else:
                print("Invalid input. Please try again.")
                # Don't change first_input here, so we keep the correct prompt
    
    return inputs

def cleanup_files(files_to_remove):
    for file in files_to_remove:
        try:
            os.remove(file)
            print(f"Removed temporary file: {file}")
        except OSError as e:
            print(f"Error removing file {file}: {e}")
    
    # Note: We're not removing the temp folder, even if it's empty

def get_media_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return float(result.stdout)

def is_video(file_path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return int(result.stdout.strip()) > 0

"""
This function generate_filter_complex implements the following behavior:

- If the total duration of all videos is less than or equal to the main audio duration:
  - Videos are used at their full length without truncation.
  - Remaining time is equally distributed among images.
- If the total duration of all videos exceeds the main audio duration:
  - All inputs (both videos and images) are treated equally and their durations are adjusted to fit the main audio duration.
- If there are only videos and they fit within the main audio duration, they will effectively loop as the function will create a filter complex that uses their full durations, and the generate_video function already includes the -shortest option which will loop the video input if it's shorter than the audio.

This implementation ensures that:

- Videos are prioritized and shown in full if they fit within the main audio duration.
- Images are used to fill any remaining time if videos don't occupy the full duration.
- All inputs are treated equally if videos exceed the main audio duration.
"""
def generate_filter_complex(inputs, main_audio_duration):
    filter_complex = []
    splits = []
    current_duration = 0
    video_inputs = [input for input in inputs if is_video(input)]
    image_inputs = [input for input in inputs if not is_video(input)]
    total_video_duration = sum(get_media_duration(video) for video in video_inputs)

    if total_video_duration <= main_audio_duration:
        # Videos fit within main audio duration
        remaining_duration = main_audio_duration - total_video_duration
        image_duration = remaining_duration / max(1, len(image_inputs))
        
        for i, input_file in enumerate(inputs):
            if is_video(input_file):
                video_duration = get_media_duration(input_file)
                filter_complex.append(f"[{i}:v]setpts=PTS-STARTPTS+{current_duration}/TB[v{i}]")
                splits.append(f"[v{i}]")
                current_duration += video_duration
            else:
                filter_complex.append(f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS+{current_duration}/TB,trim=duration={image_duration}[v{i}]")
                splits.append(f"[v{i}]")
                current_duration += image_duration
    else:
        # Videos exceed main audio duration, treat all inputs equally
        input_duration = main_audio_duration / len(inputs)
        for i, input_file in enumerate(inputs):
            if is_video(input_file):
                filter_complex.append(f"[{i}:v]setpts=PTS-STARTPTS+{current_duration}/TB,trim=duration={input_duration}[v{i}]")
            else:
                filter_complex.append(f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS+{current_duration}/TB,trim=duration={input_duration}[v{i}]")
            splits.append(f"[v{i}]")
            current_duration += input_duration

    filter_complex.append(f"{''.join(splits)}concat=n={len(inputs)}:v=1:a=0[outv]")
    
    return ';'.join(filter_complex)

def generate_video(inputs, main_audio_path, bg_music_path, output_path, bg_music_volume):
    main_audio_duration = get_media_duration(main_audio_path) + 2.5  # Adding 0.5s lead-in and 2s tail

    filter_complex = generate_filter_complex(inputs, main_audio_duration)

    ffmpeg_command = [
        "ffmpeg",
        *sum([["-i", input] for input in inputs], []),
        "-i", main_audio_path
    ]

    if bg_music_path:
        ffmpeg_command.extend(["-i", bg_music_path])
        filter_complex += f";[{len(inputs)+1}:a]aloop=loop=-1:size=2e+09,volume={bg_music_volume}[bg];"
        filter_complex += f"[{len(inputs)}:a]afade=t=in:st=0:d=0.5,afade=t=out:st={main_audio_duration-2}:d=2[main];"
        filter_complex += f"[main][bg]amix=inputs=2:duration=first[aout]"
    else:
        filter_complex += f";[{len(inputs)}:a]afade=t=in:st=0:d=0.5,afade=t=out:st={main_audio_duration-2}:d=2[aout]"

    ffmpeg_command.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[aout]",
        "-t", str(main_audio_duration),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-y", output_path
    ])

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

    files_to_cleanup = []

    try:
        # Handle audio source
        if args.audio:
            if args.audio == "generate":
                if not args.text:
                    if args.autofill:
                        raise ValueError("Text for speech generation is required in autofill mode when audio is set to 'generate'.")
                    else:
                        args.text = get_multiline_input("Enter the text you want to convert to speech (press Enter twice to finish):")
                audio_path, title, description = generate_speech(args.text, args.voice_id)
                files_to_cleanup.append(audio_path)
            elif os.path.isfile(args.audio):
                audio_path, title, description = args.audio, os.path.splitext(os.path.basename(args.audio))[0], None
            elif "youtube.com" in args.audio or "youtu.be" in args.audio:
                print("Downloading audio from YouTube...")
                audio_path, title, description = download_youtube_audio(args.audio)
                files_to_cleanup.append(audio_path)
            else:
                raise ValueError("Invalid audio input. Please provide a valid file path, YouTube URL, or 'generate'.")
        elif args.text:
            audio_path, title, description = generate_speech(args.text, args.voice_id)
            files_to_cleanup.append(audio_path)
        elif not args.autofill:
            audio_path, title, description = get_audio_source()
            files_to_cleanup.append(audio_path)
        else:
            raise ValueError("Neither audio nor text for speech generation provided in autofill mode.")

        # Handle image/video inputs
        image_inputs = get_image_inputs(args)
        if not image_inputs and not args.autofill:
            raise ValueError("No valid image inputs provided.")
        files_to_cleanup.extend([f for f in image_inputs if f.startswith(os.path.abspath(TEMP_ASSETS_FOLDER))])

        # Handle background music
        bg_music_path = None
        if args.bg_music:
            bg_music_path = get_background_music(args.bg_music)
            if bg_music_path != args.bg_music:  # If it's a new file (e.g., downloaded from YouTube)
                files_to_cleanup.append(bg_music_path)
        elif not args.autofill:
            bg_music_input = input("Enter the path to background music file or YouTube URL (or press Enter to skip): ")
            if bg_music_input:
                bg_music_path = get_background_music(bg_music_input)
                if bg_music_path != bg_music_input:  # If it's a new file
                    files_to_cleanup.append(bg_music_path)

        # Handle background music volume
        if bg_music_path:
            if args.bg_music_volume is not None:
                bg_music_volume = args.bg_music_volume
            elif not args.autofill:
                volume_input = input(f"Enter the volume for background music (0.0 to 1.0, default {DEFAULT_BG_MUSIC_VOLUME}): ")
                bg_music_volume = float(volume_input) if volume_input else DEFAULT_BG_MUSIC_VOLUME
            else:
                bg_music_volume = DEFAULT_BG_MUSIC_VOLUME
        else:
            bg_music_volume = None

        # Handle output path
        if args.output:
            output_path = args.output
        elif args.autofill:
            output_path = get_default_output_path(audio_path, title)
        else:
            default_output_path = get_default_output_path(audio_path, title)
            output_path = input(f"Enter the path for the output video file (press Enter for default: {default_output_path}): ")
            if not output_path:
                output_path = default_output_path

        if generate_video(image_inputs, audio_path, bg_music_path, output_path, bg_music_volume):
            print(f"Video created successfully at {output_path}")
            print("The length of the video is the main audio length plus 2.5 seconds.")
        else:
            print("Video creation failed.")
            sys.exit(1)

        # Cleanup temporary files if requested
        if args.cleanup:
            cleanup_files(files_to_cleanup)
        elif not args.autofill:
            print("Temporary files were not cleaned up. Use --cleanup flag to remove them in future runs.")

    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

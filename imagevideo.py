import os
import sys
import subprocess
import time
import re
import argparse
from openai import OpenAI
from PIL import Image, UnidentifiedImageError
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
    # Replace any character that's not a word character, hyphen, underscore, or space with an underscore
    sanitized = re.sub(r'[^\w\-_\\\/\. ]', '_', filename)
    # Replace multiple underscores with a single underscore
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading and trailing underscores
    sanitized = sanitized.strip('_')
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

def generate_speech_with_elevenlabs(text, voice_id=None, autofill=False):
    ensure_temp_folder()
    print("Generating speech with ElevenLabs...")
    api_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if not api_key:
        raise ValueError("ElevenLabs API key is not set.")
    
    if not voice_id and not autofill:
        voice_id = input(f"Enter ElevenLabs voice ID, or press ENTER for default [{ELEVENLABS_VOICE_ID}]: ") or ELEVENLABS_VOICE_ID
    elif not voice_id:
        voice_id = ELEVENLABS_VOICE_ID
    
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

def generate_speech(text, voice_id=None, autofill=False):
    print(f"Generating speech for text:\n{text}\n")
    tts_provider = os.environ.get("TTS_PROVIDER", "elevenlabs").lower()
    
    if tts_provider == "elevenlabs":
        try:
            return generate_speech_with_elevenlabs(text, voice_id, autofill)
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

def process_image_input(image_input, image_description=None, files_to_cleanup=[]):
    if image_input.lower() == 'generate':
        generated_image = generate_image(image_description or "A visual representation of audio", "generated_audio")
        if generated_image:
            files_to_cleanup.append(generated_image)
        return [generated_image]
    
    image_inputs = [input.strip() for input in image_input.split(',') if input.strip()]
    processed_inputs = []
    
    for input in image_inputs:
        if os.path.isfile(input):
            processed_inputs.append(input)
        elif input.startswith(('http://', 'https://')):
            if "youtube.com" in input or "youtu.be" in input:
                print(f"Downloading video from YouTube: {input}")
                downloaded_video = download_youtube_video(input, files_to_cleanup)
                if downloaded_video:
                    processed_inputs.append(downloaded_video)
                else:
                    print(f"Failed to download video: {input}")
            else:
                downloaded_file = download_file(input)
                if downloaded_file:
                    processed_inputs.append(downloaded_file)
                    files_to_cleanup.append(downloaded_file)
                else:
                    print(f"Failed to download: {input}")
        else:
            print(f"Invalid input: {input}")
    
    return processed_inputs

def download_youtube_video(url, files_to_cleanup):
    ensure_temp_folder()
    ydl_opts = {
        'format': 'bestvideo[ext=webm]/bestvideo[ext=mp4]/bestvideo',  # Prefer webm or mp4, but accept any video format
        'postprocessors': [],
        'outtmpl': os.path.join(TEMP_ASSETS_FOLDER, '%(title)s.%(ext)s'),
        'progress_hooks': [lambda d: print(f"Downloading: {d['_percent_str']}", end='\r')],
        'keepvideo': True,  # Keep the video file after post-processing
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            print(f"Video downloaded: {filename}")
            
            # Add all files in TEMP_ASSETS_FOLDER that start with the base filename to cleanup list
            base_filename = os.path.splitext(os.path.basename(filename))[0]
            for file in os.listdir(TEMP_ASSETS_FOLDER):
                if file.startswith(base_filename):
                    full_path = os.path.join(TEMP_ASSETS_FOLDER, file)
                    files_to_cleanup.append(full_path)
                    print(f"Added to cleanup list: {full_path}")
            
            return filename
        except Exception as e:
            print(f"Error downloading YouTube video: {e}")
            return None
        
def get_image_inputs(args, files_to_cleanup=[]):
    if args.autofill:
        if not args.image:
            generated_image = generate_image(args.image_description or "A visual representation of audio", "generated_audio")
            if generated_image:
                files_to_cleanup.append(generated_image)
            return [generated_image]
        elif not args.image.strip():
            raise ValueError("Empty --image argument provided with --autofill. Please provide valid image input(s) or omit the argument.")
        inputs = process_image_input(args.image, args.image_description, files_to_cleanup)
        if not inputs:
            raise ValueError("No valid image inputs found with --autofill. Please provide valid image input(s).")
        return inputs
    
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
            generated_image = generate_image(args.image_description or "A visual representation of audio", "generated_audio")
            if generated_image:
                inputs.append(generated_image)
                files_to_cleanup.append(generated_image)
            first_input = False
        elif not file_path and not first_input:
            break
        else:
            new_inputs = process_image_input(file_path, args.image_description, files_to_cleanup)
            if new_inputs:
                inputs.extend(new_inputs)
                first_input = False
            else:
                print("Invalid input. Please try again.")
    
    return inputs

def cleanup_files(files_to_remove):
    print(f"Attempting to clean up {len(files_to_remove)} files:")
    for file in files_to_remove:
        try:
            if os.path.exists(file) and os.path.isfile(file):
                os.remove(file)
                print(f"Removed temporary file: {file}")
            else:
                print(f"File not found or is not a file: {file}")
        except OSError as e:
            print(f"Error removing file {file}: {e}")
    
    print(f"Cleanup completed. Temporary folder '{TEMP_ASSETS_FOLDER}' was not removed.")

def get_media_duration(file_path):
    # Check if the file is an audio file
    if file_path.endswith(('.wav', '.mp3', '.aac', '.flac', '.ogg', '.m4a')):
        return get_audio_duration(file_path)
    
    if not is_video(file_path):
        return 5.0  # Assign a default duration of 5 seconds for images
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    output = result.stdout.strip()
    print(f"get_media_duration: file_path={file_path}, output='{output}'")  # Debugging statement
    try:
        return float(output)
    except ValueError:
        print(f"Warning: Could not determine duration for file {file_path}. Using default duration of 0.")
        return 0

def get_audio_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    output = result.stdout.strip()
    print(f"get_audio_duration: file_path={file_path}, output='{output}'")  # Debugging statement
    try:
        return float(output)
    except ValueError:
        print(f"Warning: Could not determine duration for audio file {file_path}. Using default duration of 0.")
        return 0

def is_video(file_path):
    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
        return False
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    output = result.stdout.strip()
    print(f"is_video: file_path={file_path}, output='{output}'")  # Debugging statement
    if output.isdigit():
        return int(output) > 0
    return False

"""
This function below implements the following behavior:

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

def generate_video(inputs, main_audio_path, bg_music_path, output_path, bg_music_volume):
    main_audio_duration = get_media_duration(main_audio_path)
    total_duration = main_audio_duration + 2.5  # Adding 0.5s lead-in and 2s tail

    video_inputs = [input for input in inputs if is_video(input)]
    image_inputs = [input for input in inputs if not is_video(input)]

    ensure_temp_folder()
    files_to_cleanup = []

    # Determine how to handle the inputs based on their type and durations
    if len(video_inputs) == 1 and not image_inputs:
        temp_video_parts = [create_video_part(video_inputs[0], total_duration, files_to_cleanup)]
    elif len(video_inputs) > 1 and not image_inputs:
        combined_duration = sum([get_media_duration(video) for video in video_inputs])
        if combined_duration <= total_duration:
            temp_video_parts = create_looped_video_sequence(video_inputs, total_duration, files_to_cleanup)
        else:
            temp_video_parts = create_cut_video_sequence(video_inputs, total_duration, files_to_cleanup)
    elif not video_inputs and image_inputs:
        temp_video_parts = create_image_slideshow(image_inputs, total_duration, files_to_cleanup)
    else:
        temp_video_parts = create_mixed_media_sequence(video_inputs, image_inputs, total_duration, files_to_cleanup)

    # Concatenate all parts
    concat_file = os.path.join(TEMP_ASSETS_FOLDER, "concat_list.txt")
    with open(concat_file, "w") as f:
        for part in temp_video_parts:
            relative_path = os.path.relpath(part, start=TEMP_ASSETS_FOLDER)
            f.write(f"file '{relative_path}'\n")
    files_to_cleanup.append(concat_file)

    sanitized_output_path = sanitize_filename(output_path)
    if not sanitized_output_path.lower().endswith('.mp4'):
        sanitized_output_path += '.mp4'

    # Add the main audio to the final video with silence margins and visual fade out
    final_command = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
        "-i", main_audio_path,
        "-vf", f"fade=t=out:st={total_duration-2}:d=2",
        "-af", "adelay=500|500,apad=pad_dur=2",
        "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
        "-shortest", sanitized_output_path
    ]
    subprocess.run(final_command, check=True)

    # Clean up temporary files
    for part in files_to_cleanup:
        os.remove(part)

    return True

def create_video_part(video_path, duration, files_to_cleanup):
    temp_output = os.path.join(TEMP_ASSETS_FOLDER, sanitize_filename(f"temp_{os.path.basename(video_path)}.mp4"))
    ffmpeg_command = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        temp_output
    ]
    subprocess.run(ffmpeg_command, check=True)
    files_to_cleanup.append(temp_output)
    return temp_output

def create_looped_video_sequence(video_paths, total_duration, files_to_cleanup):
    temp_video_parts = []
    current_duration = 0
    i = 0
    while current_duration < total_duration:
        video_path = video_paths[i % len(video_paths)]
        temp_output = create_video_part(video_path, min(get_media_duration(video_path), total_duration - current_duration), files_to_cleanup)
        temp_video_parts.append(temp_output)
        current_duration += get_media_duration(video_path)
        i += 1
    return temp_video_parts

def create_cut_video_sequence(video_paths, total_duration, files_to_cleanup):
    temp_video_parts = []
    current_duration = 0
    for video_path in video_paths:
        remaining_duration = total_duration - current_duration
        if remaining_duration <= 0:
            break
        temp_output = create_video_part(video_path, min(get_media_duration(video_path), remaining_duration), files_to_cleanup)
        temp_video_parts.append(temp_output)
        current_duration += get_media_duration(temp_output)
    return temp_video_parts

def create_mixed_media_sequence(video_paths, image_paths, audio_path, total_duration, files_to_cleanup):
    temp_video_parts = []
    video_duration = sum([get_media_duration(video) for video in video_paths])
    remaining_duration = total_duration - video_duration
    image_duration = remaining_duration / len(image_paths) if image_paths else 0

    for i, video_path in enumerate(video_paths):
        temp_output = os.path.join(TEMP_ASSETS_FOLDER, sanitize_filename(f"temp_{i}_{os.path.basename(video_path)}.mp4"))
        ffmpeg_command = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-profile:v", "high",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest", temp_output
        ]
        subprocess.run(ffmpeg_command, check=True)
        temp_video_parts.append(temp_output)
        files_to_cleanup.append(temp_output)

    for i, image_path in enumerate(image_paths):
        temp_output = os.path.join(TEMP_ASSETS_FOLDER, sanitize_filename(f"temp_{i + len(video_paths)}_{os.path.basename(image_path)}.mp4"))
        ffmpeg_command = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-t", str(image_duration),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-profile:v", "high",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest", temp_output
        ]
        subprocess.run(ffmpeg_command, check=True)
        temp_video_parts.append(temp_output)
        files_to_cleanup.append(temp_output)

    return temp_video_parts

def main():
    print("Entering main function...")
    args = parse_arguments()
    print("Arguments parsed...")
    
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
                audio_path, title, description = generate_speech(args.text, args.voice_id, args.autofill)
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
            audio_path, title, description = generate_speech(args.text, args.voice_id, args.autofill)
            files_to_cleanup.append(audio_path)
        elif args.autofill:
            raise ValueError("Neither audio nor text for speech generation provided in autofill mode.")
        else:
            audio_path, title, description = get_audio_source()
            files_to_cleanup.append(audio_path)

        # Handle image/video inputs
        if args.autofill and not args.image:
            args.image = "generate"
        if args.image == "generate":
            args.image_description = args.image_description or description or title or "A visual representation of audio"
        image_inputs = get_image_inputs(args, files_to_cleanup)

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
            print("Cleaning up temporary files...")
            cleanup_files(files_to_cleanup)
        else:
            print("Temporary files were not cleaned up. Use --cleanup flag to remove them in future runs.")
            print("Files that would be cleaned up:")
            for file in files_to_cleanup:
                print(f"  {file}")

    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

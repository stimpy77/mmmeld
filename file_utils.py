import os
import re
import requests
from pytube import YouTube
from config import TEMP_ASSETS_FOLDER, MAX_FILENAME_LENGTH

def sanitize_filename(filename):
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    # Trim whitespace
    filename = filename.strip()
    # Ensure the filename is not empty
    if not filename:
        filename = "unnamed"
    # Truncate to a reasonable length
    max_length = 255 - len(os.path.splitext(filename)[1])  # Account for extension
    if len(filename) > max_length:
        filename = filename[:max_length]
    return filename

def ensure_temp_folder():
    if not os.path.exists(TEMP_ASSETS_FOLDER):
        os.makedirs(TEMP_ASSETS_FOLDER)

def cleanup_files(files):
    print(f"Attempting to clean up {len(files)} files:")
    for file in files:
        try:
            if os.path.exists(file) and os.path.isfile(file):
                os.remove(file)
                print(f"Removed temporary file: {file}")
            else:
                print(f"File not found or is not a file: {file}")
        except OSError as e:
            print(f"Error removing file {file}: {e}")
    print(f"Cleanup completed. Temporary folder '{TEMP_ASSETS_FOLDER}' was not removed.")

def get_default_output_path(audio_path, title, image_inputs=None):
    if audio_path:
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        # If the title is derived from the audio filename, don't use it
        if title and title != base_name:
            base_name = f"{base_name}_{title}"
    elif title:
        base_name = title
    elif image_inputs:
        # Use the first image/video input for the base name
        base_name = os.path.splitext(os.path.basename(image_inputs[0]))[0]
    else:
        base_name = "output"

    base_name = sanitize_filename(base_name)
    output_path = f"{base_name}.mp4"
    counter = 1
    while os.path.exists(output_path):
        output_path = f"{base_name}_{counter}.mp4"
        counter += 1
    return output_path

def download_youtube_audio(url, files_to_cleanup):
    try:
        yt = YouTube(url)
        print(f"Downloading audio from YouTube video: {yt.title}")
        audio_stream = yt.streams.filter(only_audio=True).first()
        if not audio_stream:
            raise ValueError("No audio stream found for this YouTube video.")
        
        output_path = os.path.join(TEMP_ASSETS_FOLDER, f"{yt.title}.mp3")
        audio_stream.download(output_path=TEMP_ASSETS_FOLDER, filename=f"{yt.title}.mp3")
        files_to_cleanup.append(output_path)
        return output_path
    except Exception as e:
        print(f"Error downloading YouTube audio: {e}")
        return None

def download_image(url):
    response = requests.get(url)
    if response.status_code == 200:
        file_name = os.path.basename(url)
        output_path = os.path.join(TEMP_ASSETS_FOLDER, file_name)
        with open(output_path, 'wb') as f:
            f.write(response.content)
        return output_path
    else:
        raise ValueError(f"Failed to download image from {url}")

def generate_image(title, description):
    # Implement image generation logic here
    # For now, we'll just return a placeholder path
    return os.path.join(TEMP_ASSETS_FOLDER, "generated_image.png")

def get_multiline_input(prompt):
    print(prompt)
    lines = []
    while True:
        line = input()
        if line:
            lines.append(line)
        else:
            break
    return '\n'.join(lines)

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
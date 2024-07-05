import os
import requests
from pytube import YouTube
from config import TEMP_ASSETS_FOLDER, MAX_FILENAME_LENGTH

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

def get_default_output_path(audio_path, title):
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_')).rstrip()
    safe_title = safe_title[:MAX_FILENAME_LENGTH]
    return f"{safe_title}_{base_name}.mp4"

def download_youtube_audio(url):
    yt = YouTube(url)
    audio_stream = yt.streams.filter(only_audio=True).first()
    output_path = os.path.join(TEMP_ASSETS_FOLDER, f"{yt.title}.mp3")
    audio_stream.download(output_path=TEMP_ASSETS_FOLDER, filename=f"{yt.title}.mp3")
    return output_path

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
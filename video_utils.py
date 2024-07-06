import logging
import math
import os
import subprocess
from file_utils import sanitize_filename, ensure_temp_folder, cleanup_files, get_default_output_path
from config import TEMP_ASSETS_FOLDER

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
    image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.avif', '.tiff', '.tif')
    if file_path.lower().endswith('.gif') or not file_path.lower().endswith(image_extensions):
        return True
    return False

def create_visual_sequence(inputs, total_duration, files_to_cleanup):
    temp_video_parts = []
    current_duration = 0
    loop_count = 0

    while current_duration < total_duration:
        for input_file in inputs:
            input_duration = get_media_duration(input_file)
            
            if is_video(input_file):
                temp_output = os.path.join(TEMP_ASSETS_FOLDER, f"temp_{os.path.basename(input_file)}.ts")
                remaining_duration = min(input_duration, total_duration - current_duration)
                subprocess.run([
                    "ffmpeg", "-y", "-i", input_file,
                    "-t", str(remaining_duration),
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-an",
                    "-f", "mpegts", temp_output
                ], check=True)
                temp_video_parts.append(temp_output)
                files_to_cleanup.append(temp_output)
            else:  # Image
                temp_output = os.path.join(TEMP_ASSETS_FOLDER, f"temp_{os.path.basename(input_file)}.mp4")
                create_video_from_image(input_file, total_duration, temp_output)
                temp_video_parts.append(temp_output)
                files_to_cleanup.append(temp_output)
            
            current_duration += input_duration
            if current_duration >= total_duration:
                break

        loop_count += 1
        if loop_count > 1000:  # Safeguard against infinite loops
            print("Warning: Maximum loop count reached. Stopping video sequence creation.")
            break

    return temp_video_parts, current_duration

def create_video_from_image(image_path, duration, output_path, fps=30):
    ffmpeg_command = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-vf", f"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-r", str(fps),
        output_path
    ]
    subprocess.run(ffmpeg_command, check=True)

def generate_video(inputs, main_audio_path, bg_music_path, output_path, bg_music_volume, start_margin, end_margin):
    main_audio_duration = get_media_duration(main_audio_path) if main_audio_path else 0
    
    # Calculate total duration based on whether main audio is present
    if main_audio_path:
        total_duration = main_audio_duration + start_margin + end_margin
    else:
        # Calculate duration based on input media
        total_duration = sum(get_media_duration(input_file) for input_file in inputs)
        # If only images are provided, set a minimum duration
        if all(not is_video(input_file) for input_file in inputs):
            total_duration = max(total_duration, 5 * len(inputs))  # 5 seconds per image

    fade_duration = end_margin if main_audio_path else min(2.0, total_duration / 10)  # Default 2s fade or 10% of total duration

    ensure_temp_folder()
    files_to_cleanup = []

    # Create the visual sequence
    video_parts, visual_duration = create_visual_sequence(inputs, total_duration, files_to_cleanup)

    # Adjust total_duration if no main audio and visual_duration is longer
    if not main_audio_path and visual_duration > total_duration:
        total_duration = visual_duration

    # If output_path is not provided, generate a default one
    if not output_path:
        # Remove the second argument (title) to avoid duplication
        output_path = get_default_output_path(main_audio_path, None, inputs)

    # Prepare the filter complex for mixing audio and applying video fade-out
    filter_complex = []

    # Video processing with fade
    filter_complex.append(f"[0:v]fps=30,format=yuv420p,trim=duration={total_duration},setpts=PTS-STARTPTS[v0]")
    filter_complex.append(f"[v0]fade=t=out:st={total_duration-fade_duration}:d={fade_duration}[final_video]")

    # Audio processing
    audio_index = 1
    if main_audio_path:
        filter_complex.append(f"[{audio_index}:a]adelay={int(start_margin*1000)}|{int(start_margin*1000)},apad=pad_dur={end_margin}[main_audio]")
        audio_index += 1

    if bg_music_path:
        bg_music_duration = get_media_duration(bg_music_path)
        loop_count = math.ceil(total_duration / bg_music_duration)
        filter_complex.append(f"[{audio_index}:a]aloop=loop={loop_count-1}:size={int(bg_music_duration*48000)}[looped_bg]")
        filter_complex.append(f"[looped_bg]volume={bg_music_volume},afade=t=out:st={total_duration-fade_duration}:d={fade_duration}[bg_audio]")

    if main_audio_path and bg_music_path:
        filter_complex.append("[main_audio][bg_audio]amix=inputs=2:duration=longest[final_audio]")
    elif main_audio_path:
        filter_complex.append("[main_audio]acopy[final_audio]")
    elif bg_music_path:
        filter_complex.append("[bg_audio]acopy[final_audio]")

    # Construct the ffmpeg command
    ffmpeg_command = ["ffmpeg", "-y"]

    # Add input files
    ffmpeg_command.extend(["-i", f"concat:{'|'.join(video_parts)}"])
    if main_audio_path:
        ffmpeg_command.extend(["-i", main_audio_path])
    if bg_music_path:
        ffmpeg_command.extend(["-i", bg_music_path])

    # Add filter complex
    ffmpeg_command.extend(["-filter_complex", ";".join(filter_complex)])

    # Add output mapping
    ffmpeg_command.extend(["-map", "[final_video]"])
    if main_audio_path or bg_music_path:
        ffmpeg_command.extend(["-map", "[final_audio]"])

    # Add output options
    ffmpeg_command.extend([
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(total_duration),
        output_path
    ])

    # Print the ffmpeg command for debugging
    print("FFmpeg command:")
    print(" ".join(ffmpeg_command))

    # Run the ffmpeg command
    try:
        subprocess.run(ffmpeg_command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running ffmpeg command: {e}")
        return False
    finally:
        cleanup_files(files_to_cleanup)

    return True


def create_image_part(image_path, duration, files_to_cleanup):
    temp_output = os.path.join(TEMP_ASSETS_FOLDER, sanitize_filename(f"temp_{os.path.basename(image_path)}.ts"))
    ffmpeg_command = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-t", str(duration),
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0",
        "-f", "mpegts",
        temp_output
    ]
    subprocess.run(ffmpeg_command, check=True)
    files_to_cleanup.append(temp_output)
    return temp_output

def create_video_part(video_path, duration, files_to_cleanup):
    temp_output = os.path.join(TEMP_ASSETS_FOLDER, sanitize_filename(f"temp_{os.path.basename(video_path)}.ts"))
    ffmpeg_command = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0",
        "-an",
        "-f", "mpegts",
        temp_output
    ]
    subprocess.run(ffmpeg_command, check=True)
    files_to_cleanup.append(temp_output)
    return temp_output

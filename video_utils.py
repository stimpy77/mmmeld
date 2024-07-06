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

def create_visual_sequence(inputs, total_duration):
    video_parts = []
    current_duration = 0

    for input_file in inputs:
        input_duration = get_media_duration(input_file)
        
        if is_video(input_file):
            video_parts.append(input_file)
        else:  # Image
            temp_output = os.path.join(TEMP_ASSETS_FOLDER, f"temp_{os.path.basename(input_file)}.mp4")
            create_video_from_image(input_file, 5.0, temp_output)
            video_parts.append(temp_output)
        
        current_duration += input_duration

    return video_parts, current_duration

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
    
    if main_audio_path:
        total_duration = main_audio_duration + start_margin + end_margin
        fade_duration = end_margin
    else:
        total_duration = sum(get_media_duration(input_file) for input_file in inputs)
        fade_duration = 0

    ensure_temp_folder()
    files_to_cleanup = []

    video_parts, visual_duration = create_visual_sequence(inputs, total_duration)

    if not main_audio_path and visual_duration > total_duration:
        total_duration = visual_duration

    if not output_path:
        output_path = get_default_output_path(main_audio_path, None, inputs)

    filter_complex = []

    # Video processing
    if main_audio_path:
        filter_complex.append(f"[0:v]fps=30,format=yuv420p,trim=duration={total_duration},setpts=PTS-STARTPTS[v0]")
        filter_complex.append(f"[v0]fade=t=out:st={total_duration-fade_duration}:d={fade_duration}[final_video]")
    else:
        filter_complex.append("[0:v]fps=30,format=yuv420p,setpts=PTS-STARTPTS[final_video]")

    # Audio processing
    if main_audio_path:
        filter_complex.append(f"[1:a]adelay={int(start_margin*1000)}|{int(start_margin*1000)},apad=pad_dur={end_margin}[main_audio]")
    elif inputs and is_video(inputs[0]):
        filter_complex.append("[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[video_audio]")

    if bg_music_path:
        bg_music_duration = get_media_duration(bg_music_path)
        loop_count = math.ceil(total_duration / bg_music_duration)
        filter_complex.append(f"[{len(inputs) + (1 if main_audio_path else 0)}:a]aloop=loop={loop_count-1}:size={int(bg_music_duration*48000)}[looped_bg]")
        filter_complex.append(f"[looped_bg]volume={bg_music_volume},afade=t=out:st={total_duration-fade_duration}:d={fade_duration}[bg_audio]")

    # Mixing audio streams
    if main_audio_path and bg_music_path:
        filter_complex.append("[main_audio][bg_audio]amix=inputs=2:duration=longest[final_audio]")
    elif main_audio_path:
        filter_complex.append("[main_audio]acopy[final_audio]")
    elif bg_music_path and inputs and is_video(inputs[0]):
        filter_complex.append("[video_audio][bg_audio]amix=inputs=2:duration=longest[final_audio]")
    elif bg_music_path:
        filter_complex.append("[bg_audio]acopy[final_audio]")
    elif inputs and is_video(inputs[0]):
        filter_complex.append("[video_audio]acopy[final_audio]")

    ffmpeg_command = ["ffmpeg", "-y"]

    # Add input files
    for video_part in video_parts:
        ffmpeg_command.extend(["-i", video_part])
    if main_audio_path:
        ffmpeg_command.extend(["-i", main_audio_path])
    if bg_music_path:
        ffmpeg_command.extend(["-i", bg_music_path])

    ffmpeg_command.extend(["-filter_complex", ";".join(filter_complex)])
    ffmpeg_command.extend(["-map", "[final_video]"])
    
    if main_audio_path or bg_music_path or (inputs and is_video(inputs[0])):
        ffmpeg_command.extend(["-map", "[final_audio]"])

    ffmpeg_command.extend([
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
    ])

    if main_audio_path:
        ffmpeg_command.extend(["-t", str(total_duration)])

    ffmpeg_command.append(output_path)

    print("FFmpeg command:")
    print(" ".join(ffmpeg_command))

    try:
        subprocess.run(ffmpeg_command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running ffmpeg command: {e}")
        return False
    finally:
        cleanup_files(files_to_cleanup)

    return True

import subprocess
import logging
import os
import math

# Instructions:
# 1. Review and Rewrite:
#    - Study README.md for requirements and use cases.
#    - Review all .py files for bugs and missing features, focusing on video generation.
#    - Rewrite video_utils.py to meet all requirements.
# 2. Duration Calculation:
#    - Create a function to determine total duration based on main audio, inputs, and margin.
#    - With audio: total duration = main_audio_duration + start_margin + end_margin.
#    - Without audio: total duration = 5 seconds per image + video durations.
#    - Images and videos play sequentially, and start/end margins are ignored without main audio.
# 3. Visual Sequence:
#    - Create a function to sequence and render visuals to a lossless file.
#    - Visuals sized for full expected duration; images have a natural duration of 5 seconds.
#    - Multiple videos render sequentially into one sequence.
# 4. Final Render:
#    - Loop visual elements, overlay main audio with margins and background music.
#    - Fade out background music and sequence in the tail margin window if main audio exists.
#    - No main audio: use video audio and looping background music, cut off at sequence end.
#    - Avoid overlapping video audio; background music loops and cuts off with sequence or audio end.
#    - Disable audio processing when only images are present.
# 5. Additional Notes:
#    - Use ffmpeg, not moviepy.
#    - Prioritize validation tests: single image with audio, single image without audio, etc.
#    - Embed these instructions as comments in video_utils.py and never remove them.
#    - Add extensive logging for ffmpeg operations.
#    - Verify requirements repeatedly against README.md and specifications.
#    - Intermediate files should be lossless; final render should be high quality mp4

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_media_duration(file_path):
    """Get the duration of a media file using ffprobe. Return 5 seconds for images."""
    if not is_video(file_path):
        
        # if file is an audio file, get the audio length
        if is_audio(file_path):
            return get_audio_duration(file_path)

        else:
            return 5.0  # Fixed duration for images

    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.info(f"get_media_duration: file_path={file_path}, output='{result.stdout.strip()}'")
    return float(result.stdout.strip())

def is_audio(file_path):
    audio_extensions = ['.mp3', '.wav', '.aac', '.flac', '.ogg']
    return os.path.splitext(file_path)[1].lower() in audio_extensions

def is_video(file_path):
    """Check if the file is a video."""
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.mpeg', '.mpg', '.m4v']
    return os.path.splitext(file_path)[1].lower() in video_extensions

def get_audio_duration(file_path):
    # get the duration of the audio file using ffprobe
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.info(f"get_audio_duration: file_path={file_path}, output='{result.stdout.strip()}'")
    return float(result.stdout.strip())

def calculate_total_duration(main_audio_path, image_inputs, start_margin, end_margin):
    """Calculate the total duration of the output video."""
    if main_audio_path:
        main_audio_duration = get_media_duration(main_audio_path)
        return main_audio_duration + start_margin + end_margin
    else:
        total_duration = sum(get_media_duration(input_path) for input_path in image_inputs)
        return max(total_duration, 5)  # Ensure minimum 5 seconds when there's no main audio

def run_ffmpeg_command(cmd):
    """Run an ffmpeg command with proper error handling and logging, displaying output in real-time."""
    try:
        # Add -y flag to overwrite files without prompting
        if '-y' not in cmd:
            cmd.insert(1, '-y')
        
        # Use Popen to get real-time output
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
        
        logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
        
        # Read and print the output in real-time
        for line in process.stdout:
            print(line, end='', flush=True)  # Print to console with flushing
            logger.debug(line.strip())  # Log to file without extra newlines
        
        # Wait for the process to finish and get the return code
        return_code = process.wait()
        
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, cmd)
        
        logger.info("ffmpeg command completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg command failed with return code {e.returncode}")
        raise
    except Exception as e:
        logger.error(f"An error occurred while running ffmpeg: {str(e)}")
        raise

def resize_and_pad(input_path, output_path, target_size=(1920, 1080)):
    """Resize and pad the input image/video to the target size using hardware acceleration."""
    input_ext = os.path.splitext(input_path)[1].lower()
    output_ext = os.path.splitext(output_path)[1].lower()

    base_cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "auto",  # Enable hardware acceleration
        "-i", input_path,
        "-vf", f"scale={target_size[0]}:{target_size[1]}:force_original_aspect_ratio=decrease,pad={target_size[0]}:{target_size[1]}:(ow-iw)/2:(oh-ih)/2"
    ]

    if is_image(input_path):
        # For images, save as image format
        cmd = base_cmd + [output_path]
    else:
        if output_ext == '.webm':
            # For WebM output, use VP9 encoding
            cmd = base_cmd + [
                "-c:v", "libvpx-vp9",
                "-lossless", "1",  # Use lossless VP9 encoding
                "-row-mt", "1",  # Enable row-based multithreading
                "-tile-columns", "4",  # Use tile columns for faster encoding
                "-frame-parallel", "1",  # Enable frame-level parallelism
                "-speed", "4",  # Adjust speed (0-8, higher is faster but potentially lower quality)
                "-c:a", "libopus",  # Use Opus for audio in WebM
            ]
        else:
            # For other formats (including MP4), use H.264 encoding
            cmd = base_cmd + [
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "0",  # Use lossless H.264 encoding
                "-c:a", "aac",  # Use AAC for audio in other formats
            ]
        cmd.append(output_path)
    
    logger.info(f"Resizing and padding: {' '.join(cmd)}")
    run_ffmpeg_command(cmd)
    return output_path

def preprocess_inputs(image_inputs, temp_folder, target_size=(1920, 1080)):
    """Preprocess all input images and videos to ensure consistent size and format."""
    os.makedirs(temp_folder, exist_ok=True)  # Ensure the temporary folder exists
    processed_inputs = []
    for input_path in image_inputs:
        if is_video(input_path):
            # Check if the video already meets the target size
            video_info = get_video_info(input_path)
            if video_info['width'] == target_size[0] and video_info['height'] == target_size[1]:
                processed_inputs.append(input_path)
                continue
        
        if is_image(input_path) or video_info['width'] != target_size[0] or video_info['height'] != target_size[1]:
            output_path = os.path.join(temp_folder, f"processed_{os.path.basename(input_path)}")
            processed_inputs.append(resize_and_pad(input_path, output_path, target_size))
        else:
            processed_inputs.append(input_path)
    return processed_inputs

def get_video_info(file_path):
    """Get video information using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "stream=width,height",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    width, height = map(int, result.stdout.strip().split('\n'))
    return {'width': width, 'height': height}

def create_visual_sequence(processed_inputs, total_duration, temp_folder, has_audio):
    temp_sequence = os.path.join(temp_folder, "temp_sequence.mkv")
    filter_complex = []
    
    for i, input_file in enumerate(processed_inputs):
        duration = get_media_duration(input_file)
        if has_audio:
            trim_duration = min(duration, total_duration)
        else:
            trim_duration = duration if is_video(input_file) else 5.0
        
        if is_image(input_file):
            filter_complex.append(f"[{i}:v]loop=loop=-1:size=1:start=0,trim=duration={trim_duration},setpts=PTS-STARTPTS[v{i}];")
        else:
            filter_complex.append(f"[{i}:v]trim=duration={trim_duration},setpts=PTS-STARTPTS[v{i}];")
    
    filter_complex.append(f"{''.join([f'[v{i}]' for i in range(len(processed_inputs))])}concat=n={len(processed_inputs)}:v=1:a=0[outv]")
    
    inputs = []
    for input_file in processed_inputs:
        inputs.extend(["-i", input_file])
    
    cmd = ["ffmpeg", "-y", "-hwaccel", "auto"] + inputs + [
        "-filter_complex", "".join(filter_complex),
        "-map", "[outv]",
        "-c:v", "libx264",  # Use H.264 encoding instead of copying
        "-preset", "ultrafast",  # Use a ultrafast preset for lossless intermediate
        "-crf", "0",  # for lossless intermediate
        temp_sequence
    ]
    
    logger.info(f"Creating visual sequence: {' '.join(cmd)}")
    run_ffmpeg_command(cmd)
    return temp_sequence

def generate_video(image_inputs, audio_path, bg_music_path, output_path, bg_music_volume, start_margin, end_margin, temp_folder):
    """Generate the final video with audio and background music."""
    processed_inputs = preprocess_inputs(image_inputs, temp_folder)
    total_duration = calculate_total_duration(audio_path, processed_inputs, start_margin, end_margin)
    visual_sequence = create_visual_sequence(processed_inputs, total_duration, temp_folder, bool(audio_path))

    print(f"Debug: Total duration: {total_duration}")

    filter_complex = []
    inputs = ["-i", visual_sequence]
    
    if audio_path:
        inputs.extend(["-i", audio_path])
        filter_complex.append(f"[1:a]adelay={int(start_margin*1000)}|{int(start_margin*1000)},apad=pad_dur={end_margin}[main_audio];")
        # Loop the visual sequence to match the total duration
        filter_complex.append(f"[0:v]loop=-1:size={int(total_duration*30)}:start=0,setpts=N/FRAME_RATE/TB[looped_video];")
        filter_complex.append(f"[looped_video]trim=duration={total_duration},setpts=PTS-STARTPTS[trimmed_video];")
    else:
        # Handle case with no main audio
        filter_complex.append("[0:v]setpts=PTS-STARTPTS[trimmed_video];")
        if any(is_video(input_path) for input_path in processed_inputs):
            for i, input_path in enumerate(processed_inputs):
                if is_video(input_path):
                    inputs.extend(["-i", input_path])
                    filter_complex.append(f"[{i+1}:a]asetpts=PTS-STARTPTS[a{i}];")
            if len(filter_complex) > 1:
                filter_complex.append(f"{''.join([f'[a{i}]' for i in range(len(processed_inputs))])}concat=n={sum(1 for _ in processed_inputs if is_video(_))}:v=0:a=1[video_audio];")
    
    if bg_music_path:
        inputs.extend(["-i", bg_music_path])
        bg_index = len(inputs) // 2  # Calculate the correct index for background music
        filter_complex.append(f"[{bg_index}:a]aloop=-1:size=2e+09,volume={bg_music_volume}[bg_music];")
    
    filter_complex.append("[trimmed_video]fps=30,format=yuv420p")
    if audio_path:
        fade_duration = min(end_margin, total_duration / 10)
        filter_complex.append(f",fade=t=out:st={total_duration-fade_duration}:d={fade_duration}")
    filter_complex.append("[faded_video];")
    
    if audio_path and bg_music_path:
        filter_complex.append(f"[main_audio][bg_music]amix=inputs=2:duration=first:dropout_transition=2[final_audio];")
    elif audio_path:
        filter_complex.append("[main_audio]acopy[final_audio];")
    elif bg_music_path and any(is_video(input_path) for input_path in processed_inputs):
        filter_complex.append("[video_audio][bg_music]amix=inputs=2:duration=first:dropout_transition=2[final_audio];")
    elif bg_music_path:
        filter_complex.append("[bg_music]acopy[final_audio];")
    elif any(is_video(input_path) for input_path in processed_inputs):
        filter_complex.append("[video_audio]acopy[final_audio];")
    
    if audio_path or bg_music_path or any(is_video(input_path) for input_path in processed_inputs):
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", "".join(filter_complex),
            "-map", "[faded_video]", "-map", "[final_audio]",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",  # High quality H.264 encoding
            "-c:a", "aac", "-b:a", "192k",  # High quality AAC audio
            "-movflags", "+faststart",  # Optimize for web playback
            "-t", str(total_duration),
            output_path
        ]
    else:
        # Handle case with only images and no audio
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", "".join(filter_complex),
            "-map", "[faded_video]",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",  # High quality H.264 encoding
            "-movflags", "+faststart",  # Optimize for web playback
            "-t", str(total_duration),
            output_path
        ]
    
    logger.info(f"Generating final video: {' '.join(cmd)}")
    run_ffmpeg_command(cmd)
    
    os.remove(visual_sequence)
    return True

def is_image(file_path):
    """Check if the file is an image."""
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff']
    return os.path.splitext(file_path)[1].lower() in image_extensions

# Ensure to verify requirements against README.md and specifications
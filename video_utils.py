import subprocess
import logging
import os
from pathlib import Path
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
#    - Ensure no infinite loops in ffmpeg.
#    - Prioritize validation tests: single image with audio, single image without audio, etc.
#    - Embed these instructions as comments in video_utils.py and never remove them.
#    - Add extensive logging for ffmpeg operations.
#    - Verify requirements repeatedly against README.md and specifications.

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_media_duration(file_path):
    """Get the duration of a media file using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.info(f"get_media_duration: file_path={file_path}, output='{result.stdout.strip()}'")
    return float(result.stdout.strip())

def is_video(file_path):
    """Check if the file is a video."""
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-count_packets", "-show_entries", "stream=nb_read_packets",
        "-of", "csv=p=0", file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return int(result.stdout.strip()) > 0

def calculate_total_duration(main_audio_path, image_inputs, start_margin, end_margin):
    """Calculate the total duration of the output video."""
    if main_audio_path:
        main_audio_duration = get_media_duration(main_audio_path)
        return main_audio_duration + start_margin + end_margin
    else:
        total_duration = 0
        for input_path in image_inputs:
            if is_video(input_path):
                total_duration += get_media_duration(input_path)
            else:
                total_duration += 5  # 5 seconds for images
        return max(total_duration, 5)  # Ensure minimum 5 seconds when there's no main audio

def run_ffmpeg_command(cmd):
    """Run an ffmpeg command with proper error handling and logging."""
    try:
        # Add -y flag to overwrite files without prompting
        if '-y' not in cmd:
            cmd.insert(1, '-y')
        
        # Redirect stderr to stdout to capture all output
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        logger.info(f"ffmpeg command succeeded: {' '.join(cmd)}")
        logger.debug(f"ffmpeg output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg command failed: {' '.join(cmd)}")
        logger.error(f"ffmpeg error output: {e.output}")
        raise

def create_visual_sequence(image_inputs, total_duration, temp_folder, has_main_audio):
    """Create a visual sequence from input images and videos."""
    temp_sequence = Path(temp_folder) / "temp_sequence.mp4"
    filter_complex = []
    inputs = []

    for i, input_path in enumerate(image_inputs):
        inputs.extend(["-i", str(input_path)])
        if is_video(input_path):
            input_duration = get_media_duration(input_path)
            loop_count = math.ceil(total_duration / input_duration)
            filter_complex.append(f"[{i}:v]loop=loop={loop_count}:size={int(input_duration * 30 * loop_count)}:start=0,setpts=N/FRAME_RATE/TB[v{i}];")
        else:
            filter_complex.append(f"[{i}:v]loop=loop=-1:size=1:start=0,setpts=N/FRAME_RATE/TB[v{i}];")
        
        filter_complex.append(f"[v{i}]fps=30,format=yuv420p,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[v{i}];")

    if len(image_inputs) == 1:
        filter_complex.append(f"[v0]trim=duration={total_duration},setpts=PTS-STARTPTS[outv]")
    else:
        filter_complex.append(f"{''.join([f'[v{i}]' for i in range(len(image_inputs))])}concat=n={len(image_inputs)}:v=1:a=0[concat];")
        filter_complex.append(f"[concat]trim=duration={total_duration},setpts=PTS-STARTPTS[outv]")

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", "".join(filter_complex),
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0",
        str(temp_sequence)
    ]
    
    logger.info(f"Creating visual sequence: {' '.join(cmd)}")
    run_ffmpeg_command(cmd)
    
    return temp_sequence

def resize_and_pad(input_path, output_path, target_size=(1920, 1080)):
    """Resize and pad the input image/video to the target size."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", f"scale={target_size[0]}:{target_size[1]}:force_original_aspect_ratio=decrease,pad={target_size[0]}:{target_size[1]}:(ow-iw)/2:(oh-ih)/2",
        "-c:a", "copy", str(output_path)
    ]
    logger.info(f"Resizing and padding: {' '.join(cmd)}")
    run_ffmpeg_command(cmd)
    return output_path

def preprocess_inputs(image_inputs, temp_folder):
    """Preprocess all input images and videos to ensure consistent size and format."""
    os.makedirs(temp_folder, exist_ok=True)  # Ensure the temporary folder exists
    processed_inputs = []
    for input_path in image_inputs:
        output_path = Path(temp_folder) / f"processed_{Path(input_path).name}"
        processed_inputs.append(resize_and_pad(input_path, output_path))
    return processed_inputs

def generate_video(image_inputs, audio_path, bg_music_path, output_path, bg_music_volume, start_margin, end_margin, temp_folder):
    """Generate the final video with audio and background music."""
    processed_inputs = preprocess_inputs(image_inputs, temp_folder)
    total_duration = calculate_total_duration(audio_path, processed_inputs, start_margin, end_margin)
    visual_sequence = create_visual_sequence(processed_inputs, total_duration, temp_folder, bool(audio_path))

    filter_complex = []
    inputs = ["-i", str(visual_sequence)]
    
    if audio_path:
        inputs.extend(["-i", str(audio_path)])
        filter_complex.append(f"[1:a]adelay={int(start_margin*1000)}|{int(start_margin*1000)},apad=pad_dur={end_margin}[main_audio];")
    
    if bg_music_path:
        inputs.extend(["-i", str(bg_music_path)])
        bg_index = 2 if audio_path else 1
        filter_complex.append(f"[{bg_index}:a]aloop=-1:size=2e+09,volume={bg_music_volume}[bg_music];")
    
    filter_complex.append("[0:v]fps=30,format=yuv420p")
    if audio_path:
        fade_duration = min(2, total_duration / 10)
        filter_complex.append(f",fade=t=out:st={total_duration-fade_duration}:d={fade_duration}")
    filter_complex.append("[faded_video];")
    
    if audio_path and bg_music_path:
        filter_complex.append(f"[main_audio][bg_music]amix=inputs=2:duration=first:dropout_transition=2[final_audio];")
    elif audio_path:
        filter_complex.append("[main_audio]acopy[final_audio];")
    elif bg_music_path:
        filter_complex.append("[bg_music]acopy[final_audio];")

    if audio_path or bg_music_path:
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", "".join(filter_complex),
            "-map", "[faded_video]", "-map", "[final_audio]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(total_duration),
            str(output_path)
        ]
    else:
        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", "".join(filter_complex),
            "-map", "[faded_video]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-t", str(total_duration),
            str(output_path)
        ]
    
    logger.info(f"Generating final video: {' '.join(cmd)}")
    run_ffmpeg_command(cmd)
    
    os.remove(visual_sequence)
    return True

# Ensure to verify requirements against README.md and specifications

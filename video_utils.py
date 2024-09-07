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
        if is_audio(file_path):
            logger.info(f"Getting duration for audio file: {file_path}")
            return get_audio_duration(file_path)
        else:
            logger.info(f"Assuming 5 second duration for image: {file_path}")
            return 5.0  # Fixed duration for images

    logger.info(f"Getting duration for video file: {file_path}")
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        logger.info(f"get_media_duration: file_path={file_path}, output='{output}'")
        
        if not output:
            raise ValueError("ffprobe returned empty output")
        
        duration = float(output)
        return duration
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running ffprobe: {e}")
        logger.error(f"ffprobe stderr: {e.stderr}")
        raise
    except ValueError as e:
        logger.error(f"Error parsing ffprobe output: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_media_duration: {e}")
        raise

def is_audio(file_path):
    audio_extensions = ['.mp3', '.wav', '.aac', '.flac', '.ogg']
    return os.path.splitext(file_path)[1].lower() in audio_extensions

def is_video(file_path):
    """Check if the file is a video."""
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.mpeg', '.mpg', '.m4v']
    return os.path.splitext(file_path)[1].lower() in video_extensions

def get_audio_duration(file_path):
    """Get the duration of the audio file using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        logger.info(f"get_audio_duration: file_path={file_path}, output='{output}'")
        
        if not output:
            raise ValueError("ffprobe returned empty output")
        
        duration = float(output)
        return duration
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running ffprobe: {e}")
        logger.error(f"ffprobe stderr: {e.stderr}")
        raise
    except ValueError as e:
        logger.error(f"Error parsing ffprobe output: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_audio_duration: {e}")
        raise

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

def resize_and_pad(input_path, output_path, target_width, target_height):
    """Resize and pad the input image/video to the target size using hardware acceleration."""
    input_ext = os.path.splitext(input_path)[1].lower()
    output_ext = os.path.splitext(output_path)[1].lower()

    base_cmd = [
        "ffmpeg", "-y",
        "-hwaccel", "auto",  # Enable hardware acceleration
        "-i", input_path,
        f"-vf", f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2"
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

def get_video_info(file_path):
    """Get video information using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "stream=width,height",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    width, height = map(int, result.stdout.strip().split('\n'))
    return {'width': width, 'height': height}

def create_visual_sequence(processed_inputs, total_duration, temp_folder, has_main_audio, max_width, max_height):
    temp_video_sequence = os.path.join(temp_folder, "temp_video_sequence.mkv")
    temp_audio_sequence = os.path.join(temp_folder, "temp_audio_sequence.wav")
    video_filter_complex = []
    audio_filter_complex = []
    inputs = []
    
    for i, input_file in enumerate(processed_inputs):
        # Ensure the input has an audio stream
        input_file = ensure_video_has_audio(input_file, temp_folder)
        
        inputs.extend(["-i", input_file])
        duration = get_media_duration(input_file)
        if has_main_audio:
            trim_duration = min(duration, total_duration)
        else:
            trim_duration = duration if is_video(input_file) else 5.0
        
        if is_image(input_file):
            video_filter_complex.append(f"[{i}:v]loop=loop=-1:size=1:start=0,trim=duration={trim_duration},scale={max_width}:{max_height}:force_original_aspect_ratio=decrease,pad={max_width}:{max_height}:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS[v{i}];")
            audio_filter_complex.append(f"aevalsrc=0:duration={trim_duration}[a{i}];")
        else:
            video_filter_complex.append(f"[{i}:v]trim=duration={trim_duration},scale={max_width}:{max_height}:force_original_aspect_ratio=decrease,pad={max_width}:{max_height}:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS[v{i}];")
            audio_filter_complex.append(f"[{i}:a]atrim=duration={trim_duration},asetpts=PTS-STARTPTS[a{i}];")
    
    video_filter_complex.append(f"{''.join([f'[v{i}]' for i in range(len(processed_inputs))])}concat=n={len(processed_inputs)}:v=1:a=0[outv]")
    audio_filter_complex.append(f"{''.join([f'[a{i}]' for i in range(len(processed_inputs))])}concat=n={len(processed_inputs)}:v=0:a=1[outa]")
    
    # Create video sequence
    video_cmd = ["ffmpeg", "-y", "-hwaccel", "auto"] + inputs + [
        "-filter_complex", "".join(video_filter_complex),
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "0",
        temp_video_sequence
    ]
    
    logger.info(f"Creating video sequence: {' '.join(video_cmd)}")
    run_ffmpeg_command(video_cmd)
    
    # Create audio sequence
    audio_cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", "".join(audio_filter_complex),
        "-map", "[outa]",
        "-c:a", "pcm_s16le",
        temp_audio_sequence
    ]
    
    logger.info(f"Creating audio sequence: {' '.join(audio_cmd)}")
    run_ffmpeg_command(audio_cmd)
    
    return temp_video_sequence, temp_audio_sequence

def ensure_video_has_audio(input_path, temp_folder):
    """Ensure that the video has an audio track, even if silent."""
    output_path = os.path.join(temp_folder, f"audio_ensured_{os.path.basename(input_path)}")
    
    # Check if the video already has an audio stream
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a", "-count_packets",
           "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", input_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    try:
        audio_packets = int(result.stdout.strip())
    except ValueError:
        # If conversion fails, assume no audio packets
        audio_packets = 0
    
    if audio_packets > 0:
        # Video already has audio, just copy it
        return input_path
    
    # Add silent audio to the video
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        output_path
    ]
    
    logger.info(f"Adding silent audio to video: {' '.join(cmd)}")
    run_ffmpeg_command(cmd)
    return output_path

def calculate_max_dimensions(inputs):
    """Calculate the maximum width and height of all input images and videos."""
    max_width = 0
    max_height = 0

    for input_path in inputs:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x", input_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        width, height = map(int, result.stdout.strip().split('x'))
        max_width = max(max_width, width)
        max_height = max(max_height, height)

    return max_width, max_height

def generate_video(image_inputs, audio_path, bg_music_path, output_path, bg_music_volume, start_margin, end_margin, temp_folder, dimensions=None):
    """Generate the final video with audio and background music."""
    # Parse dimensions
    if dimensions:
        if dimensions.lower() in ["square", "portrait", "landscape"]:
            if dimensions.lower() == "square":
                max_width = max_height = 1024
            elif dimensions.lower() == "portrait":
                max_width, max_height = 1024, 1792
            else:  # landscape
                max_width, max_height = 1792, 1024
        elif "x" in dimensions:
            max_width, max_height = map(int, dimensions.split("x"))
        else:
            logger.warning(f"Invalid dimensions: {dimensions}. Using default 1024x1024.")
            max_width = max_height = 1024
    else:
        # If dimensions are not specified, use the maximum dimensions of input files
        max_width, max_height = calculate_max_dimensions(image_inputs)
    
    # Convert .m4a to .wav if necessary
    if audio_path and audio_path.lower().endswith('.m4a'):
        wav_audio_path = os.path.join(temp_folder, "converted_audio.wav")
        convert_m4a_to_wav(audio_path, wav_audio_path)
        audio_path = wav_audio_path

    total_duration = calculate_total_duration(audio_path, image_inputs, start_margin, end_margin)
    visual_sequence, audio_sequence = create_visual_sequence(image_inputs, total_duration, temp_folder, bool(audio_path), max_width, max_height)
    fade_duration = 0

    logger.info(f"Total duration: {total_duration}")

    filter_complex = []
    inputs = ["-i", visual_sequence, "-i", audio_sequence]
    
    if audio_path:
        inputs.extend(["-i", audio_path])
        filter_complex.append(f"[2:a]adelay={int(start_margin*1000)}|{int(start_margin*1000)},apad=pad_dur={end_margin},loudnorm=I=-16:TP=-1.5:LRA=11[main_audio];")
        filter_complex.append(f"[0:v]loop=-1:size={int(total_duration*30)}:start=0,setpts=N/FRAME_RATE/TB[looped_video];")
        filter_complex.append(f"[looped_video]trim=duration={total_duration},setpts=PTS-STARTPTS[trimmed_video];")
    else:
        filter_complex.append("[0:v]setpts=PTS-STARTPTS[trimmed_video];")
    
    if bg_music_path:
        inputs.extend(["-i", bg_music_path])
        bg_index = len(inputs) // 2 - 1
        filter_complex.append(f"[{bg_index}:a]aloop=-1:size=2e+09,volume={bg_music_volume}[bg_music];")
    
    filter_complex.append("[trimmed_video]fps=30,format=yuv420p")
    if audio_path:
        filter_complex.append(f",fade=t=out:st={total_duration-end_margin}:d={end_margin}")
    filter_complex.append("[faded_video];")
    
    if audio_path and bg_music_path:
        filter_complex.append(f"[main_audio][bg_music]amix=inputs=2:duration=first:dropout_transition=2[final_audio];")
    elif audio_path:
        filter_complex.append("[main_audio]acopy[final_audio];")
    elif bg_music_path:
        filter_complex.append(f"[1:a][bg_music]amix=inputs=2:duration=first:dropout_transition=2[final_audio];")
    else:
        filter_complex.append("[1:a]acopy[final_audio];")
    
    filter_complex.append(f"[final_audio]afade=t=out:st={total_duration-end_margin}:d={end_margin}[faded_audio];")
    
    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", "".join(filter_complex),
        "-map", "[faded_video]", "-map", "[faded_audio]",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-t", str(total_duration),
        output_path
    ]
    
    logger.info(f"Generating final video: {' '.join(cmd)}")
    run_ffmpeg_command(cmd)
    
    os.remove(visual_sequence)
    os.remove(audio_sequence)
    return True

def convert_m4a_to_wav(input_path, output_path):
    """Convert .m4a file to .wav format."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-acodec", "pcm_s16le",
        output_path
    ]
    logger.info(f"Converting .m4a to .wav: {' '.join(cmd)}")
    run_ffmpeg_command(cmd)

def is_image(file_path):
    """Check if the file is an image."""
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff']
    return os.path.splitext(file_path)[1].lower() in image_extensions

def validate_video(output_path, expected_duration, has_audio):
    """Validate the generated video."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    actual_duration = float(result.stdout.strip())
    
    logger.info(f"Validating video: expected duration={expected_duration}, actual duration={actual_duration}")
    
    if abs(actual_duration - expected_duration) > 0.5:  # Allow 0.5 second tolerance
        logger.error(f"Video duration mismatch: expected {expected_duration}, got {actual_duration}")
        return False
    
    if has_audio:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "a", "-count_packets",
               "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        audio_packets = int(result.stdout.strip())
        
        if audio_packets == 0:
            logger.error("Video should have audio, but no audio packets found")
            return False
    
    logger.info("Video validation passed")
    return True

# Validation tests
def run_validation_tests(temp_folder):
    logger.info("Running validation tests")
    
    # Test 1: Single image with audio
    image_path = os.path.join(temp_folder, "test_image.png")
    subprocess.run(["convert", "-size", "100x100", "xc:white", image_path])
    audio_path = os.path.join(temp_folder, "test_audio.wav")
    subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "sine=frequency=1000:duration=5", audio_path])
    
    output_path = os.path.join(temp_folder, "test1_output.mp4")
    generate_video([image_path], audio_path, None, output_path, 0.2, 0.5, 2.0, temp_folder)
    assert validate_video(output_path, 7.5, True), "Test 1 failed"
    
    # Test 2: Single image without audio
    output_path = os.path.join(temp_folder, "test2_output.mp4")
    generate_video([image_path], None, None, output_path, 0.2, 0.5, 2.0, temp_folder)
    assert validate_video(output_path, 5.0, False), "Test 2 failed"
    
    # Add more tests here for other scenarios
    
    logger.info("All validation tests passed")

# Ensure to verify requirements against README.md and specifications
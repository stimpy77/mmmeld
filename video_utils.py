import logging

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
    image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.avif', '.tiff', '.tif')
    if file_path.lower().endswith(image_extensions):
        return False
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    output = result.stdout.strip()
    print(f"is_video: file_path={file_path}, output='{output}'")  # Debugging statement
    if output.isdigit():
        return int(output) > 0
    return False

def generate_video(inputs, main_audio_path, bg_music_path, output_path, bg_music_volume, start_margin, end_margin):
    main_audio_duration = get_media_duration(main_audio_path)
    total_duration = main_audio_duration + start_margin + end_margin
    fade_duration = end_margin  # Define fade duration as end_margin
    logging.debug(f"Main audio duration: {main_audio_duration}")
    logging.debug(f"Total video duration: {total_duration}")
    logging.debug(f"Fade duration: {fade_duration}")

    ensure_temp_folder()
    files_to_cleanup = []

    # Create the visual sequence
    temp_video_parts = create_visual_sequence(inputs, total_duration, files_to_cleanup)

    # Log the created parts
    total_parts_duration = 0
    for i, part in enumerate(temp_video_parts):
        part_duration = get_media_duration(part)
        total_parts_duration += part_duration
        logging.debug(f"Part {i}: {part} - Duration: {part_duration}")
    logging.debug(f"Total duration of all parts: {total_parts_duration}")

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

    # Prepare the filter complex for mixing audio and applying video fade-out
    filter_complex = []

    # Add the main audio to the final video with custom silence margins
    filter_complex.append(f"[1:a]adelay={int(start_margin*1000)}|{int(start_margin*1000)},apad=pad_dur={end_margin}[main_audio]")

    # If background music is provided, add it to the mix with fade out
    if bg_music_path:
        bg_music_duration = get_media_duration(bg_music_path)
        loop_count = math.ceil(total_duration / bg_music_duration)
        fade_start = main_audio_duration + start_margin  # Start fade when main audio ends (including start margin)
        
        filter_complex.append(f"[2:a]aloop=loop={loop_count-1}:size={int(bg_music_duration*48000)}[looped_bg]")
        filter_complex.append(f"[looped_bg]volume={bg_music_volume},afade=t=out:st={fade_start}:d={fade_duration}[bg_music]")
        filter_complex.append(f"[main_audio][bg_music]amix=inputs=2:duration=longest[final_audio]")
    else:
        filter_complex.append("[main_audio]acopy[final_audio]")

    # Apply video fade-out
    filter_complex.append(f"[0:v]fade=t=out:st={total_duration-fade_duration}:d={fade_duration}[final_video]")

    # Prepare the final FFmpeg command
    final_command = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
        "-i", main_audio_path,
    ]

    # Add background music input if provided
    if bg_music_path:
        final_command.extend(["-i", bg_music_path])

    final_command.extend([
        "-filter_complex", ";".join(filter_complex),
        "-map", "[final_video]", "-map", "[final_audio]",
        "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
        "-t", str(total_duration),
        sanitized_output_path
    ])

    logging.debug(f"Final FFmpeg command: {' '.join(final_command)}")
    subprocess.run(final_command, check=True)

    # Clean up temporary files
    cleanup_files(files_to_cleanup)

    return True

def create_visual_sequence(inputs, total_duration, files_to_cleanup):
    logging.debug(f"Starting create_visual_sequence with total_duration: {total_duration}")
    temp_video_parts = []
    video_inputs = [input for input in inputs if is_video(input)]
    image_inputs = [input for input in inputs if not is_video(input)]

    logging.debug(f"Video inputs: {video_inputs}")
    logging.debug(f"Image inputs: {image_inputs}")

    total_video_duration = sum(get_media_duration(video) for video in video_inputs)
    logging.debug(f"Total video duration: {total_video_duration}")

    image_duration = max(0, total_duration - total_video_duration)
    logging.debug(f"Image duration: {image_duration}")

    if image_inputs and image_duration > 0:
        duration_per_image = image_duration / len(image_inputs)
        for image in image_inputs:
            logging.debug(f"Adding image: {image} with duration: {duration_per_image}")
            temp_output = create_image_part(image, duration_per_image, files_to_cleanup)
            temp_video_parts.append(temp_output)

    video_start_time = image_duration
    for video in video_inputs:
        video_duration = min(get_media_duration(video), total_duration - video_start_time)
        logging.debug(f"Adding video: {video} with duration: {video_duration}, starting at: {video_start_time}")
        temp_output = create_video_part(video, video_duration, files_to_cleanup)
        temp_video_parts.append(temp_output)
        video_start_time += video_duration

    logging.debug(f"Number of parts in sequence: {len(temp_video_parts)}")
    return temp_video_parts

def create_looped_video(video_path, target_duration, loop_count, files_to_cleanup):
    temp_output = os.path.join(TEMP_ASSETS_FOLDER, f"temp_looped_{os.path.basename(video_path)}")
    ffmpeg_command = [
        "ffmpeg", "-y",
        "-stream_loop", str(loop_count - 1),
        "-i", video_path,
        "-t", str(target_duration),
        "-c", "copy",
        temp_output
    ]
    subprocess.run(ffmpeg_command, check=True)
    files_to_cleanup.append(temp_output)
    return temp_output


def create_image_part(image_path, duration, files_to_cleanup):
    temp_output = os.path.join(TEMP_ASSETS_FOLDER, sanitize_filename(f"temp_{os.path.basename(image_path)}.mp4"))
    
    ffmpeg_command = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-t", str(duration),
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        temp_output
    ]
    subprocess.run(ffmpeg_command, check=True)
    files_to_cleanup.append(temp_output)
    return temp_output

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
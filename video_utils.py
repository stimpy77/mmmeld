import subprocess
import os
import json
from typing import List, Tuple

def get_media_duration(file_path: str) -> float:
    """Get the duration of a media file using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format',
        '-show_streams', file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return float(data['format']['duration'])

def is_video(file_path: str) -> bool:
    """Check if a file is a video."""
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return any(stream['codec_type'] == 'video' for stream in data['streams'])

def calculate_total_duration(main_audio: str, image_inputs: List[str], start_margin: float, end_margin: float) -> float:
    """Calculate the total duration of the output video."""
    if main_audio:
        return get_media_duration(main_audio) + start_margin + end_margin
    else:
        total_duration = 0
        for input_file in image_inputs:
            if is_video(input_file):
                total_duration += get_media_duration(input_file)
            else:
                total_duration += 5  # 5 seconds for images
        return total_duration

def create_visual_sequence(image_inputs: List[str], total_duration: float, output_path: str) -> None:
    """Create a visual sequence from input images and videos."""
    input_files = []
    filter_complex = []
    for i, input_file in enumerate(image_inputs):
        input_files.extend(['-i', input_file])
        if is_video(input_file):
            filter_complex.append(f'[{i}:v]setpts=PTS-STARTPTS[v{i}]')
        else:
            filter_complex.append(f'[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS+{i*5}/TB,trim=duration=5[v{i}]')
    
    filter_complex.append(f"{''.join([f'[v{i}]' for i in range(len(image_inputs))])}concat=n={len(image_inputs)}:v=1:a=0[outv]")
    filter_complex_str = ';'.join(filter_complex)

    cmd = ['ffmpeg', '-y'] + input_files + [
        '-filter_complex', filter_complex_str,
        '-map', '[outv]',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
        '-t', str(total_duration),
        output_path
    ]
    subprocess.run(cmd, check=True)

def generate_video(
    image_inputs: List[str],
    main_audio: str,
    bg_music: str,
    output_path: str,
    bg_music_volume: float,
    start_margin: float,
    end_margin: float,
    files_to_cleanup: List[str]
) -> bool:
    """Generate the final video with audio and visual elements."""
    total_duration = calculate_total_duration(main_audio, image_inputs, start_margin, end_margin)
    
    # Create visual sequence
    temp_visual_sequence = 'temp_visual_sequence.mp4'
    create_visual_sequence(image_inputs, total_duration, temp_visual_sequence)
    files_to_cleanup.append(temp_visual_sequence)
    
    # Prepare ffmpeg command
    cmd = ['ffmpeg', '-y', '-stream_loop', '-1', '-i', temp_visual_sequence]
    filter_complex = []
    
    if main_audio:
        cmd.extend(['-i', main_audio])
        filter_complex.append(f'[1:a]apad=pad_dur={start_margin + end_margin}[main_audio]')
        filter_complex.append(f'[0:v]setpts=PTS-STARTPTS+{start_margin}/TB[v]')
    else:
        filter_complex.append('[0:v]setpts=PTS-STARTPTS[v]')
    
    if bg_music:
        cmd.extend(['-stream_loop', '-1', '-i', bg_music])
        if main_audio:
            filter_complex.append(f'[2:a]volume={bg_music_volume},apad=whole_dur={total_duration}[bg]')
            filter_complex.append(f'[main_audio][bg]amix=inputs=2:duration=first:dropout_transition=2[a]')
        else:
            filter_complex.append(f'[1:a]volume={bg_music_volume}[bg]')
            filter_complex.append(f'[bg]atrim=duration={total_duration}[a]')
    elif main_audio:
        filter_complex.append('[main_audio]acopy[a]')
    
    if main_audio:
        filter_complex.append(f'[v]fade=t=out:st={total_duration-end_margin}:d={end_margin}[outv]')
    else:
        filter_complex.append('[v]copy[outv]')
    
    filter_complex_str = ';'.join(filter_complex)
    cmd.extend(['-filter_complex', filter_complex_str,
                '-map', '[outv]',
                '-map', '[a]' if main_audio or bg_music else '',
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                '-c:a', 'aac', '-b:a', '192k',
                '-shortest',
                output_path
    ])

    # Remove empty elements from the command
    cmd = [elem for elem in cmd if elem]

    # Execute ffmpeg command
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        print("Error occurred while generating video.")
        return False

def concatenate_audio_files(audio_files: List[str], output_path: str) -> None:
    """Concatenate multiple audio files into a single file."""
    input_files = []
    filter_complex = []
    for i, audio_file in enumerate(audio_files):
        input_files.extend(['-i', audio_file])
        filter_complex.append(f'[{i}:a]')
    
    filter_complex_str = ''.join(filter_complex) + f'concat=n={len(audio_files)}:v=0:a=1[outa]'
    
    cmd = ['ffmpeg', '-y'] + input_files + [
        '-filter_complex', filter_complex_str,
        '-map', '[outa]',
        output_path 
    ]
    subprocess.run(cmd, check=True)

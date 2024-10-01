import os
import re
import logging
import requests
from openai import OpenAI
from deepgram import Deepgram
import asyncio
from pydub import AudioSegment
import mimetypes
import wave
import struct

from config import (
    TEMP_ASSETS_FOLDER,
    ELEVENLABS_VOICE_ID,
    OPENAI_VOICE_ID,
    DEEPGRAM_VOICE_ID
)

MAX_CHUNK_SIZE = 4096

def ensure_temp_folder():
    if not os.path.exists(TEMP_ASSETS_FOLDER):
        os.makedirs(TEMP_ASSETS_FOLDER)

def split_text_into_chunks(text, max_chunk_size=MAX_CHUNK_SIZE):
    # Split text into chunks of max_chunk_size or less
    chunks = []
    current_chunk = []

    for line in text.split('\n'):
        if len(line) > max_chunk_size:
            # If the line itself is too long, split it further
            for sentence in re.split(r'(?<=[.?!])\s+', line):
                if len(sentence) > max_chunk_size:
                    # If the sentence itself is too long, split it further
                    for word in sentence.split(' '):
                        if len(' '.join(current_chunk + [word])) > max_chunk_size:
                            chunks.append(' '.join(current_chunk))
                            current_chunk = [word]
                        else:
                            current_chunk.append(word)
                else:
                    if len(' '.join(current_chunk + [sentence])) > max_chunk_size:
                        chunks.append(' '.join(current_chunk))
                        current_chunk = [sentence]
                    else:
                        current_chunk.append(sentence)
        else:
            if len(' '.join(current_chunk + [line])) > max_chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = [line]
            else:
                current_chunk.append(line)

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks

def generate_speech(text, voice_id=None, autofill=False, tts_provider='elevenlabs', files_to_cleanup=None, output_filename=None):
    # Handle voice ID selection before chunking
    if not voice_id and not autofill:
        if tts_provider == 'elevenlabs':
            voice_id = input(f"Enter ElevenLabs voice ID, or press ENTER for default [{ELEVENLABS_VOICE_ID}]: ") or ELEVENLABS_VOICE_ID
        elif tts_provider == 'openai':
            voice_id = input(f"Enter OpenAI voice ID, or press ENTER for default [{OPENAI_VOICE_ID}]: ") or OPENAI_VOICE_ID
        elif tts_provider == 'deepgram':
            voice_id = input(f"Enter DeepGram voice ID, or press ENTER for default [{DEEPGRAM_VOICE_ID}]: ") or DEEPGRAM_VOICE_ID
    elif not voice_id:
        if tts_provider == 'elevenlabs':
            voice_id = ELEVENLABS_VOICE_ID
        elif tts_provider == 'openai':
            voice_id = OPENAI_VOICE_ID
        elif tts_provider == 'deepgram':
            voice_id = DEEPGRAM_VOICE_ID
    
    chunks = split_text_into_chunks(text)
    audio_files = []
    main_title = None

    # Handle the case where tts_provider might be a list
    if isinstance(tts_provider, list):
        tts_provider = tts_provider[0] if tts_provider else 'elevenlabs'
    tts_provider = tts_provider.lower()
    
    if files_to_cleanup is None:
        files_to_cleanup = []

    for i, chunk in enumerate(chunks):
        print(f"Generating speech for chunk {i + 1}/{len(chunks)} with {tts_provider} ({voice_id})")
        if tts_provider == 'elevenlabs':
            audio_filename, title, _ = generate_speech_with_elevenlabs(chunk, voice_id)
        elif tts_provider == 'openai':
            audio_filename = generate_openai_speech(chunk, voice_id)
            title = generate_title_from_text(chunk)  # Generate a title for OpenAI TTS
        elif tts_provider == 'deepgram':
            audio_filename = generate_deepgram_speech_sync(chunk, voice_id)
            title = generate_title_from_text(chunk)  # Generate a title for Deepgram TTS
        audio_files.append(audio_filename)
        if not main_title:
            main_title = title
        files_to_cleanup.append(audio_filename)
    
    if len(audio_files) > 1:
        output_path = os.path.join(TEMP_ASSETS_FOLDER, f"{main_title}")
        output_path = concatenate_audio_files(audio_files, output_path)
    else:
        output_path = audio_files[0]

    if output_filename:
        output_extension = os.path.splitext(output_path)[1]
        final_output_path = os.path.splitext(output_filename)[0] + output_extension
        os.rename(output_path, final_output_path)
        output_path = final_output_path

    return output_path, main_title, text

def get_file_type(file_path):
    _, extension = os.path.splitext(file_path)
    return extension.lower()[1:]  # Remove the dot and convert to lowercase

def is_valid_audio_file(file_path):
    try:
        AudioSegment.from_file(file_path)
        return True
    except Exception:
        return False

def fix_wav_header(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # Check if the file starts with 'RIFF'
    if data[:4] != b'RIFF':
        # Add RIFF header
        riff_chunk_size = len(data) - 8
        header = struct.pack('<4sI4s', b'RIFF', riff_chunk_size, b'WAVE')
        data = header + data

    # Check for 'fmt ' chunk
    if b'fmt ' not in data[:44]:
        # Add basic fmt chunk (assuming PCM format, 16-bit, 44100 Hz, mono)
        fmt_chunk = struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, 1, 44100, 88200, 2, 16)
        data = data[:12] + fmt_chunk + data[12:]

    # Check for 'data' chunk
    if b'data' not in data:
        # Add data chunk header
        data_chunk_size = len(data) - 44
        data_header = struct.pack('<4sI', b'data', data_chunk_size)
        data = data[:44] + data_header + data[44:]

    # Write the fixed data back to the file
    with open(file_path, 'wb') as f:
        f.write(data)

def generate_speech_with_elevenlabs(text, voice_id):
    ensure_temp_folder()
    print("Generating speech with ElevenLabs...")
    api_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if not api_key:
        raise ValueError("ElevenLabs API key is not set.")
    
    print(f"Using voice ID: {voice_id}")

    tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "Accept": "audio/wav",  # Explicitly request WAV format
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
        content_type = response.headers.get('Content-Type', '')
        print(f"Received content type: {content_type}")  # Debug print
        
        title = generate_title_from_text(text)
        audio_filename = os.path.join(TEMP_ASSETS_FOLDER, f"{title}.wav")  # Always use .wav extension
        
        with open(audio_filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        print(f"Audio generated: {audio_filename}")
        
        if not is_valid_audio_file(audio_filename):
            print(f"Fixing invalid audio file: {audio_filename}")
            fix_wav_header(audio_filename)
        
        return audio_filename, title, text
    else:
        print(response.text)
        raise Exception("Failed to generate speech with ElevenLabs.")

def get_file_extension(content_type):
    content_type = content_type.lower()
    if 'wav' in content_type:
        return 'wav'
    elif 'flac' in content_type:
        return 'flac'
    elif 'aac' in content_type:
        return 'aac'
    elif 'ogg' in content_type:
        return 'ogg'
    elif 'mpeg' in content_type:
        return 'mp3'
    else:
        return 'wav'  # Default to WAV if content type is not recognized

def generate_openai_speech(text, voice_id=None):
    ensure_temp_folder()
    print("Generating speech with OpenAI...")
    client = OpenAI()
    voice_id = voice_id or OPENAI_VOICE_ID
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice=voice_id,
        input=text
    )
    title = generate_title_from_text(text)
    output_path = os.path.join(TEMP_ASSETS_FOLDER, f"{title}.mp3")
    response.stream_to_file(output_path)
    return output_path

async def generate_deepgram_speech(text, voice_id=None):
    deepgram = Deepgram(os.environ["DEEPGRAM_API_KEY"])
    voice_id = voice_id or DEEPGRAM_VOICE_ID
    response = await deepgram.transcription.synthesize(text, voice=voice_id)
    output_path = os.path.join(TEMP_ASSETS_FOLDER, "generated_speech.mp3")
    async with aiofiles.open(output_path, mode='wb') as f:
        await f.write(response)
    return output_path

def generate_deepgram_speech_sync(text, voice_id=None):
    return asyncio.run(generate_deepgram_speech(text, voice_id))

def generate_title_from_text(text, max_length=50):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
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
    # Truncate to max_length
    return title[:max_length]

def get_highest_quality_format(audio_files):
    format_priority = ['wav', 'flac', 'aac', 'ogg', 'mp3']
    file_formats = [os.path.splitext(file)[1][1:].lower() for file in audio_files]
    
    for format in format_priority:
        if format in file_formats:
            return format
    
    return 'wav'  # Default to WAV if no recognized formats are found

def concatenate_audio_files(audio_files, output_path):
    combined = AudioSegment.empty()
    for audio_file in audio_files:
        print(f"Processing file: {audio_file}")
        try:
            if not is_valid_audio_file(audio_file):
                print(f"Fixing invalid audio file: {audio_file}")
                if audio_file.lower().endswith('.wav'):
                    fix_wav_header(audio_file)
                else:
                    print(f"Unable to fix non-WAV file: {audio_file}")
                    continue
            
            segment = AudioSegment.from_file(audio_file)
            combined += segment
        except Exception as e:
            print(f"Error processing {audio_file}: {str(e)}")
            continue
    
    output_format = get_highest_quality_format(audio_files)
    output_path_with_extension = f"{os.path.splitext(output_path)[0]}.{output_format}"
    combined.export(output_path_with_extension, format=output_format)
    print(f"Concatenated audio saved to: {output_path_with_extension}")
    return output_path_with_extension
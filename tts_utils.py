import os
import re
import logging
import requests
from openai import OpenAI
from deepgram import Deepgram
import asyncio

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

def generate_speech(text, voice_id=None, autofill=False, tts_provider='elevenlabs', files_to_cleanup=None):
    print(f"Generating speech for text:\n{text}\n")
    
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

    tts_provider = tts_provider.lower()
    for i, chunk in enumerate(chunks):
        print(f"Generating speech for chunk {i + 1}/{len(chunks)} with {tts_provider}")
        if tts_provider == 'elevenlabs':
            audio_filename, title, _ = generate_speech_with_elevenlabs(chunk, voice_id)
        elif tts_provider == 'openai':
            audio_filename = generate_openai_speech(chunk, voice_id)
        elif tts_provider == 'deepgram':
            audio_filename = generate_deepgram_speech(chunk, voice_id)
        audio_files.append(audio_filename)
        if not main_title:
            main_title = title
        files_to_cleanup.append(audio_filename)
    
    if len(audio_files) > 1:
        output_path = os.path.join(TEMP_ASSETS_FOLDER, f"{main_title}.mp3")
        concatenate_audio_files(audio_files, output_path)
        return output_path, main_title, text
    else:
        return audio_files[0], main_title, text

def generate_speech_with_elevenlabs(text, voice_id):
    ensure_temp_folder()
    print("Generating speech with ElevenLabs...")
    api_key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("XI_API_KEY")
    if not api_key:
        raise ValueError("ElevenLabs API key is not set.")
    
    print(f"Using voice ID: {voice_id}")

    tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "Accept": "application/json",
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
        title = generate_title_from_text(text)
        audio_filename = os.path.join(TEMP_ASSETS_FOLDER, f"{title}.wav")
        with open(audio_filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        print(f"Audio generated: {audio_filename}")
        return audio_filename, title, text
    else:
        print(response.text)
        raise Exception("Failed to generate speech with ElevenLabs.")

def generate_openai_speech(text, voice_id=None):
    client = OpenAI()
    voice_id = voice_id or OPENAI_VOICE_ID
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice_id,
        input=text
    )
    output_path = os.path.join(TEMP_ASSETS_FOLDER, "generated_speech.mp3")
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
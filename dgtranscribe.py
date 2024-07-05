import os
import sys
import json
import argparse
from urllib.parse import urlparse
from deepgram import Deepgram
import requests
import yt_dlp
import asyncio
import logging
import time
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def is_url(string):
    try:
        result = urlparse(string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def sanitize_filename(title, max_length=100):
    # Remove special characters and spaces
    sanitized = re.sub(r'[^\w\-_\. ]', '', title)
    # Replace spaces with underscores
    sanitized = sanitized.replace(' ', '_')
    # Limit to max_length characters
    return sanitized[:max_length]

def download_audio(url):
    logging.info(f"Starting download from URL: {url}")
    start_time = time.time()
    
    from pytube import YouTube
    try:
        yt = YouTube(url)
        logging.info(f"Video title: {yt.title}")
        sanitized_title = sanitize_filename(yt.title)
        audio_stream = yt.streams.filter(only_audio=True).first()
        
        # Download with original extension
        downloaded_file = audio_stream.download(output_path=".", filename=sanitized_title)
        original_extension = os.path.splitext(downloaded_file)[1]
        
        # Rename to .mp3 if it's not already
        if original_extension.lower() != '.mp3':
            output_file = f"{sanitized_title}.mp3"
            os.rename(downloaded_file, output_file)
        else:
            output_file = downloaded_file
        
        logging.info(f"Download completed in {time.time() - start_time:.2f} seconds")
        return output_file
    except Exception as e:
        logging.error(f"An error occurred during download: {str(e)}")
        logging.error(f"Error type: {type(e).__name__}")
        logging.error(f"Error details: {e.args}")
        return None

async def transcribe_async(file_path):
    logging.info(f"Starting transcription for file: {file_path}")
    start_time = time.time()
    
    dg_key = os.getenv('DEEPGRAM_PERSONAL_API_KEY') or os.getenv('DEEPGRAM_API_KEY')
    if not dg_key:
        logging.error("Deepgram API key not found in environment variables")
        raise ValueError("Deepgram API key not found in environment variables")

    dg = Deepgram(dg_key)
    
    with open(file_path, 'rb') as audio:
        source = {'buffer': audio, 'mimetype': 'audio/mp3'}
        options = {
            "smart_format": True,
            "model": "nova-2",  # Updated to use Nova-2 model
            "language": "en-US",
            "paragraphs": True,  # Enable paragraph detection
            "punctuate": True    # Ensure punctuation is enabled for better paragraph detection
        }
        
        logging.info("Sending request to Deepgram API using Nova-2 model")
        try:
            response = await dg.transcription.prerecorded(source, options)
            logging.info(f"Transcription completed in {time.time() - start_time:.2f} seconds")
            return response
        except Exception as e:
            logging.error(f"An error occurred during transcription: {str(e)}")
            raise

def transcribe(file_path):
    logging.info("Entering transcribe function")
    return asyncio.run(transcribe_async(file_path))

def create_basic_transcript(transcription):
    paragraphs = []
    for channel in transcription['results']['channels']:
        paragraphs.extend(channel['alternatives'][0]['paragraphs']['paragraphs'])
    
    # Sort paragraphs by start time across all channels
    paragraphs.sort(key=lambda x: x['start'])
    
    formatted_transcript = ""
    for paragraph in paragraphs:
        paragraph_text = " ".join([sentence['text'] for sentence in paragraph['sentences']])
        formatted_transcript += paragraph_text + "\n\n"
    
    return formatted_transcript.strip()

def main():
    parser = argparse.ArgumentParser(description="Transcribe audio/video files or URLs using Deepgram")
    parser.add_argument("input", help="Path to audio/video file or URL")
    parser.add_argument("-o", "--output", help="Output JSON file path (optional)")
    args = parser.parse_args()

    logging.info(f"Processing input: {args.input}")

    if is_url(args.input):
        file_path = download_audio(args.input)
        if file_path is None:
            logging.error("Failed to download audio. Exiting.")
            return
    else:
        file_path = args.input
        logging.info(f"Using local file: {file_path}")

    logging.info("Starting transcription process")
    transcription = transcribe(file_path)
    
    output_file = args.output or f"{os.path.splitext(file_path)[0]}_transcription.json"
    logging.info(f"Saving transcription to {output_file}")
    with open(output_file, 'w') as f:
        json.dump(transcription, f, indent=2)
    
    # Save basic transcript
    basic_output_file = f"{os.path.splitext(output_file)[0]}-basic.txt"
    logging.info(f"Saving basic transcript to {basic_output_file}")
    basic_transcript = create_basic_transcript(transcription)
    with open(basic_output_file, 'w') as f:
        f.write(basic_transcript)
    
    logging.info(f"Transcription saved to {output_file} and {basic_output_file}")

    if is_url(args.input):
        logging.info(f"Removing temporary file: {file_path}")
        os.remove(file_path)

    logging.info("Process completed")

if __name__ == "__main__":
    main()

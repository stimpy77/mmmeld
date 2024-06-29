# Image Video Generator
Creates a video consisting of an image and audio. Can produce speech from text if no audio provided. Can produce an image if no image provided. Audio can come from local file or from YouTube URL.

## Installation:

Install ffmpeg and ensure it is in your operating system's PATH. See: https://ffmpeg.org/

Install Python and run the following command:

```bash
pip install openai pillow requests tqdm pytube elevenlabs yt-dlp
```

## To use:
```bash
python ./imagevideo.py
```

Answer the questions. 

``Enter the path to the audio file, YouTube video URL, or press Enter to generate speech:`` **``myaudio.wav``**

``Enter the path to the image (or press Enter to generate one):`` **``myimage.png``**

``Enter the path for the output video file (press Enter for default: myvideo.mp4):`` **``My Fantastic Video.mp4``**

### Command-line arguments

You don't have to be prompted.

```
❯ python .\imagevideo.py --help
usage: imagevideo.py [-h] [--audio AUDIO] [--image IMAGE] [--output OUTPUT] [--text TEXT] [--image_description IMAGE_DESCRIPTION] [--openai-key OPENAI_KEY]
                     [--elevenlabs-key ELEVENLABS_KEY]

Generate a video from audio and image, with options for text-to-speech and image generation.

options:
  -h, --help            show this help message and exit
  --audio AUDIO         Path to audio file, YouTube URL, or 'generate' for text-to-speech.
  --image IMAGE         Path to image file or 'generate' to create one.
  --output OUTPUT       Path for the output video file. Default is based on audio filename.
  --text TEXT           Text for speech generation (used if audio is 'generate').
  --image_description IMAGE_DESCRIPTION
                        Description for image generation (used if image is 'generate').

API Keys:
  --openai-key OPENAI_KEY
                        OpenAI API key. Default: Use OPENAI_API_KEY environment variable.
  --elevenlabs-key ELEVENLABS_KEY
                        ElevenLabs API key. Default: Use ELEVENLABS_API_KEY environment variable.

Examples:
  Generate video from local audio and image files:
    python imagevideo.py --audio path/to/audio.mp3 --image path/to/image.png

  Generate video with text-to-speech and generated image:
    python imagevideo.py --audio generate --text "Hello, world!" --image generate --image_description "A sunny day"

  Download YouTube audio and generate image:
    python imagevideo.py --audio https://www.youtube.com/watch?v=dQw4w9WgXcQ --image generate

  Run interactively (no arguments):
    python imagevideo.py
```

If you want anything to be automatatically generated, you will need the following environment variables set up on your operating system:

- `OPENAI_API_KEY`: The API key to use OpenAI services such as GPT (text generation), DALL-E (image generation), and text-to-speech.
- `ELEVENLABS_API_KEY` OR `XI_API_KEY`: The API key provided by ElevenLabs for text-to-speech. You can find it by clicking on your avatar on their web site. 

### Provide audio and image

When asked for audio, provide the full file path to the audio file (.wav, mp3, ...).

When asked for an image, provide the full file path to the image you want to display.

### Provide audio from YouTube URL

When asked for audio, you can provide a YouTube URL to download the audio from.

### Provide audio from text (convert to speech)

When asked for audio, you can just hit ENTER and enter text to be converted to speech. It will generate speech audio and use that as your audio, using the contents of your text as hints for the filename.

### Generating an image

When asked for an image, you can just hit ENTER and enter text to use as hints for an image generator prompt. 

#### Defaulting a generated image

If you hit ENTER again instead of providing image prompt hint text, the image prompt will be automatically generated using the audio hints.

### Defaulting the output file path

When asked for an output file path, you can just hit ENTER and it will generate the output file path based on the audio information and/or filename.

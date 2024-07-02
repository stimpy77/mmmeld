Image Video Generator
=====================

Creates a video consisting of images/videos and provided audio. The original purpose was to "video-ize" a music file.

Features
--------

-   Generate speech from text if no audio is provided

-   Generate an image if no image is provided

-   Use local files or YouTube URLs for audio, images, or videos

-   Create slideshows with multiple images

-   Handle multiple video inputs as a sequence (looped if necessary)

-   Support for background music

-   Multiple text-to-speech providers: ElevenLabs, OpenAI, and DeepGram

Behavior Notes
--------------

-   Video duration is determined by the main audio length plus margins (0.5s start, 2s end)

-   When using video assets, only the video is used, not the audio

-   For mixed image and video inputs, sequencing prioritizes showing full videos

-   Visual component fades out during the final 2 seconds of silence

-   Improved handling of special characters in filenames

Installation
------------

1. Install ffmpeg and ensure it's in your system PATH: https://ffmpeg.org/

2. Install Python and required packages:

pip install openai pillow requests tqdm pytube elevenlabs yt-dlp aiohttp deepgram-sdk

Usage
-----

### Interactive Mode

Run the script without arguments:

python ./imagevideo.py

Follow the prompts to provide audio, image/video, and output file information.

### Command-line Arguments

For non-interactive use, you can provide arguments:

python imagevideo.py --audio path/to/audio.mp3 --image path/to/image.png --output output.mp4

For full list of options:

python imagevideo.py --help

### Key Features

-   Generate speech: Use --audio generate --text "Your text here"

-   Generate image: Use --image generate --image_description "Your description"

-   YouTube inputs: Provide YouTube URLs for audio or background music

-   Multiple inputs: Use comma-separated list for multiple images/videos

-   Background music: Use --bg-music and --bg-music-volume

-   Cleanup: Use --cleanup to remove temporary files after generation

-   TTS provider selection: Use --tts-provider to choose between 'elevenlabs', 'openai', or 'deepgram'

API Keys
--------

Set up the following environment variables:

-   OPENAI_API_KEY: For OpenAI services (GPT, DALL-E, TTS)

-   ELEVENLABS_API_KEY or XI_API_KEY: For ElevenLabs TTS

-   DEEPGRAM_API_KEY: For DeepGram TTS

Alternatively, provide API keys via command-line arguments.

Examples
--------

1. Generate video with text-to-speech and generated image:

   python imagevideo.py --audio generate --text "Hello, world!" --image generate

2. Use YouTube audio with local images:

   python imagevideo.py --audio https://www.youtube.com/watch?v=dQw4w9WgXcQ --image path/to/image1.png,path/to/image2.jpg

3. Generate video with specific TTS provider and voice:

   python imagevideo.py --audio generate --text "Hello, world!" --tts-provider openai --voice-id alloy

Notes
-----

-   The script handles various combinations of inputs and attempts to create a coherent video output

-   For complex input combinations (multiple images and videos), results may vary

-   Use the --cleanup flag to remove temporary files after video generation

For more detailed information about the video generation rules and implementation notes, refer to the script's documentation comments.

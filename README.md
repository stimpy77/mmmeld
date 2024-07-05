# `mmmeld` - Multimedia Meld - Audio/Image Video Generator
Creates a video consisting of an image/video and provided audio. The original purpose was to "video-ize" a music file.

Can produce speech from text if no audio provided. Can produce an image if no image provided. 

Audio or image or video can come from local file or from YouTube URL. Multiple images can be provided to create a slideshow. 

If a video asset is referenced for the "image", only the video is used from that asset, not the audio. If multiple videos are provided, they are treated as a sequence and looped. 

If images and videos are provided, .. LOL well good luck and have fun.

There is a 0.5 second before and 2 seconds after silence buffer, and the visual component will fade out during those final 2 seconds of silence.

## Installation:

Install ffmpeg and ensure it is in your operating system's PATH. See: https://ffmpeg.org/

Install Python and run the following command:

```_bash
pip install openai pillow requests tqdm pytube elevenlabs yt-dlp deepgram-sdk aiohttp
```

## To use:
```_bash
python ./mmmeld.py
```

Answer the questions. 

`Enter the path to the audio file, YouTube video URL, or press Enter to generate speech:` **`myaudio.wav`**

`Enter path/URL to image/video file (press Enter to generate):` **`myimage.png`**

`Enter the path for the output video file (press Enter for default: myvideo.mp4):` **`My Fantastic Video.mp4`**

### Command-line arguments

You don't have to be prompted.

```
❯ python .\mmmeld.py --help
usage: mmmeld.py [-h] [--image IMAGE] [--audio AUDIO] [--output OUTPUT] [--text TEXT]
                     [--image_description IMAGE_DESCRIPTION] [--bg-music BG_MUSIC] [--bg-music-volume BG_MUSIC_VOLUME]
                     [--cleanup] [--autofill] [--voice-id VOICE_ID] [--tts-provider {elevenlabs,openai,deepgram}]
                     [--openai-key OPENAI_KEY] [--elevenlabs-key ELEVENLABS_KEY] [--deepgram-key DEEPGRAM_KEY]

Generate a video from audio and image/video, with options for text-to-speech, image generation, and background music.

options:
  -h, --help            show this help message and exit
  --image IMAGE         Path to image/video file(s), URL(s), or 'generate'. Use comma-separated list for multiple
                        inputs.
  --audio AUDIO         Path to audio file, YouTube URL, or 'generate' for text-to-speech.
  --output OUTPUT       Path for the output video file. Default is based on audio filename.
  --text TEXT           Text for speech generation (used if audio is 'generate').
  --image_description IMAGE_DESCRIPTION
                        Description for image generation (used if image is 'generate').
  --bg-music BG_MUSIC   Path to background music file or YouTube URL.
  --bg-music-volume BG_MUSIC_VOLUME
                        Volume of background music (0.0 to 1.0). Default: 0.2
  --cleanup             Clean up temporary files after video generation.
  --autofill            Use defaults for all unspecified options, no prompts.
  --voice-id VOICE_ID   ElevenLabs voice ID. Default: WWr4C8ld745zI3BiA8n7
  --tts-provider {elevenlabs,openai,deepgram}
                        Text-to-speech provider (default: elevenlabs)

API Keys:
  --openai-key OPENAI_KEY
                        OpenAI API key. Default: Use OPENAI_API_KEY environment variable.
  --elevenlabs-key ELEVENLABS_KEY
                        ElevenLabs API key. Default: Use ELEVENLABS_API_KEY environment variable.
  --deepgram-key DEEPGRAM_KEY
                        DeepGram API key. Default: Use DEEPGRAM_API_KEY environment variable.

Examples:
  Generate video from local audio and multiple image/video files:
    python mmmeld.py --audio path/to/audio.mp3 --image path/to/image1.png,path/to/video1.mp4,path/to/image2.jpg

  Generate video with text-to-speech, generated image, additional images/videos, and background music:
    python mmmeld.py --audio generate --text "Hello, world!" --image generate,path/to/video1.mp4,https://example.com/image.jpg --bg-music path/to/music.mp3

  Download YouTube audio, use multiple images/videos, and add background music from YouTube:
    python mmmeld.py --audio https://www.youtube.com/watch?v=dQw4w9WgXcQ --image path/to/image1.png,https://example.com/video.mp4 --bg-music https://www.youtube.com/watch?v=background_music_id

  Generate video with specific ElevenLabs voice ID:
    python mmmeld.py --audio generate --text "Hello, world!" --voice-id your_voice_id_here

  Run interactively (no arguments):
    python mmmeld.py
```

If you want anything to be automatically generated, you will need the following environment variables set up on your operating system:

- `OPENAI_API_KEY`: The API key to use OpenAI services such as GPT (text generation), DALL-E (image generation), and text-to-speech.
- `ELEVENLABS_API_KEY` OR `XI_API_KEY`: The API key provided by ElevenLabs for text-to-speech. You can find it by clicking on your avatar on their web site. 
- `DEEPGRAM_API_KEY`: The API key provided by DeepGram for text-to-speech.

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

## New Features and Improvements

- Support for multiple text-to-speech providers: ElevenLabs, OpenAI, and DeepGram
- Improved handling of special characters in filenames
- Option to clean up temporary files (including chunked audio files) with --cleanup flag
- Better integration of generated speech title and description for image generation
- Enhanced error handling and logging

## Implementation Notes

- Uses ffmpeg for video generation and audio processing
- Leverages OpenAI's DALL-E for image generation
- Supports YouTube video/audio downloads

## Future Considerations

- Custom durations for images/videos
- Transition effects
- 'Ken Burns' effect
- Option to use video length instead of audio for total duration
- Command-line flag for exact total timeline time
- Allowing users to specify custom durations for each image/video

Remember: The goal is a simple way for users to create a collage of audio-backed images and/or videos, prioritizing audio content for platforms like YouTube that require visuals.

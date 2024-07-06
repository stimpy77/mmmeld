# `mmmeld` - Multimedia Meld - Audio/Image Video Generator

Creates a video consisting of images/videos and provided audio. The primary purpose is to "video-ize" audio content, particularly useful for platforms like YouTube that require visual components.

## Key Features:

- Generates speech from text if no audio is provided
- Creates an image if no image is provided
- Supports audio/image/video from local files or YouTube URLs
- Handles multiple images to create a slideshow effect
- Processes video assets for visuals only, not audio
- Adds a 0.5-second lead-in and 2-second fade-out to background music and visuals (optional, customizable)
- Can generate videos without main audio, using only images/videos and optional background music

## Installation:

1. Install ffmpeg and ensure it's in your system PATH. See: https://ffmpeg.org/
2. Install Python and required packages:

```bash
pip install openai pillow requests tqdm pytube elevenlabs yt-dlp deepgram-sdk aiohttp moviepy
```

## Setup

### Mac/Linux
To set up `mmmeld` for easy command-line access on Mac or Linux:

1. Make sure you're in the directory containing the `mmmeld.py` file.
2. Run the setup script:

```bash
chmod +x setup_mmmeld.sh
./setup_mmmeld.sh
```

3. Restart your terminal or run `source ~/.bashrc` (or `source ~/.zshrc` if you're using zsh) to apply the changes.

### Windows
To set up `mmmeld` for easy command-line access on Windows:

1. Open PowerShell as an administrator.
2. Navigate to the directory containing the `mmmeld.py` file.
3. Run the setup script:

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.\Setup-Mmmeld.ps1
```

4. Close and reopen PowerShell to apply the changes.

After setup, you can run `mmmeld` from any directory in your terminal or PowerShell.

## Usage:

Basic interactive mode:
```bash
❯ mmmeld
```

Follow the prompts to specify audio, image, and output options.

### Command-line Arguments:

For non-interactive use, mmmeld supports various command-line arguments. You can view all available options by running:

```bash
mmmeld --help
```

This will display the following help information:

```
usage: mmmeld [-h]
              [--audio AUDIO]
              [--text TEXT]
              [--image IMAGE]
              [--image_description IMAGE_DESCRIPTION]
              [--bg-music BG_MUSIC]
              [--bg-music-volume BG_MUSIC_VOLUME]
              [--output OUTPUT]
              [--cleanup]
              [--autofill]
              [--voice-id VOICE_ID]
              [--tts-provider {elevenlabs,openai,deepgram}]
              [--openai-key OPENAI_KEY]
              [--elevenlabs-key ELEVENLABS_KEY]
              [--deepgram-key DEEPGRAM_KEY]
              [--audiomargin AUDIOMARGIN]

options:
  -h, --help            show this help message and exit
  --audio AUDIO         Path to audio file, YouTube URL, or 'generate' for text-to-speech.
  --text TEXT           Text for speech generation (used if audio is 'generate').
  --image IMAGE         Path to image/video file(s), URL(s), or 'generate'. Use comma-separated list for multiple inputs.
  --image_description IMAGE_DESCRIPTION
                        Description for image generation (used if image is 'generate').
  --bg-music BG_MUSIC   Path to background music file or YouTube URL.
  --bg-music-volume BG_MUSIC_VOLUME
                        Volume of background music (0.0 to 1.0). Default: 0.2
  --output OUTPUT       Path for the output video file. Default is based on audio filename.
  --cleanup             Clean up temporary files after video generation.
  --autofill            Use defaults for all unspecified options, no prompts.
  --voice-id VOICE_ID   ElevenLabs voice ID. Default: WWr4C8ld745zI3BiA8n7
  --tts-provider {elevenlabs,openai,deepgram}
                        Text-to-speech provider (default: elevenlabs)
  --openai-key OPENAI_KEY
                        OpenAI API key. Default: Use OPENAI_API_KEY environment variable.
  --elevenlabs-key ELEVENLABS_KEY
                        ElevenLabs API key. Default: Use ELEVENLABS_API_KEY environment variable.
  --deepgram-key DEEPGRAM_KEY
                        DeepGram API key. Default: Use DEEPGRAM_API_KEY environment variable.
  --audiomargin AUDIOMARGIN
                        Start and end audio margins in seconds, comma-separated. Default: 0.5,2.0
```

### New Feature: Optional Audio Input

You can now create videos without specifying an audio input. In this case, the video duration will be determined by the input images and videos:

```bash
mmmeld --image path/to/image1.png,path/to/video1.mp4,path/to/image2.jpg
```

This will create a video using the specified images and video, with each image displayed for 5 seconds and the video played at its original duration.

### New Feature: Custom Audio Margins

You can now specify custom start and end margins for the audio using the `--audiomargin` parameter:

```bash
mmmeld --audio path/to/audio.mp3 --image path/to/image.png --audiomargin 1.0,3.0
```

This will add a 1-second lead-in and a 3-second fade-out to the main audio. The default value is "0.5,2.0" (0.5-second lead-in and 2-second fade-out).

## Examples:

1. Generate video from local audio and multiple image/video files:
```bash
mmmeld --audio path/to/audio.mp3 --image path/to/image1.png,path/to/video1.mp4,path/to/image2.jpg
```

2. Generate video with text-to-speech, AI-generated image, and background music:
```bash
mmmeld --audio generate --text "Hello, world!" --image generate,path/to/video1.mp4 --bg-music path/to/music.mp3
```

3. Use YouTube audio, multiple images/videos, and YouTube background music:
```bash
mmmeld --audio https://www.youtube.com/watch?v=dQw4w9WgXcQ --image path/to/image1.png,https://example.com/video.mp4 --bg-music https://www.youtube.com/watch?v=background_music_id
```

4. Generate video from local audio and multiple image/video files with custom audio margins (1 second lead-in, 3 seconds out):
```bash
mmmeld --audio path/to/audio.mp3 --image path/to/image1.png,path/to/video1.mp4,path/to/image2.jpg --audiomargin 1.0,3.0
```

## Recent Improvements:

- Multiple text-to-speech provider support (ElevenLabs, OpenAI, DeepGram)
- Enhanced handling of special characters in filenames
- Temporary file cleanup option (--cleanup flag)
- Improved integration of generated speech metadata for image generation
- Enhanced error handling and logging

## Implementation Notes:

- Uses ffmpeg for video generation and audio processing
- Leverages OpenAI's DALL-E for image generation
- Supports YouTube video/audio downloads

Remember: The goal is to provide a simple way for users to create audio-backed visual content, prioritizing audio for platforms that require visual components.

## Detailed Functionality

### Audio Processing
- Supports local audio files, YouTube URLs, and text-to-speech generation
- Handles various audio formats (WAV, MP3, etc.) using ffmpeg
- Adds a 0.5-second lead-in and 2-second tail to the main audio (customizable)
- Optionally includes background music with volume adjustment and fade-out

### Image and Video Processing
- Accepts local image/video files, URLs, and can generate images using DALL-E
- Supports multiple input formats (PNG, JPG, MP4, etc.)
- Creates a slideshow effect when multiple images are provided
- Loops shorter videos to match audio duration when main audio is present
- Cuts longer videos to fit within the audio timeframe when main audio is present

### Video Generation Rules
1. Total video duration = main audio duration + lead-in + tail (if main audio is provided)
   - Lead-in default (configurable from command line): 0.5s
   - Tail default (configurable from command line): 2s
2. Single image: 
   - With main audio: Displayed for the entire duration
   - Without main audio: Displayed for 5 seconds
3. Single video: 
   - With main audio: Looped if shorter than audio, cut if longer
   - Without main audio: Played once with its own audio
4. Multiple videos, no images:
   - With main audio:
     - If total video time <= audio time: Play in sequence, then loop
     - If total video time > audio time: Play in sequence, cut at audio end
   - Without main audio: Play in sequence once
5. Videos + images, with main audio:
   - If total video time < audio time:
     - Play videos once in sequence
     - Distribute remaining time equally among images
   - If total video time >= audio time:
     - Distribute 5 seconds each to image
     - Truncate sequence to fit audio
6. Videos + images, without main audio:
   - Play videos in sequence
   - Show each image for 5 seconds
7. Image + video:
   - With main audio:
     - End of video is "anchored" to the end of the audio
     - Image shown first, filling the remaining time
     - If video longer than audio: Minimum 5s for image, then video (cut off)
   - Without main audio:
     - Image shown for 5 seconds, then video plays in full
8. Multiple images, no videos:
   - With main audio: Equal time for each, no looping
   - Without main audio: 5 seconds for each image
9. Margin and fade-out:
   - Main audio margin (lead-in and tail, configurable from command line) is only applied when main audio is present
   - The tail margin duration is configurable and determines the fade-out duration
   - Fade-out is applied to background music and visuals during the tail margin
   - No fade-out effect is applied to main audio
   - There is no fade-out functionality applied anywhere when there is no main audio because 
     fade-out is associated with the main audio margin.
   - Note: The default 2-second tail margin mentioned above also serves as the default fade-out
     duration for background music and visuals. This duration can be customized using the 
     --audiomargin parameter, where the second value represents both the tail margin and fade-out 
     duration.
10. Background music:
    - With main audio: Loops and fades out at the end of the main audio (including margin)
    - Without main audio: Loops and fades out at the end of the visual sequence

Note: When main audio is provided, it always determines the total duration of the output. The visual sequence will be cut off (with fade-out) if it's longer than the main audio duration (including margins). When no main audio is provided, the visual sequence determines the total duration.

### Supported File Formats
- Audio: WAV, MP3, M4A, and other formats supported by ffmpeg
- Images: PNG, JPG, JPEG, GIF, and other formats supported by Pillow
- Video: MP4, AVI, MOV, and other formats supported by ffmpeg

## AI-Powered Features
- Text-to-Speech: Utilizes ElevenLabs, OpenAI, or DeepGram for high-quality voice generation
- Image Generation: Uses DALL-E to create images based on text descriptions
- Content Enhancement: Leverages GPT models for title shortening and content description

## Limitations and Known Issues
- Large files may require significant processing time and memory
- YouTube content access is subject to the platform's policies and may change
- AI-generated content quality can vary and may require manual review
- Background music looping might create noticeable seams for short audio clips
- When no main audio is provided, the visual sequence determines the total duration

## Troubleshooting
1. **ffmpeg not found**: Ensure ffmpeg is installed and added to your system PATH
2. **API key errors**: Verify that you've set up the required API keys as environment variables
3. **File permission issues**: Check that you have read/write access to the input and output directories
4. **Memory errors**: For large files, try processing in smaller chunks or on a machine with more RAM
5. **Unsupported file formats**: Convert your input files to a supported format using a tool like ffmpeg

For more specific issues, please check the project's issue tracker on GitHub or submit a new issue with a detailed description of the problem and your system configuration.

## Performance Considerations
- Processing time scales with input file sizes and complexity of operations
- CPU-intensive tasks include video encoding and AI-based generation
- Consider using SSD storage for faster file I/O operations

## Advanced Usage
### Custom Voice Selection
For ElevenLabs TTS:
```bash
mmmeld --audio generate --text "Your text here" --voice-id custom_voice_id
```

### Chaining Multiple Videos
To create a sequence of videos with different audio and visuals:
```bash
mmmeld --audio audio1.mp3 --image video1.mp4 --output part1.mp4
mmmeld --audio audio2.mp3 --image video2.mp4 --output part2.mp4
ffmpeg -f concat -i <(for f in part*.mp4; do echo "file '$f'"; done) -c copy final_output.mp4
```

## Contributing
Contributions to mmmeld are welcome! Please follow these steps:
1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to your branch
5. Create a new Pull Request

Please ensure your code adheres to the project's coding standards and includes appropriate tests.

## License
This project is licensed under the MIT License - see the ~~[LICENSE](LICENSE)~~ file for details.

## Acknowledgments
- ffmpeg developers for their powerful multimedia framework
- OpenAI for GPT and DALL-E capabilities
- ElevenLabs, OpenAI, and DeepGram for text-to-speech technologies
- YouTube for providing access to a vast library of audio and video content

## Frequently Asked Questions (FAQ)

1. **Q: Can I use mmmeld for commercial projects?**
   A: Yes, mmmeld is ~~licensed under MIT~~ (whatever), allowing commercial use. However, ensure you comply with the terms of the APIs and services it uses (e.g., OpenAI, ElevenLabs).

2. **Q: How can I improve the quality of AI-generated images?**
   A: Provide detailed, descriptive prompts. Experiment with different phrasings and include specific style references for better results.

3. **Q: Is there a way to preview the video before final rendering?**
   A: Currently, there's no built-in preview feature. Consider generating a low-resolution version first for preview purposes.

4. **Q: Can mmmeld handle 4K or higher resolution videos?**
   A: Yes, but processing time and resource usage will increase significantly. Ensure your system has adequate CPU, RAM, and storage.

5. **Q: How do I report bugs or request features?**
   A: Please use the GitHub Issues page for the project. Provide as much detail as possible, including your system specs and steps to reproduce any bugs.

## Best Practices

1. **Organize Your Assets**: Keep your audio, image, and video files in well-structured directories for easier management.

2. **Use Descriptive Filenames**: This helps in identifying content and can be used for automatic title generation.

3. **Backup Original Files**: Always work with copies of your original media files to prevent accidental loss or modification.

4. **Monitor Resource Usage**: Keep an eye on CPU, RAM, and disk usage, especially when processing large files or batches.

5. **Optimize Input Files**: Compress large images and videos before input to reduce processing time and resource usage.

6. **Experiment with AI Settings**: Try different text-to-speech voices and image generation prompts to find what works best for your content.

7. **Version Control Your Scripts**: If you're creating complex automation scripts using mmmeld, use version control to track changes.

## Future Roadmap

- Implement a graphical user interface (GUI) for easier operation
- Add support for more complex video transitions and effects
- Integrate with cloud storage services for easier file management
- Develop a web-based version for online video creation
- Implement batch processing for handling multiple videos in one go
- Add support for custom fonts and text overlays in videos
- Develop a plugin system for extending functionality

We welcome community input on prioritizing these features. Please use the GitHub Discussions page to share your thoughts and ideas for the future of mmmeld.
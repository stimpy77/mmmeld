# `mmmeld` - Multimedia Meld - Audio/Image Video Generator

Creates a video consisting of images/videos and provided audio. The primary purpose is to "video-ize" audio content, particularly useful for platforms like YouTube that require visual components.

## Key Features:

- Generates speech from text if no audio is provided
- Creates an image if no image is provided
- Supports audio/image/video from local files or YouTube URLs
- Handles multiple images to create a slideshow effect
- Processes video assets for visuals only, not audio
- Adds a 0.5-second lead-in and 2-second fade-out (optional, customizable)

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
              [--image IMAGE]
              [--audio AUDIO]
              [--output OUTPUT]
              [--text TEXT]
              [--image_description IMAGE_DESCRIPTION]
              [--bg-music BG_MUSIC]
              [--bg-music-volume BG_MUSIC_VOLUME]
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
  --image IMAGE         Path to image/video file(s), URL(s), or 'generate'. Use comma-separated list for multiple inputs.
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
  --openai-key OPENAI_KEY
                        OpenAI API key. Default: Use OPENAI_API_KEY environment variable.
  --elevenlabs-key ELEVENLABS_KEY
                        ElevenLabs API key. Default: Use ELEVENLABS_API_KEY environment variable.
  --deepgram-key DEEPGRAM_KEY
                        DeepGram API key. Default: Use DEEPGRAM_API_KEY environment variable.
  --audiomargin AUDIOMARGIN
                        Start and end audio margins in seconds, comma-separated. Default: 0.5,2.0
```

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

## Future Considerations:

- Custom durations for individual images/videos
- Transition effects between visuals
- 'Ken Burns' effect for static images
- Option to use video length instead of audio for total duration
- Command-line flag for specifying exact total timeline duration

Remember: The goal is to provide a simple way for users to create audio-backed visual content, prioritizing audio for platforms that require visual components.

## Detailed Functionality

### Audio Processing
- Supports local audio files, YouTube URLs, and text-to-speech generation
- Handles various audio formats (WAV, MP3, etc.) using ffmpeg
- Adds a 0.5-second lead-in and 2-second fade-out to the main audio (optional, customizable)
- Optionally includes background music with volume adjustment and fade-out

### Image and Video Processing
- Accepts local image/video files, URLs, and can generate images using DALL-E
- Supports multiple input formats (PNG, JPG, MP4, etc.)
- Creates a slideshow effect when multiple images are provided
- Loops shorter videos to match audio duration
- Cuts longer videos to fit within the audio timeframe

### Video Generation Rules
1. Total video duration = main audio duration + 0.5s lead-in + 2s tail
2. Single image: Displayed for the entire duration
3. Single video: Looped if shorter than audio, cut if longer
4. Multiple videos, no images:
   - If total video time <= audio time: Play in sequence, then loop
   - If total video time > audio time: Play in sequence, cut at audio end
5. Videos + images, total video time < audio time:
   - Play videos once in sequence
   - Distribute remaining time equally among images
6. Videos + images, total video time >= audio time:
   - Adjust durations to fit audio time
   - Video inputs start at the tail end of the total timespan
7. Only images: Equal time for each, no looping
8. Image + video:
   - If video shorter than audio: Image shown first, then video
   - If video longer than audio: Minimum 5s for image, then video (cut off)

## Supported File Formats
- Audio: WAV, MP3, M4A, and other formats supported by ffmpeg
- Images: PNG, JPG, JPEG, GIF (first frame only), and other formats supported by Pillow
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
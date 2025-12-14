#!/usr/bin/env python3
"""
Audio to Image Prompt Generator using Google Gemini
Analyzes audio files to extract musical characteristics and generates 
detailed image prompts for AI image generators like Ideogram.
"""

import os
import sys
import time
import argparse
import json
import warnings

# Suppress warnings about Python version and SSL
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', message='urllib3')

# Fix for importlib.metadata compatibility
try:
    import importlib.metadata as importlib_metadata
except ImportError:
    import importlib_metadata

# Patch for older Python versions
if not hasattr(importlib_metadata, 'packages_distributions'):
    def packages_distributions():
        pkg_to_dist = {}
        for dist in importlib_metadata.distributions():
            if dist.files:
                for file in dist.files:
                    if file.suffix == ".py" and "/" not in str(file):
                        pkg = file.stem
                        pkg_to_dist.setdefault(pkg, []).append(dist.metadata.get("Name"))
        return pkg_to_dist
    importlib_metadata.packages_distributions = packages_distributions

import google.generativeai as genai

# --- CONFIGURATION ---
# Set this as an environment variable: export GEMINI_API_KEY="your_key"
API_KEY = os.getenv("GEMINI_API_KEY")

# You can change this to other models like "gemini-1.5-pro" or "gemini-1.5-flash"
MODEL_NAME = "gemini-2.0-flash-exp" 

def setup_client():
    """Configure the Gemini API client."""
    if not API_KEY:
        raise ValueError("Error: GEMINI_API_KEY environment variable not found.")
    genai.configure(api_key=API_KEY)

def upload_and_wait(audio_path, quiet=False):
    """
    Uploads the file to Google's Gen AI file storage and waits 
    until it is processed and in the 'ACTIVE' state.
    """
    if not quiet:
        print(f"Uploading {audio_path}...")
    audio_file = genai.upload_file(path=audio_path)
    
    if not quiet:
        print(f"Processing audio file: {audio_file.name}...")
    while audio_file.state.name == "PROCESSING":
        if not quiet:
            print(".", end="", flush=True)
        time.sleep(2)
        audio_file = genai.get_file(audio_file.name)
        
    if audio_file.state.name != "ACTIVE":
        raise Exception(f"File upload failed with state: {audio_file.state.name}")
    
    if not quiet:
        print("\nFile is ready.")
    return audio_file

def generate_ideogram_prompt(audio_file, notes, title, style_preference="auto", quiet=False):
    """
    Sends the audio and context to Gemini to generate the image prompt.
    
    Args:
        audio_file: The uploaded audio file object
        notes: Context notes about the song
        title: Title of the track
        style_preference: Style preference for the image (auto, photorealistic, artistic, etc.)
        quiet: If True, suppress progress messages
    """
    model = genai.GenerativeModel(MODEL_NAME)

    # Enhanced prompt engineering for better visual prompts
    system_instruction = f"""
    You are an expert art director and prompt engineer specializing in AI image generation, particularly for Ideogram.ai. 
    
    Your task:
    1. Listen carefully to the provided audio file. Analyze:
       - Genre and subgenre
       - Tempo and rhythm (BPM if identifiable)
       - Key instrumentation and timbres
       - Mood and emotional atmosphere
       - Energy level and dynamics
       - Any notable sonic textures or effects
       - If there are lyrics, note their themes (but don't transcribe them)
    
    2. Consider the user's context:
       - Title: "{title}"
       - Notes: "{notes}"
       - Style preference: {style_preference}
    
    3. Create a highly descriptive, single-paragraph image prompt that:
       - Translates the audio's "feeling" into visual equivalents
       - Uses synesthesia to map sonic qualities to visual elements
       - Includes specific details about:
         * Art Style (e.g., Cyberpunk, Oil Painting, 3D Render, Cinematic Photography, Watercolor, Digital Art)
         * Lighting (e.g., Neon glow, Golden hour, Moody shadows, Studio lighting, Bioluminescent)
         * Color Palette (derive from the music's emotional "color")
         * Composition and perspective
         * Subject matter and focal points
         * Atmosphere and environment
         * Texture and material qualities
       - Incorporates the title/notes thematically without being too literal
       - Is optimized for Ideogram's strengths (clear subjects, dramatic lighting, artistic styles)
    
    4. If the music has a clear genre association, incorporate genre-appropriate visual motifs:
       - Electronic/EDM: Neon cities, digital landscapes, geometric patterns
       - Classical: Grand halls, nature scenes, abstract emotional landscapes
       - Jazz: Smoky lounges, urban nights, impressionistic scenes
       - Rock: Raw energy, industrial elements, dramatic landscapes
       - Ambient: Ethereal spaces, abstract flows, cosmic vistas
       - Hip-hop: Urban environments, bold graphics, street art aesthetics
    
    Output ONLY the raw prompt string, no conversational text or explanations.
    Make it vivid, specific, and visually compelling.
    """

    if not quiet:
        print("Analyzing audio and generating prompt...")
    response = model.generate_content(
        [audio_file, system_instruction],
        request_options={"timeout": 600}  # Audio analysis can take a moment
    )

    return response.text

def save_prompt_to_file(prompt, audio_path, title):
    """Save the generated prompt to a text file alongside the audio."""
    base_name = os.path.splitext(audio_path)[0]
    output_path = f"{base_name}_ideogram_prompt.txt"
    
    with open(output_path, 'w') as f:
        f.write(f"Title: {title}\n")
        f.write(f"Audio: {os.path.basename(audio_path)}\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("-" * 50 + "\n")
        f.write(prompt)
    
    print(f"\nPrompt saved to: {output_path}")
    return output_path

def main():
    parser = argparse.ArgumentParser(
        description="Generate Ideogram image prompts from Audio files using Gemini.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "path/to/song.mp3" --title "Midnight Drive"
  %(prog)s "remix.wav" --title "Energy Burst" --notes "Upbeat electronic dance track"
  %(prog)s "audio.mp3" --title "Peaceful Morning" --style artistic --save
        """
    )
    
    parser.add_argument("audio_file", help="Path to the audio file (mp3, wav, aac, etc.)")
    parser.add_argument("--title", default="Untitled", help="Title of the track")
    parser.add_argument("--notes", default="", help="Context notes (genre, mood, themes)")
    parser.add_argument("--style", default="auto", 
                       choices=["auto", "photorealistic", "artistic", "abstract", "cinematic"],
                       help="Preferred visual style")
    parser.add_argument("--save", action="store_true", 
                       help="Save prompt to a text file")
    parser.add_argument("--json", action="store_true",
                       help="Output in JSON format")
    
    args = parser.parse_args()

    # Expand the path (handle ~)
    audio_path = os.path.expanduser(args.audio_file)
    
    # Validate audio file exists
    if not os.path.exists(audio_path):
        print(f"Error: Audio file '{audio_path}' not found.")
        return 1

    try:
        setup_client()
        
        # Use quiet mode for JSON output
        quiet = args.json
        
        # 1. Upload File
        uploaded_file = upload_and_wait(audio_path, quiet=quiet)
        
        # 2. Generate Prompt
        prompt = generate_ideogram_prompt(
            uploaded_file, 
            args.notes, 
            args.title,
            args.style,
            quiet=quiet
        )
        
        # 3. Output
        if args.json:
            output = {
                "title": args.title,
                "audio_file": audio_path,
                "style": args.style,
                "prompt": prompt.strip(),
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
            }
            print(json.dumps(output, indent=2))
        else:
            print("\n" + "=" * 60)
            print("IDEOGRAM PROMPT")
            print("=" * 60)
            print(prompt.strip())
            print("=" * 60)
        
        # 4. Save to file if requested
        if args.save:
            save_prompt_to_file(prompt, audio_path, args.title)
        
        # 5. Cleanup: Delete the file from the cloud
        try:
            uploaded_file.delete()
        except:
            pass  # Silent fail on cleanup
        
        return 0
        
    except Exception as e:
        # For JSON mode, output error in JSON format
        if args.json:
            error_output = {
                "error": str(e),
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
            }
            print(json.dumps(error_output, indent=2), file=sys.stderr)
        else:
            print(f"\nAn error occurred: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    exit(main())
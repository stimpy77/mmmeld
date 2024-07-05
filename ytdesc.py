import os
import pickle
import argparse
import json
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openai import OpenAI

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# Try to import youtube_transcript_api
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    logger.warning("youtube_transcript_api is not installed. Transcript fetching will be disabled.")
    TRANSCRIPT_API_AVAILABLE = False

def get_authenticated_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('youtube', 'v3', credentials=creds)

def get_channel_info(youtube, channel_id):
    logger.info(f"Fetching channel info for channel ID: {channel_id}")
    request = youtube.channels().list(part='snippet', id=channel_id)
    response = request.execute()
    return response['items'][0]['snippet']['description']

def get_video_info(youtube, video_id):
    logger.info(f"Fetching video info for video ID: {video_id}")
    request = youtube.videos().list(part='snippet,contentDetails', id=video_id)
    response = request.execute()
    return response['items'][0]['snippet']

def get_video_transcript(video_id):
    if not TRANSCRIPT_API_AVAILABLE:
        logger.warning(f"Transcript fetching is disabled. Skipping transcript for video ID: {video_id}")
        return None

    logger.info(f"Fetching transcript for video ID: {video_id}")
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        full_transcript = " ".join([entry['text'] for entry in transcript])
        logger.info(f"Transcript fetched successfully for video ID: {video_id}")
        return full_transcript
    except Exception as e:
        logger.error(f"An error occurred while fetching the transcript for video {video_id}: {str(e)}")
        return None

def generate_ai_description(openai_api_key, transcript, title, channel_description, upsell_links, model="gpt-4"):
    logger.info(f"Generating AI description for video: {title}")
    client = OpenAI(api_key=openai_api_key)
    
    upsell_links_str = ""
    if upsell_links:
        upsell_links_str = "Upsell Links:\n" + "\n".join([f"- {key}: {value}" for key, value in upsell_links.items()])

    prompt = f"""
    Create a YouTube video description based on the following information:
    
    Video Title: {title}
    Channel Description: {channel_description}
    Transcript: {transcript if transcript else 'Not available'}
    {upsell_links_str}

    The description should:
    1. Be engaging and capture the essence of the video
    2. Include relevant keywords for SEO without being spammy
    3. Encourage viewers to engage (like, comment, subscribe)
    4. Be between 100-200 words
    5. Include 3-5 relevant hashtags at the end
    6. If upsell links are provided, incorporate them naturally into the description

    Format the description with appropriate line breaks for readability.
    """

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that creates engaging YouTube video descriptions."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        n=1,
        stop=None,
        temperature=0.7,
    )

    logger.info(f"AI description generated for video: {title}")
    return response.choices[0].message.content.strip()

def update_video_description(youtube, video_id, new_description, category_id):
    logger.info(f"Updating description for video ID: {video_id}")
    try:
        # First, get the existing video details
        video_response = youtube.videos().list(
            part='snippet',
            id=video_id
        ).execute()

        if not video_response['items']:
            logger.error(f"Video not found: {video_id}")
            return None

        # Get the existing snippet
        snippet = video_response['items'][0]['snippet']

        # Update only the description and category
        snippet['description'] = new_description
        snippet['categoryId'] = str(category_id)  # Ensure category_id is a string

        # Update the video with the new snippet
        request = youtube.videos().update(
            part="snippet",
            body={
                "id": video_id,
                "snippet": snippet
            }
        )
        response = request.execute()
        logger.info(f"Description updated successfully for video ID: {video_id}")
        return response
    except HttpError as e:
        error_content = json.loads(e.content.decode('utf-8'))
        logger.error(f"An HTTP error occurred: {e}")
        logger.error(f"Error details: {error_content}")
        if e.resp.status == 403:
            logger.error("This could be due to insufficient permissions. Please ensure you're using an account with appropriate access to this channel.")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        return None

def pause_execution(args):
    if args.pause:
        while True:
            user_input = input("Press Enter to continue to the next video, 'R' to run without further pauses, or 'Q' to quit: ").strip().lower()
            if user_input == '':
                return True
            elif user_input == 'r':
                logger.info("Continuing without further pauses")
                args.pause = False
                return True
            elif user_input == 'q':
                logger.info("Quitting the script")
                return False
    return True

def main(args):
    if not args.openai_api_key:
        logger.error("OpenAI API key is missing. Please provide it using the --openai_api_key argument or set the OPENAI_API_KEY environment variable.")
        return

    try:
        youtube = get_authenticated_service()
        channel_description = get_channel_info(youtube, args.channel_id)

        # Parse upsell links if provided
        upsell_links = {}
        if args.upsell_links:
            try:
                upsell_links = json.loads(args.upsell_links)
                if not isinstance(upsell_links, dict):
                    raise ValueError("Upsell links must be a JSON object")
            except json.JSONDecodeError:
                logger.error("Invalid JSON format for upsell links. Please provide a valid JSON object.")
                return
            except ValueError as e:
                logger.error(str(e))
                return

        logger.info(f"Fetching videos for channel ID: {args.channel_id}")
        request = youtube.search().list(part='id', type='video', channelId=args.channel_id, maxResults=args.max_videos)
        response = request.execute()

        for item in response['items']:
            video_id = item['id']['videoId']
            video_info = get_video_info(youtube, video_id)
            
            if not video_info['description'] or args.force_update:
                logger.info(f"Processing video: {video_info['title']} (ID: {video_id})")
                
                transcript = get_video_transcript(video_id) if TRANSCRIPT_API_AVAILABLE else None
                new_description = generate_ai_description(args.openai_api_key, transcript, video_info['title'], channel_description, upsell_links, args.openai_model)
                
                logger.info(f"New description for video {video_id}:\n{new_description}")
                
                if pause_execution(args):
                    update_video_description(youtube, video_id, new_description, args.category_id)
                    logger.info(f"Updated description for video: {video_info['title']} (ID: {video_id})")
                else:
                    break
            else:
                logger.info(f"Skipping video with existing description: {video_info['title']} (ID: {video_id})")

            if not pause_execution(args):
                break

    except HttpError as e:
        error_content = json.loads(e.content.decode('utf-8'))
        logger.error(f"An HTTP error occurred: {e}")
        logger.error(f"Error details: {error_content}")
        if e.resp.status == 403:
            logger.error("This could be due to insufficient permissions. Please ensure you're using an account with appropriate access to this channel.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")

    logger.info("Script execution completed")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Update YouTube video descriptions using AI-generated content.")
    parser.add_argument('--channel_id', default='UCY9XO3gfKgvr94KSSbDu2uA', help="YouTube channel ID")
    parser.add_argument('--category_id', type=int, default=10, help="YouTube video category ID")
    parser.add_argument('--openai_api_key', default=os.getenv("OPENAI_PERSONAL_API_KEY") or os.getenv("OPENAI_API_KEY"), help="OpenAI API key")
    parser.add_argument('--openai_model', default="gpt-4", help="OpenAI model to use")
    parser.add_argument('--max_videos', type=int, default=50, help="Maximum number of videos to process")
    parser.add_argument('--force_update', action='store_true', help="Update all video descriptions, even if they already exist")
    parser.add_argument('--pause', action='store_true', help="Pause after each video for user input")
    parser.add_argument('--upsell_links', type=str, help="JSON string of upsell links, e.g., '{\"buy album\": \"http://amazon_link/\", \"listen on Spotify\": \"http://spotify_link\"}'")
    
    args = parser.parse_args()
    main(args)


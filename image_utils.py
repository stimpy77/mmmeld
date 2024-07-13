from file_utils import download_image, generate_image
import logging
from file_utils import sanitize_filename
from openai import OpenAI
from PIL import Image
from io import BytesIO
import requests
import os

def get_image_inputs(args, title, description, files_to_cleanup):
    logging.info("Starting image input processing")
    
    if args.image:
        logging.info(f"Image argument provided: {args.image}")
        image_inputs = []
        for input_path in args.image.split(','):
            logging.info(f"Processing image input: {input_path}")
            try:
                if input_path.lower() == "generate":
                    image_description = args.image_description or description or f"A visual representation of audio titled '{title}'"
                    logging.info(f"Generating image with description: {image_description}")
                    generated_image_path = generate_image(image_description, title)
                    image_inputs.append(generated_image_path)
                    files_to_cleanup.append(generated_image_path)
                elif input_path.startswith("http"):
                    logging.info(f"Downloading image from URL: {input_path}")
                    downloaded_image_path = download_image(input_path)
                    image_inputs.append(downloaded_image_path)
                    files_to_cleanup.append(downloaded_image_path)
                else:
                    logging.info(f"Using local image file: {input_path}")
                    image_inputs.append(input_path)
            except Exception as e:
                logging.error(f"Error processing image input {input_path}: {str(e)}")
    elif args.autofill:
        logging.info("Autofill enabled, generating default image")
        image_description = f"A visual representation of audio titled '{title}'"
        logging.info(f"Generating image with description: {image_description}")
        generated_image_path = generate_image(image_description, title)
        image_inputs = [generated_image_path]
        files_to_cleanup.append(generated_image_path)
    else:
        logging.info("No image argument provided and autofill not enabled, prompting user for input")
        image_inputs = []
        while True:
            input_path = input("Enter path/URL to image/video file, 'generate' for AI image, or press Enter to finish: ").strip()
            if not input_path:
                break
            logging.info(f"User input received: {input_path}")
            try:
                if input_path.lower() == "generate":
                    image_description = input("Enter a description for the image to generate (or press Enter to use default): ")
                    if not image_description:
                        image_description = f"A visual representation of audio titled '{title}'"
                    logging.info(f"Generating image with description: {image_description}")
                    generated_image_path = generate_image(image_description, title)
                    image_inputs.append(generated_image_path)
                    files_to_cleanup.append(generated_image_path)
                elif input_path.startswith("http"):
                    logging.info(f"Downloading image from URL: {input_path}")
                    downloaded_image_path = download_image(input_path)
                    image_inputs.append(downloaded_image_path)
                    files_to_cleanup.append(downloaded_image_path)
                else:
                    logging.info(f"Using local image file: {input_path}")
                    image_inputs.append(input_path)
                logging.info(f"Added image: {image_inputs[-1]}")
            except Exception as e:
                logging.error(f"Error processing image input {input_path}: {str(e)}")
                print("Failed to process input. Please try again.")

    logging.info(f"Image input processing complete. Total images: {len(image_inputs)}")
    return image_inputs

def generate_image_prompt(description, is_retry=False):
    client = OpenAI(api_key=os.environ.get("OPENAI_PERSONAL_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    system_content = "You are a helpful assistant that creates high-quality image prompts for DALL-E based on user descriptions."
    if len(description) < 15:
        system_content += " Always include visual elements that represent music or audio in your prompts, even if not explicitly mentioned in the description."
    if is_retry:
        system_content += " The previous prompt violated content policy. Please create a new prompt that avoids potentially sensitive or controversial topics."
    
    user_content = f"Create a detailed, high-quality image prompt for DALL-E based on this description: {description}"
    if len(description) < 15:
        user_content += " Ensure to include visual elements representing music or audio."

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]
    )
    return response.choices[0].message.content

def generate_image(prompt, title, max_retries=3):
    client = OpenAI(api_key=os.environ.get("OPENAI_PERSONAL_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    
    for attempt in range(max_retries):
        try:
            response = client.images.generate(
                prompt=prompt,
                model="dall-e-3",
                n=1,
                quality="hd",
                size="1024x1024"
            )
            
            image_url = response.data[0].url
            img_response = requests.get(image_url)
            img = Image.open(BytesIO(img_response.content))
            
            # Create a filename based on the title and prompt
            filename = f"{sanitize_filename(title)}_{sanitize_filename(prompt[:50])}.png"
            img_path = os.path.join("temp_assets", filename)
            img.save(img_path)
            
            print(f"Image generated and saved: {img_path}")
            return img_path

        except Exception as e:
            if "content_policy_violation" in str(e):
                print("Content policy violation. Regenerating prompt...")
                prompt = generate_image_prompt(prompt, is_retry=True)
            else:
                print(f"Error generating image: {e}")
            
            if attempt == max_retries - 1:
                print("Max retries reached. Image generation failed.")
                return None

    return None
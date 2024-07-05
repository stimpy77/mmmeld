from file_utils import download_image, generate_image
import logging

def get_image_inputs(args, title, description, files_to_cleanup):
    if args.image:
        image_inputs = []
        for input_path in args.image.split(','):
            try:
                if input_path == "generate":
                    generated_image_path = generate_image(title, description)
                    image_inputs.append(generated_image_path)
                    files_to_cleanup.append(generated_image_path)
                elif input_path.startswith("http"):
                    downloaded_image_path = download_image(input_path)
                    image_inputs.append(downloaded_image_path)
                    files_to_cleanup.append(downloaded_image_path)
                else:
                    image_inputs.append(input_path)
            except Exception as e:
                logging.error(f"Error processing image input {input_path}: {str(e)}")
    else:
        image_inputs = input("Enter the path(s) to image/video file(s), separated by commas: ").split(',')

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
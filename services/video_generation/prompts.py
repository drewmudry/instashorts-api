import json
from openai import OpenAI
from typing import List, Dict, Any
import logging
from services.dynamo import DynamoDBService
from config.settings import settings
from models.videos import ImagePrompt

logger = logging.getLogger(__name__)


class PromptGenerationError(Exception):
    """Custom exception for image prompt generation errors"""
    pass


def generate_prompts(video_id: str, user_id: str, dynamo: DynamoDBService) -> List[Dict[str, Any]]:
    """
    Generate image prompts for a video based on its script.
    Returns a list of image prompts with indexes.
    """
    try:
        video = dynamo.get_video(video_id, user_id)
        if not video:
            raise PromptGenerationError(f"Video {video_id} not found")
        
        client = OpenAI(api_key=settings.openai_api_key)
        
        max_retries = 3
        attempt = 0
        
        while attempt < max_retries:
            try:
                messages = [
                    {"role": "system", "content": "You are a creative visual designer who creates engaging image prompts for videos."},
                    {
                        "role": "user",
                        "content": (
                            f"Create 10 image prompts for a video about: {video['topic']} with the title '{video['title']}'. "
                            f"The script for the video is: \n\n{video['script']}\n\n"
                            f"Each prompt should describe a detailed, visually compelling scene that matches a part of the script. "
                            f"The prompts will be used to generate images for a short video, so they should flow together to tell the story. "
                            f"Make the prompts descriptive, detailed, and visually interesting. Add an overarching visual theme to the prompts that is consistant across all prompts. "
                            "Respond with valid JSON data only in this exact format: "
                            '{"prompts": [{"index": 0, "prompt": "description for first image"}, '
                            '{"index": 1, "prompt": "description for second image"}, ...]}'
                        )
                    }
                ]
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1000
                )
                
                response_text = response.choices[0].message.content
                
                try:
                    content = json.loads(response_text)
                except json.JSONDecodeError:
                    # If direct parsing fails, try to extract JSON
                    import re
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        content = json.loads(json_match.group())
                    else:
                        raise
                
                # Validate the response has required fields
                if 'prompts' not in content or not isinstance(content['prompts'], list):
                    raise json.JSONDecodeError("Missing required prompts field or not a list", response_text, 0)
                
                # Validate each prompt has the required fields
                for prompt in content['prompts']:
                    if not all(key in prompt for key in ['index', 'prompt']):
                        raise json.JSONDecodeError("Prompt missing required fields", response_text, 0)
                
                # Update the video with the image prompts
                img_prompts = content['prompts']
                dynamo.update_video(
                    video_id=video_id,
                    update_data={"img_prompts": img_prompts}
                )
                
                return img_prompts
                
            except json.JSONDecodeError as e:
                logger.warning(f"Attempt {attempt + 1}: Invalid JSON response: {str(e)}")
                logger.warning(f"Response text was: {response_text}")
                attempt += 1
                if attempt == max_retries:
                    raise PromptGenerationError("Failed to get valid JSON response after maximum retries")
                continue
                
    except Exception as e:
        logger.error(f"Error generating image prompts: {str(e)}")
        raise PromptGenerationError(f"Image prompt generation failed: {str(e)}")
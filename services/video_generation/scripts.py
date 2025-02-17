import json
from google import genai
from typing import Tuple
import logging
from services.dynamo import DynamoDBService
from config.settings import settings

logger = logging.getLogger(__name__)


class ScriptGenerationError(Exception):
    """Custom exception for script generation errors"""
    pass

def generate_script_and_title(video_id: str, user_id: str, dynamo: DynamoDBService) -> Tuple[str, str]:
    try:
        video = dynamo.get_video(video_id, user_id)
        if not video:
            raise ScriptGenerationError(f"Video {video_id} not found")
        client = genai.Client(api_key=settings.gemini_api_key)
        
        max_retries = 3
        attempt = 0
        
        while attempt < max_retries:
            try:
                prompt = (
                    f"Create a script and title for a video about {video['topic']}. \n"
                    f"the script should be an entertaining story written from a narriators point of view so it can be read off by one person."
                    f"Make sure the script is approx 250 words as the video is meant to be 60-65 seconds. \n"
                    f"You must respond with valid JSON data in this exact format, with no additional text before or after:\n"
                    f"{{\n"
                    f"  \"title\": \"your title here\",\n"
                    f"  \"script\": \"your script here\"\n"
                    f"}}"
                )
                
                response = client.models.generate_content(
                    model="gemini-1.5-pro",
                    contents=prompt
                )
                
                # Get the response text and clean it
                response_text = response.text
                
                # Remove markdown code blocks if present
                response_text = response_text.replace('```json\n', '').replace('\n```', '')
                
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
                if not all(key in content for key in ['title', 'script']):
                    raise json.JSONDecodeError("Missing required fields", response_text, 0)

                update_data = {
                    'title': content['title'],
                    'script': content['script']
                }                
                dynamo.update_video(video_id, update_data)
                
                return content['title'], content['script']
                
            except json.JSONDecodeError as e:
                logger.warning(f"Attempt {attempt + 1}: Invalid JSON response: {str(e)}")
                logger.warning(f"Response text was: {response_text}")
                attempt += 1
                if attempt == max_retries:
                    raise ScriptGenerationError("Failed to get valid JSON response after maximum retries")
                continue
                
    except Exception as e:
        logger.error(f"Error generating script: {str(e)}")
        raise ScriptGenerationError(f"Script generation failed: {str(e)}")
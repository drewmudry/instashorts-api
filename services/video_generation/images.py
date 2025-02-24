import asyncio
import requests
import json
import boto3
import base64
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict
import logging

from config.settings import settings
from services.dynamo import DynamoDBService

logger = logging.getLogger(__name__)

class ImageGenerationError(Exception):
    """Custom exception for image generation errors"""
    pass

def generate_single_image(prompt: str, index: int, video_id: str) -> Dict:
    """Generate a single image using getimg.ai API and upload to S3"""
    try:
        url = "https://api.getimg.ai/v1/flux-schnell/text-to-image"
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {settings.GETIMG_AKI_KEY}"
        }
        
        logger.info(f"Generating image {index} with prompt: {prompt[:50]}...")
        
        payload = {
            "prompt": prompt,
            "width": 720,
            "height": 1280,
            "steps": 5,
            "output_format": "png",
            "response_format": "b64" # recieve image b64 encoded
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            error_msg = f"API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise ImageGenerationError(error_msg)
        
        result = response.json()
        logger.info(f"Successfully received image {index} from API")
        
        if "image" not in result:
            raise ImageGenerationError(f"No image data in API response for index {index}")
        
        # Decode base64 image
        image_data = base64.b64decode(result["image"])
        logger.info(f"Successfully decoded base64 for image {index}")
        
        # Simplified S3 path construction
        s3_key = f'images/{video_id}/{index}.png'
        logger.info(f"Attempting S3 upload with key: {s3_key}")
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        
        # Upload to S3
        s3_client.put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=image_data,
            ContentType='image/png'
        )
        logger.info(f"S3 upload successful for image {index}")
        
        # Generate URL
        s3_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.s3_bucket_name,
                'Key': s3_key
            },
            ExpiresIn=3600*24*7
        )
        logger.info(f"Generated presigned URL for image {index}")
        
        return {"index": index, "url": s3_url}
        
    except Exception as e:
        logger.error(f"Error generating image {index}: {str(e)}")
        raise

def generate_images(video_id: str, user_id: str, dynamo_service: DynamoDBService) -> List[Dict]:
    """Generate all images for a video in parallel"""
    logger.info(f"Starting image generation for video {video_id}")
    
    try:
        video = dynamo_service.get_video(video_id, user_id)
        if not video:
            raise ImageGenerationError(f"Video {video_id} not found")
        
        if not video.get('img_prompts'):
            raise ImageGenerationError(f"No image prompts found for video {video_id}")
        
        prompts = video['img_prompts']
        
        generated_images = []
        failed_images = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(generate_single_image, 
                              prompt_obj['prompt'],
                              prompt_obj['index'],
                              video_id)
                for prompt_obj in prompts
            ]
            
            for future in futures:
                try:
                    result = future.result()  # This will raise any exceptions from the thread
                    generated_images.append(result)
                except Exception as e:
                    failed_images.append(str(e))
        
        if failed_images:
            error_msg = f"Failed to generate {len(failed_images)} images: {'; '.join(failed_images)}"
            logger.error(error_msg)
            raise ImageGenerationError(error_msg)
        
        if not generated_images:
            raise ImageGenerationError("No images were successfully generated")
        
        generated_images.sort(key=lambda x: x['index'])
        
        dynamo_service.update_video(
            video_id=video_id,
            update_data={"images": generated_images}
        )
        
        logger.info(f"Successfully generated and uploaded {len(generated_images)} images for video {video_id}")
        return generated_images
        
    except Exception as e:
        logger.error(f"Error in generate_images: {str(e)}")
        raise
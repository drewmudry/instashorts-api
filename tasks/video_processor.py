from celery import chain
from config.settings import settings
from config.celery import celery_app as celery
from services.dynamo import DynamoDBService
from models.videos import VideoStatus
from services.video_generation.scripts import generate_script_and_title
from services.video_generation.voice import generate_voice
from services.video_generation.prompts import generate_prompts
from services.video_generation.images import generate_images
from services.video_generation.compiler import compile_video
import time


dynamo_service = DynamoDBService()

@celery.task(bind=True, max_retries=3)
def generate_script_task(self, video_id: str, user_id: str):
    try:
        logger.info(f"Starting generate_script_task for video_id: {video_id}, user_id: {user_id}")
        print(f"we in generate_script_task for {video_id}")
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.GENERATING_SCRIPT.value,
                "user_id": user_id  # Use string key for user_id
            }
        )

        # Generate script and title
        generate_script_and_title(video_id, user_id, dynamo_service)

        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.SCRIPT_COMPLETE.value
            }
        )

        return {"video_id": video_id, "user_id": user_id}  # Return a dictionary

    except Exception as e:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.FAILED.value,
                "status": VideoStatus.FAILED.value
            }
        )
        raise self.retry(exc=e, countdown=60)

@celery.task(bind=True, max_retries=3)
def generate_voice_task(self, previous_result):  # Takes previous result
    try:
        video_id = previous_result['video_id']
        user_id = previous_result['user_id']
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.GENERATING_VOICE.value
            }
        )

        # Generate voice
        generate_voice(video_id, user_id, dynamo_service)

        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.VOICE_COMPLETE.value
            }
        )
        return previous_result # Return the previous result to pass forward
    except Exception as e:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.FAILED.value
            }
        )
        raise self.retry(exc=e, countdown=60)

@celery.task(bind=True, max_retries=3)
def generate_prompts_task(self, previous_result):
    try:
        video_id = previous_result['video_id']
        user_id = previous_result['user_id']
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.GENERATING_PROMPTS.value
            }
        )
        generate_prompts(video_id, user_id, dynamo_service)
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.PROMPTS_COMPLETE.value
            }
        )
        return previous_result
    except Exception as e:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.FAILED.value
            }
        )
        raise self.retry(exc=e, countdown=60)

@celery.task(bind=True, max_retries=3)
def generate_images_task(self, previous_result):
    try:
        video_id = previous_result['video_id']
        user_id = previous_result['user_id']
        
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.GENERATING_IMAGES.value
            }
        )
        
        from services.video_generation.images import generate_images
        generate_images(video_id, user_id, dynamo_service)
        
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.IMAGES_COMPLETE.value
            }
        )
        
        return previous_result
    except Exception as e:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.FAILED.value,
            }
        )
        raise self.retry(exc=e, countdown=60)

@celery.task(bind=True, max_retries=3)
def compile_video_task(self, previous_result):
    try:
        video_id = previous_result['video_id']
        user_id = previous_result['user_id']
        
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.COMPILING.value
            }
        )
        
        # Import the compile_video function
        from services.video_generation.compiler import compile_video
        
        # Call the video compilation function
        video_url = compile_video(video_id, user_id, dynamo_service)
        
        # Update the video record with the completed status
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.COMPLETED.value,
                "final_url": video_url
            }
        )
        
        return previous_result
    except Exception as e:
        # Update DynamoDB with failure status
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.FAILED.value,
            }
        )
        # Log the error
        print(f"Error compiling video {video_id}: {str(e)}")
        # Retry the task
        raise self.retry(exc=e, countdown=60)


import logging
logger = logging.getLogger(__name__)

def start_video_pipeline(video_id: str, user_id: str):
    """Start the Celery pipeline for video generation"""
    logger.info(f"Starting video pipeline")
    pipeline = chain(
        # chain means args passed into the 1st task will be passed to the 2nd and so on 
        generate_script_task.s(video_id, user_id), # done
        generate_voice_task.s(),  # done
        generate_prompts_task.s(), # done
        generate_images_task.s(), # done
        compile_video_task.s()  # No arguments here
    )
    pipeline.apply_async()
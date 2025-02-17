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
        print(f"we in generate_script_task for {video_id}")
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.GENERATING_SCRIPT.value,
                "user_id": user_id  # Use string key for user_id
            }
        )

        # Generate script and title
        # generate_script_and_title(video_id, user_id, dynamo_service)

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
        video_id = previous_result['video_id']  # Extract video_id
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.GENERATING_VOICE.value
            }
        )

        # Generate voice
        # generate_voice(video_id) # Example

        time.sleep(3)  # Keep for demonstration

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

# ... (Similar changes for generate_prompts_task, generate_images_task, compile_video_task)

@celery.task(bind=True, max_retries=3)
def generate_prompts_task(self, previous_result):
    try:
        video_id = previous_result['video_id']
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.GENERATING_PROMPTS.value
            }
        )
        time.sleep(3)
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
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.GENERATING_IMAGES.value
            }
        )
        time.sleep(3)
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
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.COMPILING.value
            }
        )
        time.sleep(3)
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "creation_status": VideoStatus.COMPLETED.value
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


def start_video_pipeline(video_id: str, user_id: str):
    """Start the Celery pipeline for video generation"""
    print("we in start_video_pipeline")
    pipeline = chain(
        generate_script_task.s(video_id, user_id),
        generate_voice_task.s(),  # No arguments here
        generate_prompts_task.s(), # No arguments here
        generate_images_task.s(), # No arguments here
        compile_video_task.s()  # No arguments here
    )
    pipeline.apply_async()
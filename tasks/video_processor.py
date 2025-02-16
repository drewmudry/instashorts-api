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
    """Generate script and title"""
    try:
        print(f"we in generate_script_task for {video_id}")
        dynamo_service.update_video(
            video_id=video_id, 
            update_data={"creation_status": VideoStatus.GENERATING_SCRIPT}
        )
        time.sleep(10)
        generate_script_and_title(video_id, user_id, dynamo_service)
        
        return {"video_id": video_id, "user_id": user_id}
    except Exception as e:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={"creation_status": VideoStatus.FAILED}
        )
        raise self.retry(exc=e, countdown=60)

@celery.task(bind=True, max_retries=3)
def generate_voice_task(self, task_data):
    """Generate voice"""
    video_id = task_data["video_id"]
    user_id = task_data["user_id"]
    print("we in generate_voice_task")
    try:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={"creation_status": VideoStatus.GENERATING_VOICE}
        )
        generate_voice(video_id, user_id, dynamo_service)
        return task_data
    except Exception as e:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={"creation_status": VideoStatus.FAILED}
        )
        raise self.retry(exc=e, countdown=60)

@celery.task(bind=True, max_retries=3)
def generate_prompts_task(self, task_data):
    """Generate prompts"""
    video_id = task_data["video_id"]
    user_id = task_data["user_id"]
    try:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={"creation_status": VideoStatus.GENERATING_PROMPTS}
        )
        generate_prompts(video_id, user_id, dynamo_service)
        return task_data
    except Exception as e:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={"creation_status": VideoStatus.FAILED}
        )
        raise self.retry(exc=e, countdown=60)

@celery.task(bind=True, max_retries=3)
def generate_images_task(self, task_data):
    """Generate images"""
    video_id = task_data["video_id"]
    user_id = task_data["user_id"]
    try:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={"creation_status": VideoStatus.GENERATING_IMAGES}
        )
        generate_images(video_id, user_id, dynamo_service)
        return task_data
    except Exception as e:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={"creation_status": VideoStatus.FAILED}
        )
        raise self.retry(exc=e, countdown=60)

@celery.task(bind=True, max_retries=3)
def compile_video_task(self, task_data):
    """Final video compilation"""
    video_id = task_data["video_id"]
    user_id = task_data["user_id"]
    try:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={"creation_status": VideoStatus.COMPILING}
        )
        compile_video(video_id, user_id)
        dynamo_service.update_video(
            video_id=video_id,
            update_data={"creation_status": VideoStatus.COMPLETED}
        )
    except Exception as e:
        dynamo_service.update_video(
            video_id=video_id,
            update_data={"creation_status": VideoStatus.FAILED}
        )
        raise self.retry(exc=e, countdown=60)

# This starts the entire pipeline
def start_video_pipeline(video_id: str, user_id: str):
    """Start the Celery pipeline for video generation"""
    print("we in start_video_pipeline")
    pipeline = chain(
        generate_script_task.s(video_id, user_id),
        # generate_voice_task.s(),
        # generate_prompts_task.s(),
        # generate_images_task.s(),
        # compile_video_task.s()
    )
    pipeline.apply_async()
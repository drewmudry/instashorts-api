from fastapi import BackgroundTasks
from celery import Celery
from config.settings import settings
from services.dynamo import DynamoDBService
from models.videos import VideoStatus
from services.video_generation.scripts import generate_script_and_title
from services.video_generation.voice import generate_voice
from services.video_generation.prompts import generate_prompts
from services.video_generation.images import generate_images
from services.video_generation.compiler import compile_video
from time import sleep


# Keep Celery just for video compilation
celery = Celery('video_compiler', broker=settings.redis_url)
dynamo_service_old = DynamoDBService()


async def process_video_background(
    background_tasks: BackgroundTasks,
    video_id: str,
    user_id: str,
    dynamo: DynamoDBService
):
    """Main function to handle video processing using background tasks"""
    try:
        print("CHAIN ACTIVATED")
        print(f"Adding background task for video {video_id}")
        background_tasks.add_task(
            _generate_script_task,
            video_id,
            user_id,
            dynamo
        )
        print("Background task added successfully")
        return {"message": "Video processing started"}
    except Exception as e:
        await dynamo.update_video(video_id=video_id, update_data={"creation_status": VideoStatus.FAILED})
        raise e


# Changed to internal helper functions with underscore prefix
async def _generate_script_task(video_id: str, user_id: str, dynamo: DynamoDBService):
    """Generate script and chain the next task"""
    print(f"Starting _generate_script_task for video {video_id}")
    try:
        print("Updating video status to GENERATING_SCRIPT")
        try:
            # Update with just video_id and the update data dictionary
            await dynamo.update_video(
                video_id=video_id, 
                update_data={"creation_status": VideoStatus.GENERATING_SCRIPT}
            )
        except Exception as status_error:
            print(f"Error updating status: {str(status_error)}")
            await dynamo.update_video(video_id=video_id, update_data={"creation_status": VideoStatus.FAILED})
            raise status_error
        
        print('entering generate_script_and_title')
        await generate_script_and_title(video_id, user_id, dynamo)
        
        # Queue the next task
        await _generate_voice_task(video_id, user_id)
        
    except Exception as e:
        print(f"Error in _generate_script_task: {str(e)}")
        await dynamo.update_video(
            video_id=video_id,
            update_data={"creation_status": VideoStatus.FAILED}
        )
        raise e


async def _generate_voice_task(video_id: str, user_id: str, dynamo: DynamoDBService):
    """Generate voice and chain the next task"""
    try:
        await dynamo.update_video(video_id, VideoStatus.GENERATING_VOICE)
        # Call your existing voice generation service
        voice = await generate_voice(video_id, user_id)
        
        # Queue the next task
        await _generate_prompts_task(video_id, user_id)
    except Exception as e:
        await dynamo.update_video(video_id, VideoStatus.FAILED)
        raise e


async def _generate_prompts_task(video_id: str, user_id: str, dynamo: DynamoDBService):
    """Generate prompts and chain the next task"""
    try:
        await dynamo.update_video(video_id, VideoStatus.GENERATING_PROMPTS)
        # Call your existing prompts generation service
        prompts = await generate_prompts(video_id, user_id)
        
        # Queue the next task
        await _generate_images_task(video_id, user_id)
    except Exception as e:
        await dynamo.update_video(video_id, VideoStatus.FAILED)
        raise e


async def _generate_images_task(video_id: str, user_id: str, dynamo: DynamoDBService):
    """Generate images and chain to final compilation"""
    try:
        await dynamo.update_video(video_id, VideoStatus.GENERATING_IMAGES)
        # Call your existing image generation service
        images = await generate_images(video_id, user_id)
        
        # Start the final Celery task
        await _start_compilation(video_id, user_id)
    except Exception as e:
        await dynamo.update_video(video_id, VideoStatus.FAILED)
        raise e



async def _start_compilation(video_id: str, user_id: str, dynamo: DynamoDBService):
    """Start the Celery task for video compilation"""
    await dynamo.update_video(video_id, VideoStatus.FAILED)
    compile_video_task.delay(video_id, user_id)


# The heavy computation Celery task
@celery.task
def compile_video_task(video_id: str, user_id: str):
    """Heavy computation task for video compilation"""
    try:
        compile_video(video_id, user_id)
        dynamo_service_old.update_video(
            video_id,
            user_id,
            {"status": VideoStatus.COMPLETED}
        )
    except Exception as e:
        dynamo_service_old.update_video(
            video_id,
            user_id,
            {
                "status": VideoStatus.FAILED,
                "error": str(e)
            }
        )
        raise e
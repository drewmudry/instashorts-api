from fastapi import BackgroundTasks
from celery import Celery
from config.settings import settings
from services.dynamo import DynamoDBService
from models.videos import VideoStatus
from services.video_generation.scripts import generate_script
from services.video_generation.voice import generate_voice
from services.video_generation.prompts import generate_prompts
from services.video_generation.images import generate_images
from services.video_generation.compiler import compile_video

# Keep Celery just for video compilation
celery = Celery('video_compiler', broker=settings.redis_url)
dynamo_service = DynamoDBService()

async def process_video_background(
    background_tasks: BackgroundTasks,
    video_id: str,
    user_id: str
):
    """Main function to handle video processing using background tasks"""
    try:
        # Add the first task to the chain
        background_tasks.add_task(
            _generate_script_task,  # Note the underscore prefix for internal function
            video_id,
            user_id
        )
        return {"message": "Video processing started"}
    except Exception as e:
        await update_video_status(video_id, user_id, VideoStatus.FAILED, str(e))
        raise e

# Changed to internal helper functions with underscore prefix
async def _generate_script_task(video_id: str, user_id: str):
    """Generate script and chain the next task"""
    try:
        await update_video_status(video_id, user_id, VideoStatus.GENERATING_SCRIPT)
        # Call your existing script generation service
        script = await generate_script(video_id, user_id)
        
        # Queue the next task
        await _generate_voice_task(video_id, user_id)
    except Exception as e:
        await update_video_status(video_id, user_id, VideoStatus.FAILED, str(e))
        raise e

async def _generate_voice_task(video_id: str, user_id: str):
    """Generate voice and chain the next task"""
    try:
        await update_video_status(video_id, user_id, VideoStatus.GENERATING_VOICE)
        # Call your existing voice generation service
        voice = await generate_voice(video_id, user_id)
        
        # Queue the next task
        await _generate_prompts_task(video_id, user_id)
    except Exception as e:
        await update_video_status(video_id, user_id, VideoStatus.FAILED, str(e))
        raise e

async def _generate_prompts_task(video_id: str, user_id: str):
    """Generate prompts and chain the next task"""
    try:
        await update_video_status(video_id, user_id, VideoStatus.GENERATING_PROMPTS)
        # Call your existing prompts generation service
        prompts = await generate_prompts(video_id, user_id)
        
        # Queue the next task
        await _generate_images_task(video_id, user_id)
    except Exception as e:
        await update_video_status(video_id, user_id, VideoStatus.FAILED, str(e))
        raise e

async def _generate_images_task(video_id: str, user_id: str):
    """Generate images and chain to final compilation"""
    try:
        await update_video_status(video_id, user_id, VideoStatus.GENERATING_IMAGES)
        # Call your existing image generation service
        images = await generate_images(video_id, user_id)
        
        # Start the final Celery task
        await _start_compilation(video_id, user_id)
    except Exception as e:
        await update_video_status(video_id, user_id, VideoStatus.FAILED, str(e))
        raise e

async def update_video_status(video_id: str, user_id: str, status: VideoStatus, error: str = None):
    """Helper function to update video status"""
    update_data = {"status": status}
    if error:
        update_data["error"] = error
    await dynamo_service.update_video(video_id, user_id, update_data)

async def _start_compilation(video_id: str, user_id: str):
    """Start the Celery task for video compilation"""
    await update_video_status(video_id, user_id, VideoStatus.COMPILING)
    compile_video_task.delay(video_id, user_id)

# The heavy computation Celery task
@celery.task
def compile_video_task(video_id: str, user_id: str):
    """Heavy computation task for video compilation"""
    try:
        compile_video(video_id, user_id)
        dynamo_service.update_video(
            video_id,
            user_id,
            {"status": VideoStatus.COMPLETED}
        )
    except Exception as e:
        dynamo_service.update_video(
            video_id,
            user_id,
            {
                "status": VideoStatus.FAILED,
                "error": str(e)
            }
        )
        raise e
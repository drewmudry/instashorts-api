from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Optional
import uuid
from typing import List
from datetime import datetime
from models.videos import VideoCreate, VideoDetail, VideoList, VideoStatus
from services.dynamo import DynamoDBService
from dependencies.auth import get_current_user
from tasks.video_processor import process_video_background

router = APIRouter(prefix="/videos", tags=["videos"])
dynamo_service = DynamoDBService()

@router.post("/", response_model=VideoCreate)
async def create_video(
    background_tasks: BackgroundTasks,
    video_theme: str,
    video_voice: str,
    user_id: str = Depends(get_current_user)
):
    video_data = {
        "user_id": user_id,
        "theme": video_theme,
        "voice": video_voice,
        "status": VideoStatus.PENDING,
        "script": "",  # Will be populated by background task
        "title": ""   # Will be populated by background task
    }
    
    video = await dynamo_service.create_video(video_data)
    await process_video_background(background_tasks, video['id'], user_id)
    return video

@router.get("/{video_id}", response_model=VideoDetail)
async def get_video(video_id: str, user_id: str = Depends(get_current_user)):
    video = await dynamo_service.get_video(video_id, user_id)
    return video

@router.get("/", response_model=List[VideoList])
async def list_videos(user_id: str = Depends(get_current_user)):
    videos = await dynamo_service.get_user_videos(user_id)
    return videos

@router.delete("/{video_id}")
async def delete_video(video_id: str, user_id: str = Depends(get_current_user)):
    success = await dynamo_service.delete_video(video_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    return {"message": "Video deleted successfully"}
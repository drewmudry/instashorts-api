from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Optional
import uuid
from typing import List
from datetime import datetime
from models.videos import VideoCreate, VideoDetail, VideoList, VideoStatus, VideoRequest
from services.dynamo import DynamoDBService
from dependencies.auth import get_current_user
from tasks.video_processor import process_video_background

router = APIRouter(prefix="/videos", tags=["videos"])
dynamo = DynamoDBService()

@router.post("/", response_model=VideoCreate)
async def create_video(
    request: VideoRequest,  # This will read from request body
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user)
):
    video_data = {
        "user_id": user_id,
        "topic": request.topic,
        "voice": request.voice,
        "status": VideoStatus.PENDING,
        "script": "",  # Will be populated by background task
        "title": ""   # Will be populated by background task
    }
    
    video = await dynamo.create_video(video_data)
    await process_video_background(background_tasks, video['id'], user_id, dynamo)
    return video

@router.get("/{video_id}", response_model=VideoDetail)
async def get_video(video_id: str, user_id: str = Depends(get_current_user)):
    video = await dynamo.get_video(video_id, user_id)
    return video

@router.get("/", response_model=List[VideoList])
async def list_videos(user_id: str = Depends(get_current_user)):
    videos = await dynamo.get_user_videos(user_id)
    return videos

@router.delete("/{video_id}")
async def delete_video(video_id: str, user_id: str = Depends(get_current_user)):
    success = await dynamo.delete_video(video_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    return {"message": "Video deleted successfully"}
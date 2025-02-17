from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from typing import AsyncGenerator
from typing import Optional
from typing import List
from datetime import datetime
from models.videos import VideoCreate, VideoDetail, VideoList, VideoStatus, VideoRequest
from services.dynamo import DynamoDBService
from dependencies.auth import get_current_user
from tasks.video_processor import start_video_pipeline


router = APIRouter(prefix="/videos", tags=["videos"])
dynamo = DynamoDBService()

@router.get("/", response_model=List[VideoList])
async def list_videos(user_id: str = Depends(get_current_user)):
    videos = dynamo.get_user_videos(user_id)
    return videos


@router.post("/", response_model=VideoCreate)
async def create_video(
    request: VideoRequest,
    user_id: str = Depends(get_current_user)
):
    video_data = {
        "user_id": user_id,
        "topic": request.topic,
        "voice": request.voice,
        "status": VideoStatus.PENDING.value,
        "script": "",
        "title": ""
    }
    
    video = dynamo.create_video(video_data)
    # Start the Celery pipeline
    start_video_pipeline(video['id'], user_id)
    return video


@router.get("/{video_id}/status")
async def video_status(video_id: str, user_id: str = Depends(get_current_user)):
    async def event_generator():
        while True:
            video = dynamo.get_video(video_id=video_id, user_id=user_id)
            
            if not video or video["user_id"] != user_id:
                break
                
            # Transform the status to match enum values if needed
            if "creation_status" in video:
                try:
                    video["creation_status"] = VideoStatus(video["creation_status"]).value
                except ValueError:
                    video["creation_status"] = VideoStatus.FAILED.value
            
            yield {
                "data": json.dumps(video)
            }
            
            # Compare with enum values instead of raw strings
            if video["creation_status"] in [VideoStatus.COMPLETED.value, VideoStatus.FAILED.value]:
                break
                
            await asyncio.sleep(2)
    
    return EventSourceResponse(event_generator(), media_type="text/event-stream")


@router.get("/{video_id}", response_model=VideoDetail)
async def get_video(video_id: str, user_id: str = Depends(get_current_user)):
    video = dynamo.get_video(video_id, user_id)
    return video


@router.delete("/{video_id}")
async def delete_video(video_id: str, user_id: str = Depends(get_current_user)):
    success = dynamo.delete_video(video_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    return {"message": "Video deleted successfully"}
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Optional
import uuid
from datetime import datetime
from models.videos import Video, VideoStatus
from services.dynamo import DynamoDBService
from dependencies.auth import get_current_user
from tasks.video_processor import process_video_background

router = APIRouter(prefix="/videos", tags=["videos"])
dynamo_service = DynamoDBService()

@router.post("/", response_model=Video)
async def create_video(
    background_tasks: BackgroundTasks,
    title: str,
    description: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    video_data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": title,
        "description": description,
        "status": VideoStatus.PENDING,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    video = await dynamo_service.create_video(video_data)
    await process_video_background(background_tasks, video['id'], user_id)
    return video

@router.get("/{video_id}", response_model=Video)
async def get_video(video_id: str, user_id: str = Depends(get_current_user)):
    video = await dynamo_service.get_video(video_id, user_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    return video

@router.get("/", response_model=list[Video])
async def list_videos(
    user_id: str = Depends(get_current_user),
    last_key: Optional[str] = None
):
    last_evaluated_key = None
    if last_key:
        # Implement your pagination logic here
        pass
    
    result = await dynamo_service.get_user_videos(user_id, last_evaluated_key)
    return result['items']

@router.delete("/{video_id}")
async def delete_video(video_id: str, user_id: str = Depends(get_current_user)):
    success = await dynamo_service.delete_video(video_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    return {"message": "Video deleted successfully"}
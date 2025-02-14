from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
import uuid
from datetime import datetime
from models.series import Series
from services.dynamo import DynamoDBService
from dependencies.auth import get_current_user

router = APIRouter(prefix="/series", tags=["series"])
dynamo_service = DynamoDBService()

@router.post("/", response_model=Series)
async def create_series(
    title: str,
    description: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    series_data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": title,
        "description": description,
        "video_ids": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "is_active": True
    }
    
    return await dynamo_service.create_series(series_data)

@router.get("/{series_id}", response_model=Series)
async def get_series(series_id: str, user_id: str = Depends(get_current_user)):
    series = await dynamo_service.get_series(series_id, user_id)
    if not series:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Series not found"
        )
    return series

@router.post("/{series_id}/videos/{video_id}")
async def add_video_to_series(
    series_id: str,
    video_id: str,
    user_id: str = Depends(get_current_user)
):
    series = await dynamo_service.get_series(series_id, user_id)
    if not series:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Series not found"
        )
    
    video = await dynamo_service.get_video(video_id, user_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    if video_id not in series['video_ids']:
        series['video_ids'].append(video_id)
        series['updated_at'] = datetime.utcnow().isoformat()
        await dynamo_service.update_series(series_id, user_id, series)
    
    return {"message": "Video added to series successfully"}
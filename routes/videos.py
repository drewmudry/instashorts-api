from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from decimal import Decimal
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
    
    voices = [ "pNInz6obpgDQGcFmaJgB", "nPczCjzI2devNBz1zQrb", "piTKgcLEGmPE4e6mEKli", "2EiwWnXFnvU5JabPnv8n", "ThT5KcBeYPX3keUQqHPh",
        "29vD33N1CtxCmqQRPOHJ","jsCqWAovK2LkecY7zXl4", "ZQe5CZNOzWyzPSCn5a3c", "cgSgspJ2msm6clMCkdW9", "EXAVITQu4vr4xnSDxMaL", "GBv7mTt0atIp3Br8iCZE"
    ]
    if request.voice not in voices: 
        raise HTTPException(status_code=400, detail="Voice not supported")
    
    video = dynamo.create_video(video_data)
    # Start the Celery pipeline
    start_video_pipeline(video['id'], user_id)
    
    # do something like this 
    # request.session['user'].update({
    #     'first_name': "ian"
    #     # 'last_video_created_at': updated_user.get('last_video_created_at'),
    #     # 'subscription_tier': updated_user.get('subscription_tier'),
    #     # 'daily_video_limit': updated_user.get('daily_video_limit')
    # })
    return video


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

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
            
            # Remove img_prompts from the response
            if "img_prompts" in video:
                del video["img_prompts"]
            
            # Use the custom encoder to handle Decimal values
            yield {
                "data": json.dumps(video, cls=DecimalEncoder)
            }
            
            # Compare with enum values instead of raw strings
            if video["creation_status"] in [VideoStatus.COMPLETED.value, VideoStatus.FAILED.value]:
                break
                
            await asyncio.sleep(1)
    
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
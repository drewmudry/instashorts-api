from typing import Optional, List
from pydantic import BaseModel
from enum import Enum
from datetime import datetime

class VideoStatus(str, Enum):
    PENDING = "pending"
    GENERATING_SCRIPT = "generating_script"
    GENERATING_VOICE = "generating_voice"
    GENERATING_PROMPTS = "generating_prompts"
    GENERATING_IMAGES = "generating_images"
    COMPILING = "compiling"
    COMPLETED = "completed"
    FAILED = "failed"

class Video(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str]
    status: VideoStatus = VideoStatus.PENDING
    script: Optional[str]
    voice_file_url: Optional[str]
    image_prompts: Optional[List[str]]
    image_urls: Optional[List[str]]
    final_video_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    series_id: Optional[str]

# models/series.py
class Series(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str]
    video_ids: List[str] = []
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
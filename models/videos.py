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

class ImagePrompt(BaseModel):
    index: int
    prompt: str

class GeneratedImage(BaseModel):
    index: int
    url: str

class VideoBase(BaseModel):
    id: str
    user_id: str
    topic: str
    voice: str
    creation_status: VideoStatus
    title: Optional[str] = None
    series: Optional[str]


class VideoCreate(VideoBase):
    script: str
    
    
class VideoRequest(BaseModel):
    topic: str
    voice: str


class VideoList(VideoBase):
    final_url: Optional[str] = None


class VideoDetail(VideoBase):
    script: str
    img_prompts: Optional[List[ImagePrompt]] = None
    audio_url: Optional[str] = None
    images: Optional[List[GeneratedImage]] = None
    final_url: Optional[str] = None
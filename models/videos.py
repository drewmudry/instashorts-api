from typing import Optional, List
from pydantic import BaseModel
from enum import Enum
from datetime import datetime

class VideoStatus(str, Enum):
    PENDING = "Pending"
    GENERATING_SCRIPT = "Writing Script"
    SCRIPT_COMPLETE = "Script Completed"
    
    GENERATING_VOICE = "Generating Audio"
    VOICE_COMPLETE = "Narration Completed"
    
    GENERATING_PROMPTS = "Brainstorming Images"
    PROMPTS_COMPLETE = "Finalizing Content"
    
    GENERATING_IMAGES = "Crafting Images"
    IMAGES_COMPLETE = "Images Finished"
    
    COMPILING = "Video Rendering"
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
    created_at: datetime


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
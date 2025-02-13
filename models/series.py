from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class SeriesBase(BaseModel):
    """Base Series model with common attributes"""
    title: str = Field(..., description="Title of the series")
    description: Optional[str] = Field(None, description="Description of the series")

class SeriesCreate(SeriesBase):
    """Series creation model"""
    pass

class SeriesUpdate(BaseModel):
    """Series update model with optional fields"""
    title: Optional[str] = Field(None, description="Updated title of the series")
    description: Optional[str] = Field(None, description="Updated description of the series")
    is_active: Optional[bool] = Field(None, description="Series active status")

class SeriesInDB(SeriesBase):
    """Series model as stored in the database"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    video_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @classmethod
    def create_new(cls, user_id: str, series_data: SeriesCreate) -> 'SeriesInDB':
        """Create a new series instance with generated fields"""
        return cls(
            user_id=user_id,
            **series_data.model_dump()
        )

    def to_dynamo(self) -> dict:
        """Convert the model to DynamoDB format"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "video_ids": self.video_ids,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active
        }

    @classmethod
    def from_dynamo(cls, data: dict) -> 'SeriesInDB':
        """Create a model instance from DynamoDB data"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            title=data["title"],
            description=data.get("description"),
            video_ids=data.get("video_ids", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            is_active=data.get("is_active", True)
        )

class Series(SeriesInDB):
    """API response model for series"""
    video_count: int = Field(..., description="Number of videos in the series")

    @classmethod
    def from_db_model(cls, db_model: SeriesInDB) -> 'Series':
        """Create an API response model from a database model"""
        data = db_model.model_dump()
        data["video_count"] = len(db_model.video_ids)
        return cls(**data)
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "InstaShorts API"
    google_client_id: str
    google_client_secret: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    redis_url: str 
    
    
    class Config:
        env_file = '../.env'

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
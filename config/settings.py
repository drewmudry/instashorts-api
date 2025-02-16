from pydantic_settings import BaseSettings
from pydantic import field_validator, Field
from functools import lru_cache
from ssl import CERT_NONE
import os

class Settings(BaseSettings):
    app_name: str = "InstaShorts API"
    google_client_id: str
    google_client_secret: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    gemini_api_key: str
    redis_url: str = Field(..., alias="REDIS_URL")

    # Debug print in model initialization
    def __init__(self, **kwargs):
        print("Current working directory:", os.getcwd())
        print("Env file exists:", os.path.exists('.env'))
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                print("Env file contents:", f.read())
        print("Environment REDIS_URL:", os.getenv('REDIS_URL'))
        super().__init__(**kwargs)

    # Redis SSL Configuration
    redis_ssl_config: dict = {
        'ssl_cert_reqs': CERT_NONE
    }

    @field_validator('redis_url')
    @classmethod
    def ensure_rediss_protocol(cls, v: str) -> str:
        print(f"Validating redis_url: {v}")
        if v.startswith('redis://'):
            v = 'rediss://' + v[8:]
        elif not v.startswith('rediss://'):
            v = 'rediss://' + v
        return v

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

@lru_cache()
def get_settings():
    settings = Settings()
    print(f"Final Redis URL: {settings.redis_url}")
    return settings

settings = get_settings()
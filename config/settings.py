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
    openai_api_key: str
    elevenlabs_api_key: str
    GETIMG_API_KEY: str
    s3_bucket_name: str
    resend_api_key: str
    redis_url: str = Field(..., alias="REDIS_URL")
    frontend_url: str
    backend_url: str

    # stripe
    # stripe_secret_key: str
    # stripe_webhook_secret: str
    # stripe_basic_price_id: str
    # stripe_premium_price_id: str
    # stripe_enterprise_price_id: str

    # Redis SSL Configuration
    redis_ssl_config: dict = {
        'ssl_cert_reqs': CERT_NONE
    }

    @field_validator('redis_url')
    @classmethod
    def ensure_rediss_protocol(cls, v: str) -> str:
        if v.startswith('redis://'):
            v = 'redis://' + v[8:]
        elif not v.startswith('redis://'):
            v = 'redis://' + v
        return v

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'

@lru_cache()
def get_settings():
    settings = Settings()
    return settings

settings = get_settings()
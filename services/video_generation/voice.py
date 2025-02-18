import os
import io
import tempfile
from typing import Optional
import boto3
from elevenlabs import ElevenLabs
from config.settings import settings
from services.dynamo import DynamoDBService

class VoiceGenerationError(Exception):
    """Custom exception for voice generation errors"""
    pass

def generate_voice(video_id: str, user_id: str, dynamo_service: DynamoDBService) -> str:
    """
    Generate voice audio from script using ElevenLabs and upload to S3
    Returns the S3 URL of the uploaded audio file
    """
    try:
        print("/voice.py \n we at 1")
        # Initialize ElevenLabs client
        eleven_client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
        
        # Get video details from DynamoDB
        video = dynamo_service.get_video(video_id, user_id)
        if not video:
            raise VoiceGenerationError(f"Video {video_id} not found")

        # Create temp file for audio
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            try:
                # Generate audio with timestamps
                audio_stream = eleven_client.text_to_speech.convert(
                    voice_id=video['voice'],
                    output_format="mp3_44100_128",
                    text=video['script'],
                    model_id="eleven_multilingual_v2"
                )
                
                audio_file = io.BytesIO()
                for chunk in audio_stream:
                    audio_file.write(chunk)
                audio_file.seek(0)
                
                # Upload to S3
                s3_file_name = f"audio/{video_id}.mp3"
                s3_client.upload_fileobj(audio_file, settings.s3_bucket_name, s3_file_name)

                
                # Generate S3 URL
                s3_url = s3_client.generate_presigned_url('get_object',
                                                  Params={'Bucket': settings.s3_bucket_name,
                                                          'Key': s3_file_name},
                                                  ExpiresIn=3600)  # URL expires in 1 hour
                # Update video object with audio URL
                dynamo_service.update_video(
                    video_id=video_id,
                    update_data={"audio_url": s3_url}
                )
                return s3_url
                
            except Exception as e:
                print(f"/voice.py \n Error in file handling: {str(e)}")
                raise
                
    except Exception as e:
        raise VoiceGenerationError(f"Voice generation failed: {str(e)}")
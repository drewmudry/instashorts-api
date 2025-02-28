import os
import tempfile
import requests
import boto3
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
from urllib.parse import urlparse

def compile_video(video_id, user_id, dynamo_service):
    """
    Compile a video by overlaying audio onto images.
    
    Args:
        video_id (str): The ID of the video to compile
        user_id (str): The ID of the user who owns the video
        dynamo_service: DynamoDB service instance
    
    Returns:
        str: URL of the compiled video
    """
    # Fetch video data from DynamoDB
    video_data = dynamo_service.get_video(video_id, user_id)
    
    if not video_data:
        raise ValueError(f"Video with ID {video_id} not found")
    
    if not video_data.get("audio_url") or not video_data.get("images"):
        raise ValueError("Video missing audio or images")
    
    # Create a temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download audio file
        audio_url = video_data["audio_url"]
        audio_path = os.path.join(temp_dir, "audio.mp3")
        download_file(audio_url, audio_path)
        
        # Load audio and get its duration
        audio_clip = AudioFileClip(audio_path)
        total_duration = audio_clip.duration
        
        # Sort images by index to ensure correct order
        images = sorted(video_data["images"], key=lambda x: x["index"])
        
        # Calculate how long each image should be shown
        image_duration = total_duration / len(images)
        
        # Download images and create clips
        image_clips = []
        for i, image_data in enumerate(images):
            image_url = image_data["url"]
            image_path = os.path.join(temp_dir, f"image_{i}.png")
            download_file(image_url, image_path)
            
            # Create ImageClip with duration
            img_clip = ImageClip(image_path, duration=image_duration)
            
            # Resize to standard dimensions (e.g., 1080x1920 for vertical video)
            img_clip = img_clip.resized(width=1080, height=1920)
            
            image_clips.append(img_clip)
        
        # Concatenate image clips
        video_clip = concatenate_videoclips(image_clips, method="compose")
        
        # Add audio to the video
        final_clip = video_clip.with_audio(audio_clip)
        
        # Export the final video
        output_path = os.path.join(temp_dir, f"{video_id}.mp4")
        final_clip.write_videofile(
            output_path, 
            codec="libx264", 
            audio_codec="aac", 
            temp_audiofile=os.path.join(temp_dir, "temp_audio.m4a"),
            remove_temp=True,
            fps=24
        )
        
        # Upload to S3
        video_url = upload_to_s3(output_path, video_id)
        
        # Update the video record in DynamoDB
        dynamo_service.update_video(
            video_id=video_id,
            update_data={
                "final_url": video_url
            }
        )
        
        return video_url

def download_file(url, local_path):
    """Download a file from a URL to a local path"""
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(local_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

def upload_to_s3(file_path, video_id):
    """Upload file to S3 and return the URL"""
    # Initialize S3 client
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_KEY')
    )
    
    # S3 bucket name
    bucket_name = "instashorts-content"
    
    # S3 key (path) for the video
    s3_key = f"videos/{video_id}.mp4"
    
    # Upload the file with public-read ACL
    s3_client.upload_file(
        file_path, 
        bucket_name, 
        s3_key,
        ExtraArgs={'ACL': 'public-read'}
    )
    
    # Generate a permanent URL
    url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
    
    return url
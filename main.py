from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2AuthorizationCodeBearer
from typing import Optional, List
import uuid
from datetime import datetime
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from starlette.responses import RedirectResponse, JSONResponse
from config.settings import settings
from services.dynamo import DynamoDBService
from models.videos import Video, VideoStatus
from models.series import Series
from tasks.video_processor import process_video

app = FastAPI(title="InstaShorts API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key="your-secret-key")  # Change in production

# Initialize OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

dynamo_service = DynamoDBService()

# Auth dependency
async def get_current_user(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user.get('sub')  # Google's user ID

# Auth routes
@app.get("/login/google")
async def google_login(request: Request):
    redirect_uri = request.url_for('google_auth_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google/callback")
async def google_auth_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user = await oauth.google.parse_id_token(request, token)
        request.session['user'] = user
        return RedirectResponse(url="/docs")  # Redirect to your frontend
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(e)}
        )

@app.get("/logout")
async def logout(request: Request):
    request.session.pop('user', None)
    return {"message": "Successfully logged out"}


@app.get("/")
async def root():
    return {"message": "Welcome to Instashorts!"}

# Video routes
@app.post("/videos/", response_model=Video)
async def create_video(
    title: str,
    description: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    video_data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": title,
        "description": description,
        "status": VideoStatus.PENDING,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    video = await dynamo_service.create_video(video_data)
    # Start video processing
    process_video.delay(video['id'], user_id)
    return video

@app.get("/videos/{video_id}", response_model=Video)
async def get_video(
    video_id: str,
    user_id: str = Depends(get_current_user)
):
    video = await dynamo_service.get_video(video_id, user_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    return video

@app.get("/videos/", response_model=List[Video])
async def list_videos(user_id: str = Depends(get_current_user)):
    return await dynamo_service.list_user_videos(user_id)

@app.delete("/videos/{video_id}")
async def delete_video(
    video_id: str,
    user_id: str = Depends(get_current_user)
):
    success = await dynamo_service.delete_video(video_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    return {"message": "Video deleted successfully"}


@app.post("/series/", response_model=Series)
async def create_series(
    title: str,
    description: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    series_data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": title,
        "description": description,
        "video_ids": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "is_active": True
    }
    
    return await dynamo_service.create_series(series_data)

@app.get("/series/{series_id}", response_model=Series)
async def get_series(
    series_id: str,
    user_id: str = Depends(get_current_user)
):
    series = await dynamo_service.get_series(series_id, user_id)
    if not series:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Series not found"
        )
    return series

@app.post("/series/{series_id}/videos/{video_id}")
async def add_video_to_series(
    series_id: str,
    video_id: str,
    user_id: str = Depends(get_current_user)
):
    series = await dynamo_service.get_series(series_id, user_id)
    if not series:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Series not found"
        )
    
    video = await dynamo_service.get_video(video_id, user_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    if video_id not in series['video_ids']:
        series['video_ids'].append(video_id)
        series['updated_at'] = datetime.utcnow().isoformat()
        await dynamo_service.update_series(series_id, user_id, series)
    
    return {"message": "Video added to series successfully"}
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from config.settings import settings
from routes import auth, videos, series

app = FastAPI(title="InstaShorts API")
print(f"FastAPI Redis URL: {settings.redis_url}")

# Initialize OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'prompt': 'select_account'
    }
)
app.oauth = oauth

app.add_middleware(
    CORSMiddleware,  # CORS MUST come BEFORE SessionMiddleware
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["content-type", "content-length", "access-control-allow-origin", "text/event-stream"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key="your-secret-key",  # Use a strong, randomly generated key!
    session_cookie="user_session",
    same_site="lax",  # Adjust for production
    https_only=False,  # Set to True in production
)

# Included routers
app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(series.router)

@app.get("/")
async def root():
    return {"message": "Welcome to Instashorts!"}
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from config.settings import settings
from middleware.auth import AuthMiddleware
from routes import auth, videos, series

app = FastAPI(title="InstaShorts API")
app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")  # Change in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Included routers
app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(series.router)

@app.get("/")
async def root():
    return {"message": "Welcome to Instashorts!"}
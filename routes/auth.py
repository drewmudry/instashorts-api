from fastapi import APIRouter, Request, HTTPException, status
from starlette.responses import RedirectResponse, JSONResponse
from models.user import User
from services.dynamo import DynamoDBService
from config.settings import settings
from services.email import send_welcome_email
from fastapi import BackgroundTasks

router = APIRouter(prefix="/auth", tags=["auth"])
dynamo_service = DynamoDBService()

@router.get("/login/google")
async def google_login(request: Request):
    redirect_uri = f"{settings.backend_url}/auth/google/callback"
    return await request.app.oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def google_auth_callback(request: Request, background_tasks: BackgroundTasks):
    try:
        token = await request.app.oauth.google.authorize_access_token(request)
        userinfo = token.get('userinfo')
        if userinfo:
            user = User.from_google_oauth(userinfo)
            user_data, is_new_user = await dynamo_service.create_or_update_user(user.model_dump())
            request.session['user'] = user_data
            
            # Schedule welcome email as a background task if new user
            if is_new_user:
                background_tasks.add_task(send_welcome_email, user.email, user.full_name) 
                
            return RedirectResponse(url=f"{settings.frontend_url}/dashboard")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user info"
            )
    except Exception as e:
        print(f"Auth error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(e)}
        )

@router.get("/logout")
async def logout(request: Request):
    request.session.pop('user', None)
    return {"message": "Successfully logged out"}


async def get_current_user(request: Request):
    print("All cookies:", request.cookies)  # This will show the raw cookie
    print("Session data:", request.session) # This will show the decrypted session
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user

@router.get("/me")  # This will make the endpoint available at /me
async def get_current_user(request: Request):
    try:
        user = request.session.get("user")
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        return user
    except Exception as e:
        print(f"Error in /me: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
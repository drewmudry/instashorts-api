from fastapi import APIRouter, Request, HTTPException, status
from starlette.responses import RedirectResponse, JSONResponse
from models.user import User
from services.dynamo import DynamoDBService
from config.settings import settings

router = APIRouter(tags=["auth"])
dynamo_service = DynamoDBService()

@router.get("/login/google")
async def google_login(request: Request):
    redirect_uri = "http://localhost:8000/auth/google/callback"
    return await request.app.oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth/google/callback")
async def google_auth_callback(request: Request):
    try:
        token = await request.app.oauth.google.authorize_access_token(request)
        userinfo = token.get('userinfo')
        if userinfo:
            user = User.from_google_oauth(userinfo)
            await dynamo_service.create_or_update_user(user.model_dump())
            request.session['user'] = user.model_dump()
            return RedirectResponse(url="http://localhost:3000/dashboard")
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
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method == "OPTIONS" or request.url.path in ["/", "/login/google", "/auth/google/callback"]:
            return await call_next(request)

        try:
            print("Cookies in request:", request.cookies)  # Debug
            print("Session data:", request.session)  # Debug
            
            user = request.session.get("user")
            print("User from session:", user)  # Debug
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated"
                )

            return await call_next(request)
            
        except Exception as e:
            print(f"Auth error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication error"
            )
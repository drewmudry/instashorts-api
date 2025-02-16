from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        print("LOGS (/middleware/auth.py")
        # #print(f"Request path: {request.url.path}")  # Add logging
        # print(f"Request method: {request.method}")  # Add logging
        # print(f"Request cookies: {request.cookies}")  # Add logging

        if request.method == "OPTIONS" or request.url.path in ["/", "/auth/login/google", "/auth/google/callback"]:
            return await call_next(request)

        try:
            user = request.cookies.get("user_session")
            # print(f"Found user session: {user}")  # Add logging
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated"
                )

            return await call_next(request)
            
        except Exception as e:
            print(f"Auth middleware error: {str(e)}")  # Add logging
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication error"
            )
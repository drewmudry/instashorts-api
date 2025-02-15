from fastapi import Request, Depends, HTTPException, status

async def get_current_user(request: Request):
    try:
        user = request.session.get("user")
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        return user.get('id')
    except Exception as e:
        print(f"Auth error in dependency: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication error"
        )
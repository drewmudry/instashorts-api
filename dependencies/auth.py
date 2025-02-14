from fastapi import Request, Depends, HTTPException, status

async def get_current_user(request: Request):
    user = request.state.user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user.get('id')
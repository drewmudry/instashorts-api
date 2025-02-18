from fastapi import Request, Depends, HTTPException, status
from services.dynamo import DynamoDBService

dynamo_service = DynamoDBService()

async def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    user_id = user.get('id')

    # Check if user exists in DynamoDB
    db_user = await dynamo_service.get_user(user_id)
    if not db_user:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists"
        )

    # Update session with latest subscription info
    request.session["user"]["subscription_tier"] = db_user.get('subscription_tier')
    request.session["user"]["active_subscription"] = db_user.get('active_subscription', False)

    return user_id

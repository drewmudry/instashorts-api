from pydantic import BaseModel, EmailStr
from typing import Optional

class User(BaseModel):
    id: str  # This will be the Google sub ID
    email: EmailStr
    full_name: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    disabled: Optional[bool] = False
    subscription_tier: str = None
    active_subscription: bool = False

    @classmethod
    def from_google_oauth(cls, userinfo: dict):
        return cls(
            id=userinfo['sub'],
            email=userinfo['email'],
            full_name=userinfo['name'],
            given_name=userinfo.get('given_name'),
            family_name=userinfo.get('family_name'),
            picture=userinfo.get('picture'),
            disabled=False
        )
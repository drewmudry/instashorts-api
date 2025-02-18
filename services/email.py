import os
import resend
from config.settings import settings

resend.api_key = settings.resend_api_key

def send_welcome_email(email: str):
    try:
        params: resend.Emails.SendParams = {
            "from": "InstaShorts <notifications@email.instashorts.io>",
            "to": [email],
            "subject": "Welcome to InstaShorts!",
            "html": "<strong>im gay!</strong>",
        }
        
        email_response = resend.Emails.send(params)
        return email_response
    except Exception as e:
        print(f"Failed to send welcome email to {email}: {str(e)}")
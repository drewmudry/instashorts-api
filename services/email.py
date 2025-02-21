import resend
from pathlib import Path
from config.settings import settings

resend.api_key = settings.resend_api_key

def send_welcome_email(email: str, name: str = ""):
    try:
        # Get the template path
        template_path = Path(__file__).parent / "templates" / "welcome_email.html"
        with open(template_path, "r") as file:
            html_content = file.read()
            html_content = html_content.replace("{email}", email)
            
            if name:
                html_content = html_content.replace("Hi there,", f"Hi {name},")
            
        params: resend.Emails.SendParams = {
            "from": "InstaShorts <notifications@email.instashorts.io>",
            "to": [email],
            "subject": "Welcome to InstaShorts!",
            "html": html_content,
        }
        
        email_response = resend.Emails.send(params)
        return email_response
    except Exception as e:
        print(f"Failed to send welcome email to {email}: {str(e)}")
        return None
    

def send_video_completion_email(email: str, video_data: dict):
    try:
        template_path = Path(__file__).parent / "templates" / "video_completion_email.html"
        with open(template_path, "r") as file:
            html_content = file.read()
            
            html_content = html_content.replace("{email}", email)
            html_content = html_content.replace("{video_title}", video_data.get("title", "Your Video"))
            html_content = html_content.replace("{creation_date}", video_data.get("created_at", ""))
            html_content = html_content.replace("{video_id}", str(video_data.get("id", "")))
            
            
        params: resend.Emails.SendParams = {
            "from": "InstaShorts <notifications@email.instashorts.io>",
            "to": [email],
            "subject": f"Your InstaShorts Video \"{video_data.get('title', 'Your Video')}\" Is Ready!",
            "html": html_content,
        }
        
        email_response = resend.Emails.send(params)
        return email_response
    except Exception as e:
        print(f"Failed to send video completion email to {email}: {str(e)}")
        return None
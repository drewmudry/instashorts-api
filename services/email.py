import resend
from pathlib import Path
from config.settings import settings

resend.api_key = settings.resend_api_key

def send_welcome_email(email: str, name: str = ""):
    try:
        # Get the template path
        template_path = Path(__file__).parent / "templates" / "welcome_email.html"
        
        # Read the template and replace placeholders
        with open(template_path, "r") as file:
            html_content = file.read()
            html_content = html_content.replace("{email}", email)
            
            # If we have a name, personalize the greeting
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
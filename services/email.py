def send_welcome_email(email: str, full_name: str):
    print(f"Sending welcome email to {email} ({full_name})")
    # In a real application, you would use an email service here
    # For example, using 'smtplib' for SMTP, or libraries for
    # SendGrid, Mailgun, AWS SES, etc.
    # Example placeholder for actual email sending:
    # try:
    #     # Email sending logic here
    #     print("Email sent successfully")
    # except Exception as e:
    #     print(f"Error sending email: {e}")
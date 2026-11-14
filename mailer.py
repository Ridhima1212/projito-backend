# backend/mailer.py
import os
import requests

def send_contact_email(name: str, email: str, subject: str, message: str) -> bool:
    """
    Sends an email notification via EmailJS REST API.
    Reads EMAILJS_SERVICE_ID, EMAILJS_TEMPLATE_ID, EMAILJS_PUBLIC_KEY, and EMAILJS_PRIVATE_KEY from .env.
    """
    service_id = os.environ.get("EMAILJS_SERVICE_ID")
    template_id = os.environ.get("EMAILJS_TEMPLATE_ID")
    public_key = os.environ.get("EMAILJS_PUBLIC_KEY")
    private_key = os.environ.get("EMAILJS_PRIVATE_KEY")
    to_email = os.environ.get("EMAILJS_TO_EMAIL", "snehagade76@gmail.com")

    if not service_id or not template_id or not public_key:
        print("\n📬 [EMAIL NOTIFICATION SIMULATION]")
        print(f"👉 From: {name} <{email}>")
        print(f"👉 To (Admin): {to_email}")
        print(f"👉 Subject: [AutoProjectEval Contact] {subject}")
        print(f"👉 Message:\n{message}\n")
        return False

    url = "https://api.emailjs.com/api/v1.0/email/send"
    headers = {"Content-Type": "application/json"}

    payload = {
        "service_id": service_id,
        "template_id": template_id,
        "user_id": public_key,
        "template_params": {
            "name": name,
            "from_name": name,
            "email": email,
            "from_email": email,
            "reply_to": email,
            "subject": subject,
            "message": message,
            "to_email": to_email
        }
    }

    if private_key:
        payload["accessToken"] = private_key

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=12)
        if response.status_code == 200:
            print(f"✅ Contact email delivered via EmailJS to {to_email}!")
            return True
        else:
            print(f"⚠️ EmailJS response error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"⚠️ EmailJS request failed: {e}")
        return False

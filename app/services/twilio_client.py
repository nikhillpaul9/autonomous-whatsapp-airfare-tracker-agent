import os
from twilio.rest import Client

def send_whatsapp_message(to_phone: str, body_text: str, media_urls: list = None):
    """Sends a standard WhatsApp message with multiple optional attachments."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    
    # Safely strip any existing 'whatsapp:' prefixes from the .env to prevent double-prefixing
    raw_from = os.getenv("TWILIO_WHATSAPP_NUMBER", "+14155238886").replace("whatsapp:", "").strip()
    raw_to = to_phone.replace("whatsapp:", "").strip()
    
    client = Client(account_sid, auth_token)
    
    msg_kwargs = {
        "from_": f"whatsapp:{raw_from}",
        "body": body_text,
        "to": f"whatsapp:{raw_to}"
    }
    
    # If a list of URLs is provided, attach them all
    if media_urls:
        valid_urls = [url for url in media_urls if url]
        if valid_urls:
            msg_kwargs["media_url"] = valid_urls
        
    try:
        message = client.messages.create(**msg_kwargs)
        print(f"✅ WhatsApp Sent with {len(msg_kwargs.get('media_url', []))} attachments! SID: {message.sid}")
        return message.sid
    except Exception as e:
        print(f"❌ Twilio Error: {e}")
        return None
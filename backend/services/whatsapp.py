import os
from dotenv import load_dotenv

load_dotenv()

def normalize_indian_mobile(mobile: str) -> str:
    value = str(mobile or "").strip().replace(" ", "").replace("-", "")
    if value.startswith("whatsapp:"):
        value = value.replace("whatsapp:", "", 1)
    if value.startswith("+"):
        return value
    if value.startswith("91") and len(value) == 12:
        return "+" + value
    if len(value) == 10:
        return "+91" + value
    return value

def send_whatsapp(to_mobile: str, body: str) -> bool:
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    sender = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    if not sid or not token:
        print(f"[WHATSAPP DEMO] To={to_mobile} | {body}")
        return False

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        client.messages.create(
            from_=sender,
            to=f"whatsapp:{normalize_indian_mobile(to_mobile)}",
            body=body
        )
        return True
    except Exception as exc:
        print("[WHATSAPP ERROR]", exc)
        return False

import os
import smtplib
from email.message import EmailMessage


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Optional SMTP email channel. If credentials are absent, demo keeps running."""
    if not to_email:
        return False

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", username or "")

    if not all([host, username, password, sender]):
        print(f"\n[EMAIL DEMO]\nTo: {to_email}\nSubject: {subject}\nBody:\n{body}\n{'-' * 40}")
        return False

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        msg.set_content(body)

        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
        return True
    except Exception as exc:
        print(f"[EMAIL ERROR] {exc}")
        return False


def send_registration_email(to_email: str, farmer_name: str, farmer_id: str, mobile_number: str) -> bool:
    subject = "🌾 Swagat Hai! Aapka Kisan Registration Safal Hua"
    body = f"""Namaste {farmer_name} ji,

Hamare portal par aapka swagat hai. Aapka registration safal ho chuka hai.

Login Vivaran:
- Kisan ID (Farmer ID): {farmer_id}
- Panjikrit Mobile No: {mobile_number}

Aap apne Farmer ID aur registered mobile number se login karke apna slot book kar sakte hain.

Dhanyawad!
Kisan Sahayata Kendra
"""
    return send_email(to_email, subject, body)


def send_token_booking_email(to_email: str, farmer_name: str, token_id: str, slot_date: str, slot_time: str, place: str) -> bool:
    subject = f"🎟️ Token Confirmed: #{token_id}"
    body = f"""Namaste {farmer_name} ji,

Aapka token safaltapoorvak book ho gaya hai.

Booking Vivaran:
- Token ID: {token_id}
- Tareekh (Date): {slot_date}
- Samay (Time Slot): {slot_time}
- Sthan (Place/Kendra): {place}

Kripya nirdharit samay par apne dastavez aur token ID ke sath kendra par upasthit hon.

Dhanyawad!
"""
    return send_email(to_email, subject, body)


def send_slot_reminder_email(to_email: str, farmer_name: str, token_id: str, slot_time: str, place: str) -> bool:
    subject = f"⏰ Yaad Dihani: Aapka Slot 1 Ghante Mein Hai (Token #{token_id})"
    body = f"""Namaste {farmer_name} ji,

Yeh ek suchna hai ki aapka slot lagbhag 1 ghante baad hai.

Slot Vivaran:
- Token ID: {token_id}
- Samay: {slot_time}
- Sthan: {place}

Kripya samay se kendra par pahuchein taaki bina kisi rukawat ke kaam poora ho sake.

Dhanyawad!
"""
    return send_email(to_email, subject, body)


def send_completion_email(to_email: str, farmer_name: str, token_id: str, weight: str, total_price: str, completion_time: str) -> bool:
    subject = f"✅ Kaam Poora Hua (Receipt - Token #{token_id})"
    body = f"""Namaste {farmer_name} ji,

Aapki fasal/anaj ki tulaai aur prakriya safaltapoorvak poori ho gayi hai.

Raseed Vivaran:
- Token ID: {token_id}
- Kul Wajan (Weight): {weight}
- Kul Rashi (Total Price): {total_price}
- Samapti Samay: {completion_time}

Hamari sewayen lene ke liye aapka bahut-bahut aabhar.

Shubhkaamnayein,
Kisan Kalyan Kendra
"""
    return send_email(to_email, subject, body)

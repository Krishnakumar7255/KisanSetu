# KisanSetu Email Notifications

The backend now supports four email events:

1. Farmer registration: welcome + Farmer ID + mobile.
2. Token booking: token + date + slot + procurement centre.
3. One-hour reminder: automatic reminder for today's waiting booking.
4. Procurement completion: weight + amount + completion time.

## Enable SMTP

Copy the SMTP values into `backend/.env`.

For Gmail, use an **App Password**, not your normal Gmail password:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-character-app-password
SMTP_FROM=your-email@gmail.com
```

The existing WhatsApp/in-app notification flow is unchanged.

If SMTP values are absent, the backend prints an `[EMAIL DEMO]` message in the terminal instead of failing the main operation.

The reminder worker runs with the backend and checks every 60 seconds. It sends when a waiting booking is approximately 1 hour away and uses the notifications table to avoid duplicate reminder emails.

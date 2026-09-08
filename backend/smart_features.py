from datetime import datetime, timezone, timedelta
from collections import Counter

BIHAR_TZ = timezone(timedelta(hours=5, minutes=30), name='Asia/Kolkata')

WEATHER_PROFILES = [
    ('Clear', 0, 'Normal operations'),
    ('Hot', 8, 'Heat buffer added for farmer comfort'),
    ('Rain', 15, 'Rain buffer added for safe arrival'),
    ('Heavy Rain', 25, 'Capacity reduced for safety'),
]


def demo_weather(centre_id: str, date_str: str):
    # Deterministic demo weather adapter. Replace with IMD/authorized weather API in production.
    seed = sum(ord(c) for c in f'{centre_id}:{date_str}')
    name, buffer_min, note = WEATHER_PROFILES[seed % len(WEATHER_PROFILES)]
    return {
        'mode': 'deterministic-operational-estimate',
        'condition': name,
        'buffer_min': buffer_min,
        'note': note,
        'source': 'KisanSetu operational estimate; not a live weather feed',
    }


def suspicious_booking_signals(bookings):
    now = datetime.now(BIHAR_TZ)
    by_farmer = Counter(b.get('farmer_id') for b in bookings if b.get('farmer_id'))
    signals = []
    for farmer_id, count in by_farmer.items():
        farmer_rows = [b for b in bookings if b.get('farmer_id') == farmer_id]
        cancellations = sum(b.get('status') == 'cancelled' for b in farmer_rows)
        no_shows = sum(b.get('status') in ('skipped', 'cancelled') and b.get('checked_in') is False for b in farmer_rows)
        score = 0
        reasons = []
        if count >= 4:
            score += 35; reasons.append('high booking frequency')
        if cancellations >= 2:
            score += 25; reasons.append('repeated cancellations')
        if no_shows >= 2:
            score += 20; reasons.append('repeated no-show pattern')
        recent = 0
        for b in farmer_rows:
            raw = b.get('created_at')
            try:
                if raw and (now - datetime.fromisoformat(str(raw).replace('Z','+00:00')).astimezone(BIHAR_TZ)).total_seconds() <= 86400:
                    recent += 1
            except Exception:
                pass
        if recent >= 3:
            score += 20; reasons.append('multiple bookings in 24h')
        if score >= 40:
            signals.append({'farmer_id': farmer_id, 'risk_score': min(100, score), 'level': 'HIGH' if score >= 70 else 'MEDIUM', 'reasons': reasons})
    return sorted(signals, key=lambda x: x['risk_score'], reverse=True)

from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException

SLOTS = [
    '08:00 - 10:00',
    '10:00 - 12:00',
    '12:00 - 14:00',
    '14:00 - 16:00',
    '16:00 - 18:00',
]

def parse_slot_start(slot: str):
    start = slot.split('-')[0].strip()
    return datetime.strptime(start, '%H:%M').time()

def parse_slot_end(slot: str):
    end = slot.split('-')[1].strip()
    return datetime.strptime(end, '%H:%M').time()

def validate_booking_time(booking_date: str, slot: str):
    try:
        selected = date.fromisoformat(booking_date)
    except ValueError:
        raise HTTPException(400, 'Invalid booking date.')

    if slot not in SLOTS:
        raise HTTPException(400, 'Invalid time slot.')

    BIHAR_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
    now = datetime.now(BIHAR_TZ)
    if selected < now.date():
        raise HTTPException(400, 'Past date booking is not allowed.')
    if selected == now.date() and parse_slot_start(slot) <= now.time():
        raise HTTPException(400, f'{slot} slot has already started or passed. Please select a later slot.')

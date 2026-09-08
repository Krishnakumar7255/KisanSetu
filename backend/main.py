import os
import math
import re
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional
import threading
import time
import secrets
import base64
import hashlib
import hmac
import json
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from fastapi import Header

from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.lib.units import mm

import db as db_module
from db import supabase, SUPABASE_ENABLED, execute_select
from time_utils import SLOTS, validate_booking_time, parse_slot_start, parse_slot_end
from ai_engine import build_model, features, predict, explain, slot_start, operational_insights, anomaly_flags
from services.whatsapp import send_whatsapp
from smart_features import demo_weather, suspicious_booking_signals
from services.email import (
    send_email,
    send_registration_email,
    send_token_booking_email,
    send_slot_reminder_email,
    send_completion_email,
)

ENV_FILE = Path(__file__).resolve().parent / ".env"
PROJECT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
# Backend .env has priority; project-root .env is supported as a fallback.
load_dotenv(dotenv_path=ENV_FILE, override=True)
load_dotenv(dotenv_path=PROJECT_ENV_FILE, override=False)
from sih_v10 import router as sih_router, sign_qr as sign_sih_qr, verify_qr as verify_sih_qr
BIHAR_TZ = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")

# Queue performance cache. Live position uses only today's rows; the expensive
# historical AI training data is refreshed in the background/short TTL and is
# NEVER fetched on every WebSocket heartbeat.
_QUEUE_MODEL_CACHE = {}
_QUEUE_MODEL_CACHE_TTL = 120.0
_QUEUE_HISTORY_CACHE = {}
_QUEUE_HISTORY_CACHE_TTL = 120.0
_BACKGROUND = ThreadPoolExecutor(max_workers=4)
_CENTRE_CACHE = {}
_CENTRE_CACHE_TTL = 300.0
_QUEUE_SNAPSHOT_CACHE = {}
_QUEUE_SNAPSHOT_CACHE_TTL = 0.75

def _cached_queue_model(centre_id, counters):
    now = time.monotonic()
    cached = _QUEUE_MODEL_CACHE.get(centre_id)
    if cached and now - cached[0] < _QUEUE_MODEL_CACHE_TTL:
        return cached[1], cached[2]
    h = _QUEUE_HISTORY_CACHE.get(centre_id)
    if not h or now - h[0] >= _QUEUE_HISTORY_CACHE_TTL:
        # Keep the expensive query out of the live queue hot path after the first load.
        history = rows("bookings", centre_id=centre_id)
        _QUEUE_HISTORY_CACHE[centre_id] = (now, history)
    else:
        history = h[1]
    model, training_count = build_model(history, counters)
    _QUEUE_MODEL_CACHE[centre_id] = (now, model, training_count)
    return model, training_count

app = FastAPI(title="KisanSetu V9 API", version="9.0.0")

@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    """Return configuration/runtime dependency failures as a useful 503."""
    message = str(exc)
    if "Supabase authentication failed" in message or "Supabase is not configured" in message:
        return JSONResponse(status_code=503, content={"detail": message, "code": "SUPABASE_CONFIG_ERROR"})
    return JSONResponse(status_code=500, content={"detail": message})
origins = [os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"), "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set(origins)),
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(sih_router)

CENTRES = [
    {"centre_id":"C001","district":"Araria","city":"Araria","lat":26.1558,"lon":87.5017,"counters":3},
    {"centre_id":"C002","district":"Arwal","city":"Arwal","lat":25.2492,"lon":84.6810,"counters":2},
    {"centre_id":"C003","district":"Aurangabad","city":"Aurangabad","lat":24.7521,"lon":84.3742,"counters":3},
    {"centre_id":"C004","district":"Banka","city":"Banka","lat":24.8874,"lon":86.9198,"counters":2},
    {"centre_id":"C005","district":"Begusarai","city":"Begusarai","lat":25.4182,"lon":86.1272,"counters":4},
    {"centre_id":"C006","district":"Bhagalpur","city":"Bhagalpur","lat":25.2425,"lon":86.9842,"counters":4},
    {"centre_id":"C007","district":"Bhojpur","city":"Ara","lat":25.5560,"lon":84.6633,"counters":3},
    {"centre_id":"C008","district":"Buxar","city":"Buxar","lat":25.5647,"lon":83.9777,"counters":2},
    {"centre_id":"C009","district":"Darbhanga","city":"Darbhanga","lat":26.1542,"lon":85.8918,"counters":4},
    {"centre_id":"C010","district":"East Champaran","city":"Motihari","lat":26.6499,"lon":84.9161,"counters":4},
    {"centre_id":"C011","district":"Gaya","city":"Gaya","lat":24.7955,"lon":84.9994,"counters":5},
    {"centre_id":"C012","district":"Gopalganj","city":"Gopalganj","lat":26.4672,"lon":84.4402,"counters":3},
    {"centre_id":"C013","district":"Jamui","city":"Jamui","lat":24.9260,"lon":86.2249,"counters":2},
    {"centre_id":"C014","district":"Jehanabad","city":"Jehanabad","lat":25.2070,"lon":84.9874,"counters":3},
    {"centre_id":"C015","district":"Kaimur","city":"Bhabua","lat":25.0400,"lon":83.6150,"counters":2},
    {"centre_id":"C016","district":"Katihar","city":"Katihar","lat":25.5394,"lon":87.5788,"counters":4},
    {"centre_id":"C017","district":"Khagaria","city":"Khagaria","lat":25.5022,"lon":86.4671,"counters":3},
    {"centre_id":"C018","district":"Kishanganj","city":"Kishanganj","lat":26.1025,"lon":87.9553,"counters":2},
    {"centre_id":"C019","district":"Lakhisarai","city":"Lakhisarai","lat":25.1574,"lon":86.0952,"counters":2},
    {"centre_id":"C020","district":"Madhepura","city":"Madhepura","lat":25.9213,"lon":86.7927,"counters":3},
    {"centre_id":"C021","district":"Madhubani","city":"Madhubani","lat":26.3489,"lon":86.0717,"counters":4},
    {"centre_id":"C022","district":"Munger","city":"Munger","lat":25.3708,"lon":86.4734,"counters":3},
    {"centre_id":"C023","district":"Muzaffarpur","city":"Muzaffarpur","lat":26.1209,"lon":85.3647,"counters":5},
    {"centre_id":"C024","district":"Nalanda","city":"Bihar Sharif","lat":25.1980,"lon":85.5149,"counters":4},
    {"centre_id":"C025","district":"Nawada","city":"Nawada","lat":24.8860,"lon":85.5430,"counters":3},
    {"centre_id":"C026","district":"Patna","city":"Patna","lat":25.5941,"lon":85.1376,"counters":6},
    {"centre_id":"C027","district":"Purnia","city":"Purnea","lat":25.7771,"lon":87.4753,"counters":4},
    {"centre_id":"C028","district":"Rohtas","city":"Sasaram","lat":24.9490,"lon":84.0060,"counters":3},
    {"centre_id":"C029","district":"Saharsa","city":"Saharsa","lat":25.8830,"lon":86.6006,"counters":3},
    {"centre_id":"C030","district":"Samastipur","city":"Samastipur","lat":25.8629,"lon":85.7810,"counters":4},
    {"centre_id":"C031","district":"Saran","city":"Chhapra","lat":25.7796,"lon":84.7499,"counters":4},
    {"centre_id":"C032","district":"Sheikhpura","city":"Sheikhpura","lat":25.1390,"lon":85.8551,"counters":2},
    {"centre_id":"C033","district":"Sheohar","city":"Sheohar","lat":26.5147,"lon":85.2940,"counters":2},
    {"centre_id":"C034","district":"Sitamarhi","city":"Sitamarhi","lat":26.5887,"lon":85.5016,"counters":3},
    {"centre_id":"C035","district":"Siwan","city":"Siwan","lat":26.2200,"lon":84.3560,"counters":3},
    {"centre_id":"C036","district":"Supaul","city":"Supaul","lat":26.1260,"lon":86.6050,"counters":3},
    {"centre_id":"C037","district":"Vaishali","city":"Hajipur","lat":25.6865,"lon":85.2162,"counters":4},
    {"centre_id":"C038","district":"West Champaran","city":"Bettiah","lat":27.0992,"lon":84.0900,"counters":4},
]
for c in CENTRES:
    c["name"] = f"{c['district']} Procurement Centre"
    c["address"] = f"{c['city']}, {c['district']}, Bihar"

DISTRICT_TO_CENTRE = {c["district"]: c["centre_id"] for c in CENTRES}

AUTH_SECRET = os.getenv("AUTH_SECRET", "").strip()
if not AUTH_SECRET:
    # Local development should not crash the entire API when .env has not
    # been created yet. A fresh process-local secret is safe for development
    # and intentionally invalidates old tokens after restart. Production
    # deployments should always provide a persistent AUTH_SECRET.
    AUTH_SECRET = secrets.token_urlsafe(48)
    os.environ["AUTH_SECRET"] = AUTH_SECRET
    print("[KisanSetu] WARNING: AUTH_SECRET is not configured; generated a temporary development secret.")

def issue_token(role, subject):
    payload = {"role": role, "sub": subject, "exp": int(time.time()) + 60 * 60 * 12}
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"

def verify_token(authorization: Optional[str], expected_role: Optional[str] = None):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentication required.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        raw, sig = token.split(".", 1)
        expected = hmac.new(AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired")
        if expected_role and payload.get("role") != expected_role:
            raise ValueError("role")
        return payload
    except Exception:
        raise HTTPException(401, "Invalid or expired session.")


def resolve_token_booking(token: str, authorization: Optional[str] = None):
    """Resolve a centre-scoped token safely using the authenticated owner/centre."""
    auth = verify_token(authorization)
    q = db_required().table("bookings").select("*").eq("token", token)
    if auth.get("role") == "farmer":
        q = q.eq("farmer_id", auth.get("sub"))
    elif auth.get("role") == "centre":
        q = q.eq("centre_id", auth.get("sub"))
    elif auth.get("role") != "admin":
        raise HTTPException(403, "Access denied.")
    data = q.order("created_at", desc=True).limit(1).execute().data or []
    if not data:
        raise HTTPException(404, "Token not found")
    return auth, data[0]

class FarmerIn(BaseModel):
    mobile: str = Field(min_length=10, max_length=10, pattern=r"^[0-9]{10}$")
    email: Optional[str] = None
    name: str
    village: str
    district: str
    crop: str = "Wheat"
    centre_id: str = "C014"

class CentreIn(BaseModel):
    employee_id: Optional[str] = None
    mobile: str
    name: str
    centre_id: Optional[str] = None
    district: str
    address: str
    counters: int = Field(default=2, ge=1, le=20)

class LoginIn(BaseModel):
    mobile: str
    role: str
    username: Optional[str] = None
    password: Optional[str] = None
    farmer_id: Optional[str] = None
    employee_id: Optional[str] = None

class BookingIn(BaseModel):
    farmer_id: str
    centre_id: str
    crop: str
    quantity_kg: float
    date: str
    slot: str

class QueueAction(BaseModel):
    token: str
    action: str

class AdminRateIn(BaseModel):
    crop: str
    rate_per_kg: float = Field(gt=0, le=100000)
    quality_grade: str = "FAQ"

class PaymentIn(BaseModel):
    farmer_id: str
    token: str

class ProcurementIn(BaseModel):
    farmer_id: str
    centre_id: str
    token: str
    crop: str
    quantity_kg: float
    gross_weight_kg: Optional[float] = None
    tare_weight_kg: Optional[float] = 0
    moisture_percent: Optional[float] = None
    quality_grade: str = "FAQ"
    rate_per_kg: Optional[float] = None
    employee_id: Optional[str] = None

SERVICE_BASE_MIN = {"Wheat": 9.0, "Rice": 11.0, "Maize": 10.0, "Mustard": 8.0}

def service_minutes(crop="Wheat", quantity_kg=100):
    base = SERVICE_BASE_MIN.get(str(crop), 10.0)
    return round(max(5.0, min(30.0, base + max(0.0, float(quantity_kg or 0) - 200.0) / 180.0)), 1)

def dynamic_capacity(counters, crop="Wheat", quantity_kg=100, safety=0.85):
    counters = max(1, int(counters or 1))
    minutes = service_minutes(crop, quantity_kg)
    raw = counters * (120.0 / minutes)
    return max(1, int(math.floor(raw * safety)))

def no_show_prediction(booking, now=None):
    now = now or datetime.now(BIHAR_TZ)
    if booking.get("checked_in"):
        return {"risk":"LOW","score":5,"reason":"Farmer is already checked in."}
    if booking.get("status") != "waiting":
        return {"risk":"LOW","score":0,"reason":"Token is not waiting."}
    try:
        start = datetime.strptime(booking.get("slot", "").split("-")[0].strip(), "%H:%M").time()
        slot_dt = datetime.combine(now.date(), start, tzinfo=BIHAR_TZ)
        mins = (slot_dt - now).total_seconds()/60
    except Exception:
        mins = 999
    score = 15
    reasons=[]
    if mins < 0: score += 35; reasons.append("slot has started")
    elif mins <= 20: score += 20; reasons.append("arrival window is close")
    if booking.get("deferred_at"): score += 25; reasons.append("previously deferred")
    if mins > 120: score += 10; reasons.append("early booking")
    score=min(95,score)
    risk="HIGH" if score>=65 else ("MEDIUM" if score>=40 else "LOW")
    return {"risk":risk,"score":score,"reason":", ".join(reasons) or "No strong no-show signal."}

def audit(event, centre_id=None, farmer_id=None, token=None, details=None):
    try:
        db_required().table("audit_logs").insert({"event":event,"centre_id":centre_id,"farmer_id":farmer_id,"token":token,"details":details or {}}).execute()
    except Exception as exc:
        print("audit log error:", exc)

def find_centre(centre_id):
    now = time.monotonic()
    cached = _CENTRE_CACHE.get(centre_id)
    if cached and now - cached[0] < _CENTRE_CACHE_TTL:
        return cached[1]
    found = None
    if SUPABASE_ENABLED:
        try:
            found = first("centres", centre_id=centre_id)
        except Exception:
            pass
    found = found or next((c for c in CENTRES if c["centre_id"] == centre_id), None)
    if found:
        _CENTRE_CACHE[centre_id] = (now, found)
    return found

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def db_required():
    # Always read the current client from db_module. This is important because
    # db.reconnect() replaces the client after a dropped HTTP connection.
    if not SUPABASE_ENABLED or db_module.supabase is None:
        raise HTTPException(503, "Supabase is not configured. Add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to backend/.env")
    return db_module.supabase

def rows(table, **filters):
    try:
        return execute_select(table, filters)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

def first(table, **filters):
    data = rows(table, **filters)
    return data[0] if data else None

def notify(farmer_id, title, message):
    farmer = first("farmers", farmer_id=farmer_id)
    payload = {"farmer_id": farmer_id, "title": title, "message": message}
    try:
        db_required().table("notifications").insert(payload).execute()
    except Exception as exc:
        print("notification db error:", exc)
    if farmer:
        try: send_whatsapp(farmer.get("mobile", ""), f"{title}\n{message}")
        except Exception: pass
        if farmer.get("email"):
            try: send_email(farmer["email"], f"KisanSetu: {title}", message)
            except Exception: pass

def auto_skip_expired_waiting(centre_id=None):
    """Move stale waiting bookings to skipped and persist the audit fields.
    A waiting token is auto-skipped 3 hours after its booked slot END time.
    """
    today = datetime.now(BIHAR_TZ).date().isoformat()
    data = rows("bookings", date=today, **({"centre_id": centre_id} if centre_id else {}))
    now = datetime.now(BIHAR_TZ)
    for b in data:
        if b.get("status") != "waiting":
            continue
        try:
            slot_end = parse_slot_end(b["slot"])
            deadline = datetime.combine(datetime.fromisoformat(b["date"]).date(), slot_end, tzinfo=BIHAR_TZ) + timedelta(hours=3)
        except Exception:
            continue
        if now >= deadline:
            reason = "Auto-skipped: farmer did not arrive within 3 hours after slot end."
            db_required().table("bookings").update({
                "status": "skipped",
                "skipped_at": now.isoformat(),
                "skip_reason": reason,
            }).eq("booking_id", b["booking_id"]).eq("status", "waiting").execute()
            notify(b["farmer_id"], "Slot Auto-Skipped", f"Token {b['token']} was skipped because the 3-hour grace period after your slot ended.")

def email_reminder_worker():
    """Send one email reminder roughly one hour before today's waiting slot."""
    while True:
        try:
            if SUPABASE_ENABLED:
                today = datetime.now(BIHAR_TZ).date().isoformat()
                now = datetime.now(BIHAR_TZ)
                bookings = rows("bookings", date=today)
                for b in bookings:
                    if b.get("status") != "waiting":
                        continue
                    try:
                        slot_start = datetime.strptime(b["slot"].split("-")[0].strip(), "%H:%M").time()
                        slot_dt = datetime.combine(now.date(), slot_start, tzinfo=BIHAR_TZ)
                    except Exception:
                        continue

                    minutes_until = (slot_dt - now).total_seconds() / 60
                    if not (55 <= minutes_until <= 65):
                        continue

                    farmer = first("farmers", farmer_id=b.get("farmer_id")) or {}
                    email = farmer.get("email")
                    if not email:
                        continue

                    # notifications table acts as the durable de-duplication marker.
                    already_sent = rows(
                        "notifications",
                        farmer_id=b.get("farmer_id"),
                        title="Slot Reminder",
                    )
                    if any(str(b.get("token")) in str(n.get("message", "")) for n in already_sent):
                        continue

                    centre = find_centre(b.get("centre_id")) or {}
                    place = (centre.get("name") or f"{centre.get('district', '')} Procurement Centre").strip()
                    send_slot_reminder_email(
                        email,
                        farmer.get("name", "Kisan"),
                        str(b.get("token", "")),
                        b.get("slot", ""),
                        place,
                    )
                    try:
                        db_required().table("notifications").insert({
                            "farmer_id": b.get("farmer_id"),
                            "title": "Slot Reminder",
                            "message": f"Reminder email sent for token {b.get('token')} at {b.get('slot')}.",
                        }).execute()
                    except Exception as exc:
                        print("[EMAIL] reminder marker error:", exc)
        except Exception as exc:
            print("[KisanSetu] email reminder error:", exc)
        time.sleep(60)


def auto_skip_worker():
    while True:
        try:
            if SUPABASE_ENABLED:
                auto_skip_expired_waiting()
        except Exception as exc:
            print("[KisanSetu] auto-skip error:", exc)
        time.sleep(60)

def _slot_start_minutes(slot):
    try:
        t = datetime.strptime(slot.split("-")[0].strip(), "%H:%M").time()
        return t.hour * 60 + t.minute
    except Exception:
        return 10**9

def _queue_priority(b):
    # Slot-aware queue: checked-in farmers first; deferred/no-show waiting tokens
    # never block the next eligible farmer. Earlier slot always outranks later slot.
    deferred = 1 if b.get("deferred_at") else 0
    checked = 0 if b.get("checked_in") else 1
    return (deferred, _slot_start_minutes(b.get("slot", "")), checked, b.get("created_at", ""))

def _decorate_queue(data):
    now = datetime.now(BIHAR_TZ)
    current_min = now.hour * 60 + now.minute
    active = [b for b in data if b.get("status") in ("waiting", "confirmed", "serving", "procurement_pending")]
    for b in active:
        start = _slot_start_minutes(b.get("slot", ""))
        b["eligible_now"] = bool(b.get("checked_in")) or start <= current_min
        b["queue_priority"] = "checked-in" if b.get("checked_in") else ("slot-active" if b["eligible_now"] else "upcoming")
    active.sort(key=_queue_priority)
    for i, b in enumerate(active, 1):
        b["queue_rank"] = i
    return active

def queue_for(centre_id):
    now_mono = time.monotonic()
    cached = _QUEUE_SNAPSHOT_CACHE.get(centre_id)
    if cached and now_mono - cached[0] < _QUEUE_SNAPSHOT_CACHE_TTL:
        return copy.deepcopy(cached[1])
    # Auto-skip is handled by the dedicated worker; never run extra UPDATE/notify
    # work inside the latency-sensitive queue request.
    today = datetime.now(BIHAR_TZ).date().isoformat()
    data = rows("bookings", centre_id=centre_id, date=today)
    decorated = _decorate_queue(data)
    _QUEUE_SNAPSHOT_CACHE[centre_id] = (now_mono, decorated)
    return copy.deepcopy(decorated)

def queue_state(centre_id, user_token=None):
    centre = find_centre(centre_id)
    today = datetime.now(BIHAR_TZ).date().isoformat()
    # Today's live queue is the hot path. Query it once and match the farmer token
    # locally. Only fall back to a single booking lookup when the token is not in
    # today's queue (normally a future scheduled booking).
    items = queue_for(centre_id)
    matched = next((b for b in items if b["token"] == user_token), None) if user_token else None
    # A future booking is confirmed, but it must not be treated as today's live queue.
    if user_token and not matched:
        future_booking = first("bookings", token=user_token, centre_id=centre_id)
        if future_booking and future_booking.get("date") != today and future_booking.get("status") in ("waiting", "confirmed", "serving", "procurement_pending"):
            start = parse_slot_start(future_booking.get("slot", SLOTS[0]))
            booking_dt = datetime.combine(datetime.fromisoformat(future_booking["date"]).date(), start, tzinfo=BIHAR_TZ)
            mins = max(0, math.ceil((booking_dt - datetime.now(BIHAR_TZ)).total_seconds()/60))
            return {"centre": centre, "user_token": future_booking.get("token"), "now_serving": "--",
                    "recommended_next": None, "ahead": 0, "estimated_wait_min": None,
                    "recommended_departure_in_min": max(0, mins-30), "queue_status": "Confirmed",
                    "queue_phase": "scheduled", "slot_confirmed": True, "booking_date": future_booking.get("date"),
                    "slot": future_booking.get("slot"), "utilization_percent": 0,
                    "average_service_min": service_minutes(future_booking.get("crop", "Wheat"), future_booking.get("quantity_kg", 100)),
                    "progress": 0, "smart_arrival": {"recommended_departure_in_min": max(0, mins-30), "arrival_buffer_min": 10,
                    "confidence": "medium", "message": "Your slot is confirmed. Live queue will start on the booking date."},
                    "status": future_booking.get("status"),
                    "ai": {"enabled": True, "model": "explainable-ridge-regression", "training_samples": 0,
                    "confidence": "scheduled", "explanation": ["Slot is confirmed for the booked date."]}}
    serving = next((b for b in items if b["status"] == "serving"), None)
    eligible = [b for b in items if b.get("eligible_now") and b.get("status") == "waiting" and not b.get("deferred_at")]
    recommended = eligible[0] if eligible else (serving or None)
    # Completed/skipped/cancelled bookings are deliberately NOT treated as live tokens.
    live_token = user_token if matched else "--"
    ahead = 0
    if matched:
        for b in items:
            if b["token"] == user_token: break
            if b.get("status") in ("waiting", "serving") and b.get("eligible_now") and not b.get("deferred_at"):
                ahead += 1
    counters = max(1, int(centre["counters"] if centre else 1))
    w, training_count = _cached_queue_model(centre_id, counters)
    x = features(ahead=ahead, counters=counters, quantity=float(matched.get("quantity_kg") or 0) if matched else 0,
                 slot=matched.get("slot", SLOTS[0]) if matched else SLOTS[0],
                 checked_in=bool(matched.get("checked_in")) if matched else False)
    base_wait = max(0, math.ceil(ahead * 5 / counters))
    ai_wait = predict(w, x) if w else max(2, round(base_wait * 1.05, 1))
    if matched and not matched.get("eligible_now"):
        ai_wait = max(ai_wait, max(0, slot_start(matched.get("slot", SLOTS[0])) - datetime.now(BIHAR_TZ).hour*60-datetime.now(BIHAR_TZ).minute))
    queue_status = "Your turn" if matched and ahead == 0 else ("Approaching" if matched and ahead <= 2 else ("Waiting" if matched else "No active booking"))
    avg_service = service_minutes(matched.get("crop", "Wheat"), matched.get("quantity_kg", 100)) if matched else service_minutes()
    utilization = round(min(100, len(items) / max(1, dynamic_capacity(counters)) * 100))
    total = max(1, len(items))
    progress = min(100, round((1 - ahead / total) * 100)) if matched else 0
    departure = max(0, round(ai_wait - 10))
    smart = {"recommended_departure_in_min":departure,"arrival_buffer_min":10,"confidence":"high" if training_count >= 10 else "medium","message":f"Reach the centre about 10 minutes before your predicted turn."}
    if matched:
        smart["no_show"] = no_show_prediction(matched)
    return {"centre": centre, "user_token": live_token,
            "now_serving": serving["token"] if serving else (recommended["token"] if recommended else "--"),
            "recommended_next": recommended, "ahead": ahead, "estimated_wait_min": ai_wait,
            "recommended_departure_in_min": departure, "queue_status": queue_status,
            "utilization_percent": utilization, "average_service_min": avg_service, "progress": progress, "smart_arrival": smart,
            "status": matched["status"] if matched else "none", "ai": {"enabled": True, "model": "explainable-ridge-regression",
            "training_samples": training_count, "confidence": "high" if training_count >= 10 else "cold-start",
            "explanation": explain(ahead, counters, bool(matched and matched.get("checked_in")), matched.get("slot", "-" ) if matched else "-")}}

@app.get("/api/smart-arrival/{farmer_id}")
def smart_arrival(farmer_id: str, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, farmer_id)
    bookings = rows("bookings", farmer_id=farmer_id)
    # A confirmed booking is already a valid active booking for the farmer's
    # AI arrival planner. It becomes a live queue item only on its booking date.
    active = [b for b in bookings if b.get("status") in ("waiting", "confirmed", "serving", "procurement_pending")]
    if not active:
        return {"active": False, "message": "No active mandi booking."}
    b = sorted(active, key=lambda x: (x.get("date", "9999"), x.get("slot", "")))[0]
    q = queue_state(b.get("centre_id"), b.get("token"))
    weather = demo_weather(b.get("centre_id"), b.get("date") or datetime.now(BIHAR_TZ).date().isoformat())
    wait = q.get("estimated_wait_min")
    wait_num = int(wait or 0)
    adjusted_wait = wait_num + int(weather["buffer_min"])
    departure = max(0, adjusted_wait - 10)
    confidence = q.get("ai", {}).get("confidence", "medium")
    if weather["buffer_min"] >= 15 and confidence == "high": confidence = "medium"
    if weather["buffer_min"] >= 25: confidence = "cautious"
    return {
        "active": True, "token": b.get("token"), "centre_id": b.get("centre_id"), "date": b.get("date"), "slot": b.get("slot"),
        "queue_wait_min": wait, "weather_buffer_min": weather["buffer_min"], "adjusted_wait_min": adjusted_wait,
        "recommended_departure_in_min": departure, "confidence": confidence, "weather": weather,
        "advice": "Leave after the recommended countdown and aim to reach the centre about 10 minutes before your predicted turn.",
        "model": "queue-ai + weather-aware demo adapter"
    }


@app.get("/api/farmer/risk-signals/{farmer_id}")
def farmer_risk_signals(farmer_id: str, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, farmer_id)
    bs = rows("bookings", farmer_id=farmer_id)
    signals = suspicious_booking_signals(bs)
    return {"risk": signals[0] if signals else {"risk_score": 0, "level": "LOW", "reasons": []}, "safe": not bool(signals)}


@app.get("/api/operator/{centre_id}/risk-signals")
def operator_risk_signals(centre_id: str, authorization: Optional[str] = Header(None)):
    require_any_operator(authorization, centre_id)
    bs = rows("bookings", centre_id=centre_id)
    signals = suspicious_booking_signals(bs)
    return {"centre_id": centre_id, "signals": signals[:12], "count": len(signals), "review_policy": "Flag for human review; no automatic farmer punishment."}


@app.get("/api/operator/{centre_id}/weather-capacity")
def operator_weather_capacity(centre_id: str, booking_date: Optional[str] = None, authorization: Optional[str] = Header(None)):
    require_any_operator(authorization, centre_id)
    centre = find_centre(centre_id)
    date_str = booking_date or datetime.now(BIHAR_TZ).date().isoformat()
    weather = demo_weather(centre_id, date_str)
    base = dynamic_capacity((centre or {}).get("counters", 1))
    multiplier = 0.75 if weather["condition"] == "Heavy Rain" else (0.9 if weather["condition"] == "Rain" else (0.95 if weather["condition"] == "Hot" else 1.0))
    adjusted = max(1, int(base * multiplier))
    return {"centre_id": centre_id, "date": date_str, "weather": weather, "base_capacity": base, "weather_adjusted_capacity": adjusted, "capacity_reduction": max(0, base-adjusted)}


@app.get("/api/ai/centre-insights")
def ai_centre_insights(centre_id: str, authorization: Optional[str] = Header(None)):
    require_any_operator(authorization, centre_id)
    centre = find_centre(centre_id)
    if not centre: raise HTTPException(404, "Centre not found")
    bookings = rows("bookings", centre_id=centre_id)
    counters = max(1, int(centre.get("counters") or 1))
    insights = operational_insights(bookings, counters)
    insights["anomalies"] = anomaly_flags(bookings)
    insights["centre_id"] = centre_id
    waiting=[b for b in bookings if b.get("status")=="waiting"]
    risks=[no_show_prediction(b) for b in waiting]
    insights["no_show_summary"]={"high":sum(x["risk"]=="HIGH" for x in risks),"medium":sum(x["risk"]=="MEDIUM" for x in risks),"low":sum(x["risk"]=="LOW" for x in risks)}
    insights["dynamic_capacity"] = dynamic_capacity(counters)
    insights["service_minutes"] = service_minutes()
    insights["recommended_counters"] = max(1, min(20, math.ceil(max(1,len(waiting))*service_minutes()/120)))
    return insights

@app.get("/api/ai/slot-recommendation")
def ai_slot_recommendation(centre_id: str, booking_date: str, crop: str = "Wheat", quantity_kg: float = 100, authorization: Optional[str] = Header(None)):
    auth = verify_token(authorization)
    if auth.get("role") == "centre" and auth.get("sub") == centre_id:
        pass
    elif auth.get("role") == "admin":
        pass
    elif auth.get("role") == "farmer":
        try:
            farmer = first("farmers", farmer_id=auth.get("sub"))
        except Exception as exc:
            print("[KisanSetu] AI auth lookup failed:", repr(exc))
            raise HTTPException(503, "Supabase temporarily unavailable. Please retry in a few seconds.")
        if not farmer or farmer.get("centre_id") != centre_id:
            raise HTTPException(403, "Farmer access denied.")
    else:
        raise HTTPException(403, "Access denied.")
    centre = find_centre(centre_id)
    if not centre: raise HTTPException(404, "Centre not found")
    try: datetime.strptime(booking_date, "%Y-%m-%d")
    except ValueError: raise HTTPException(400, "Invalid booking date")
    counters=max(1,int(centre.get("counters") or 1))
    try:
        bookings=rows("bookings", centre_id=centre_id, date=booking_date)
        history=rows("bookings", centre_id=centre_id)
    except Exception as exc:
        # AI recommendations must remain usable during a transient Supabase
        # transport outage. The engine supports a deterministic cold-start mode.
        print("[KisanSetu] AI slot recommendation DB read failed; using cold-start model:", exc)
        bookings=[]
        history=[]
    w, training_count=build_model(history, counters)
    results=[]
    selected_date=datetime.fromisoformat(booking_date).date()
    now_local=datetime.now(BIHAR_TZ)
    for slot in SLOTS:
        active=[b for b in bookings if b.get("slot")==slot and b.get("status") not in ("cancelled","completed","skipped")]
        ahead=len(active); capacity=dynamic_capacity(counters, crop, quantity_kg)
        base=max(2, round(ahead*5/counters,1))
        x=features(ahead=ahead,counters=counters,quantity=quantity_kg,slot=slot,checked_in=False)
        ai=predict(w,x) if w else base
        available=max(0,capacity-ahead)
        start=parse_slot_start(slot)
        slot_dt=datetime.combine(selected_date,start,tzinfo=BIHAR_TZ)
        is_past=slot_dt <= now_local if selected_date == now_local.date() else selected_date < now_local.date()
        results.append({"slot":slot,"predicted_wait_min":ai,"available":available,"utilization_percent":round(ahead/capacity*100),
                        "recommended":False,"is_past":is_past,"reason":f"{available} capacity left; {ahead} active booking(s)"})
    candidates=[r for r in results if r["available"]>0 and not r.get("is_past")]
    if candidates:
        best=min(candidates,key=lambda r:(r["predicted_wait_min"],r["utilization_percent"]))
        best["recommended"]=True; best["reason"]="Lowest predicted waiting time with available capacity."
    return {"centre_id":centre_id,"date":booking_date,"crop":crop,"quantity_kg":quantity_kg,
            "model":"ridge-regression","training_samples":training_count,"results":results,
            "message":"AI recommendation uses queue load, active counters, quantity and historical service observations."}


class GrievanceIn(BaseModel):
    farmer_id: str
    centre_id: Optional[str] = None
    token: Optional[str] = None
    category: str
    subject: str
    description: str
    priority: str = "MEDIUM"

class GrievanceUpdate(BaseModel):
    status: str
    resolution: Optional[str] = None
    assigned_to: Optional[str] = None

class FeedbackIn(BaseModel):
    farmer_id: str
    centre_id: str
    token: Optional[str] = None
    waiting_rating: int = Field(ge=1, le=5)
    service_rating: int = Field(ge=1, le=5)
    staff_rating: int = Field(ge=1, le=5)
    overall_rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None

@app.get("/api/public/mandi-status")
def public_mandi_status(centre_id: Optional[str] = None):
    """Read-only public congestion board; no login required."""
    today = datetime.now(BIHAR_TZ).date().isoformat()
    masters = [find_centre(centre_id)] if centre_id else CENTRES
    masters = [c for c in masters if c]
    try:
        all_today = rows("bookings", date=today)
    except Exception:
        all_today = []
    out=[]
    for c in masters:
        bs=[b for b in all_today if b.get("centre_id")==c["centre_id"]]
        active=[b for b in bs if b.get("status") in ("waiting","confirmed","serving","procurement_pending")]
        cap=dynamic_capacity(c.get("counters",1))
        util=round(min(100,len(active)/max(1,cap)*100))
        out.append({"centre_id":c["centre_id"],"district":c["district"],"city":c["city"],"name":c["name"],"active_queue":len(active),"capacity":cap,"utilization_percent":util,"congestion":"HIGH" if util>=80 else ("MEDIUM" if util>=50 else "LOW"),"now_serving":next((b.get("token") for b in active if b.get("status")=="serving"),"--"),"completed_today":sum(b.get("status")=="completed" for b in bs),"recommended": "Consider a later slot" if util>=80 else "Normal load"})
    return {"date":today,"centres":out}

# Farmer scheme directory: official government destinations only.
# myScheme is the Government of India's national scheme discovery platform. It does
# not publish a documented public developer API, so KisanSetu does not scrape it or
# invent a "live" feed. The cards below are verified official entry points; the
# portal itself remains the live source for current eligibility/application details.
FARMER_SCHEMES = [
    {
        "id": "pm-kisan",
        "name": "PM-KISAN",
        "category": "Financial",
        "level": "Central",
        "short_description": "Direct financial support scheme for eligible land-holding farmer families.",
        "benefit": "₹6,000 per year through DBT, subject to scheme eligibility.",
        "url": "https://www.data.gov.in/catalog/pm-kisan-scheme",
        "source": "Open Government Data • Ministry of Agriculture & Farmers Welfare",
    },
    {
        "id": "kcc",
        "name": "Kisan Credit Card",
        "category": "Credit",
        "level": "Central",
        "short_description": "Credit support for cultivation, post-harvest needs and eligible allied agricultural activities.",
        "benefit": "Timely agricultural credit with applicable interest support under the scheme.",
        "url": "https://www.myscheme.gov.in/schemes/kcc",
        "source": "myScheme • Ministry of Agriculture & Farmers Welfare",
    },
    {
        "id": "pmfby",
        "name": "Pradhan Mantri Fasal Bima Yojana",
        "category": "Insurance",
        "level": "Central",
        "short_description": "Crop insurance platform for farmers, including online application, policy status and crop-loss support.",
        "benefit": "Crop-risk insurance and digital claim/status services subject to notified crops, areas and eligibility.",
        "url": "https://www.pmfby.gov.in/",
        "source": "PMFBY • Ministry of Agriculture & Farmers Welfare",
    },
    {
        "id": "pmksy",
        "name": "Pradhan Mantri Krishi Sinchayee Yojana",
        "category": "Irrigation",
        "level": "Central",
        "short_description": "Government irrigation initiative focused on improving access to irrigation and efficient water use.",
        "benefit": "Support for irrigation and water-use efficiency through applicable PMKSY components.",
        "url": "https://pmksy.gov.in/",
        "source": "PMKSY • Government of India",
    },
    {
        "id": "bihar-agri-food-processing",
        "name": "Chief Minister Agriculture and Food Processing Scheme",
        "category": "Agriculture",
        "level": "Bihar",
        "short_description": "Bihar-focused agriculture and food-processing scheme entry maintained on the national government scheme platform.",
        "benefit": "See the official scheme page for the current Bihar-specific benefit and eligibility conditions.",
        "url": "https://www.myscheme.gov.in/schemes/chief-minister-agriculture-and-food-processing-scheme",
        "source": "myScheme • Bihar Government scheme listing",
    },
]

@app.get("/api/schemes")
def farmer_schemes(state: Optional[str] = None, language: Optional[str] = None):
    """Return verified official scheme entry points for the Farmer Schemes page.

    The response intentionally does not claim a live scheme database. Current
    eligibility, application windows and detailed benefits are always opened on
    the linked official government portal. The source portal is separately live
    and is not scraped by KisanSetu.
    """
    requested_state = (state or "Bihar").strip().lower()
    items = []
    for item in FARMER_SCHEMES:
        if item["level"].lower() == "bihar" and requested_state not in ("bihar", ""):
            continue
        items.append(dict(item))
    return {
        "items": items,
        "source": "Government of India myScheme / official department portals",
        "catalog_mode": "verified_official_links",
        "catalog_checked_at": datetime.now(BIHAR_TZ).strftime("%d %b %Y, %I:%M %p"),
        "source_last_updated": "See each linked official portal for the latest scheme information.",
        "live_finder": "https://www.myscheme.gov.in/",
    }

_ADMIN_RATE_CACHE = None
_ADMIN_RATE_CACHE_AT = 0.0
_ADMIN_RATE_CACHE_TTL = 10.0

def _current_admin_rates(crop: Optional[str] = None):
    global _ADMIN_RATE_CACHE, _ADMIN_RATE_CACHE_AT
    now_mono = time.monotonic()
    if _ADMIN_RATE_CACHE is None or now_mono - _ADMIN_RATE_CACHE_AT >= _ADMIN_RATE_CACHE_TTL:
        q = db_required().table("crop_rates").select("rate_id,crop,quality_grade,rate_per_kg,effective_from,active,created_at").eq("active", True).order("effective_from", desc=True)
        data = q.execute().data or []
        latest = {}
        for r in data:
            key = (str(r.get("crop") or "").strip().casefold(), str(r.get("quality_grade") or "FAQ").strip().casefold())
            if key not in latest: latest[key] = r
        _ADMIN_RATE_CACHE = list(latest.values())
        _ADMIN_RATE_CACHE_AT = now_mono
    data = list(_ADMIN_RATE_CACHE or [])
    if crop:
        wanted = crop.strip().casefold()
        data = [r for r in data if str(r.get("crop") or "").strip().casefold() == wanted]
    return data

@app.get("/api/rates")
def crop_rates(crop: Optional[str] = None, district: Optional[str] = None):
    selected = _current_admin_rates(crop.strip() if crop else None)
    items = [{"crop":r.get("crop"),"quality_grade":r.get("quality_grade") or "FAQ","rate_per_kg":round(float(r.get("rate_per_kg") or 0),2),"min_price_per_kg":round(float(r.get("rate_per_kg") or 0),2),"max_price_per_kg":round(float(r.get("rate_per_kg") or 0),2),"market":"KisanSetu Admin Rate","district":"All Bihar","state":"Bihar","effective_from":str(r.get("effective_from") or ""),"arrival_date":str(r.get("effective_from") or ""),"scope":"state","source":"KisanSetu Admin • Central Bihar Rate","source_type":"admin_managed"} for r in selected if float(r.get("rate_per_kg") or 0)>0]
    return {"source":"KisanSetu Admin • Central Bihar Rate","granularity":"admin-managed","unit":"₹/kg","district_requested":district or None,"items":items,"available":bool(items),"note":None if items else "No admin rates configured yet."}

@app.get("/api/rates/history")
def rate_history(crop: Optional[str] = None, authorization: Optional[str] = Header(None)):
    # Public-to-farmer read endpoint: only rate history is exposed, never admin credentials.
    wanted = crop.strip().casefold() if crop else None
    try:
        data = db_required().table("crop_rate_history").select("history_id,crop,quality_grade,rate_per_kg,effective_from,recorded_at").order("recorded_at", desc=False).execute().data or []
    except Exception:
        # Backward-compatible fallback for deployments that have not yet run the
        # history migration: existing crop_rates rows can still be charted.
        data = db_required().table("crop_rates").select("rate_id,crop,quality_grade,rate_per_kg,effective_from,created_at").order("effective_from", desc=False).execute().data or []
    # If history exists but is empty (common immediately after migration), include
    # the current admin rates so the farmer never sees a blank price graph.
    if not data:
        data = db_required().table("crop_rates").select("rate_id,crop,quality_grade,rate_per_kg,effective_from,created_at").order("effective_from", desc=False).execute().data or []
    if wanted:
        data = [r for r in data if str(r.get("crop") or "").strip().casefold() == wanted]
    items = [{
        "id": r.get("history_id") or r.get("rate_id"),
        "crop": r.get("crop"),
        "quality_grade": r.get("quality_grade") or "FAQ",
        "rate_per_kg": round(float(r.get("rate_per_kg") or 0), 2),
        "effective_from": str(r.get("effective_from") or ""),
        "recorded_at": str(r.get("recorded_at") or r.get("created_at") or ""),
    } for r in data if float(r.get("rate_per_kg") or 0) > 0]
    return {"items": items, "unit": "₹/kg", "source": "KisanSetu Admin Rate History", "scope": "All Bihar districts"}

@app.get("/api/admin/rates")
def admin_rates(authorization: Optional[str] = Header(None)):
    verify_token(authorization, "admin")
    return {"items":_current_admin_rates(),"scope":"All Bihar districts","unit":"₹/kg"}

@app.post("/api/admin/rates")
def update_admin_rate(data: AdminRateIn, authorization: Optional[str] = Header(None)):
    verify_token(authorization, "admin")
    crop=data.crop.strip(); grade=data.quality_grade.strip() or "FAQ"
    if crop not in SERVICE_BASE_MIN: raise HTTPException(400, f"Unsupported crop: {crop}")
    payload={"crop":crop,"quality_grade":grade,"rate_per_kg":round(float(data.rate_per_kg),2),"effective_from":datetime.now(BIHAR_TZ).date().isoformat(),"active":True}
    try:
        result=db_required().table("crop_rates").upsert(payload,on_conflict="crop,quality_grade,effective_from").execute().data or []
        # Keep an append-only history row so the farmer dashboard can show the
        # actual previous admin-set values instead of an external market feed.
        try:
            db_required().table("crop_rate_history").insert({
                "crop": crop, "quality_grade": grade, "rate_per_kg": round(float(data.rate_per_kg),2),
                "effective_from": payload["effective_from"]
            }).execute()
        except Exception as history_exc:
            # Current-rate update must remain usable on older databases; the
            # migration can be run later to enable persistent chart history.
            print("[RATES] history write unavailable:", history_exc)

        # Rates are centrally managed; invalidate local rate/forecast caches if present.
        global _ADMIN_RATE_CACHE, _ADMIN_RATE_CACHE_AT
        _ADMIN_RATE_CACHE = None
        _ADMIN_RATE_CACHE_AT = 0.0
        return {"status":"updated","scope":"All Bihar districts","item":result[0] if result else payload}
    except Exception as exc: raise HTTPException(400,f"Could not update procurement rate: {exc}")


@app.post("/api/grievances")
def create_grievance(data: GrievanceIn, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, data.farmer_id)
    if data.centre_id and not find_centre(data.centre_id): raise HTTPException(400,"Invalid centre")
    if data.token:
        b=first("bookings", token=data.token, farmer_id=data.farmer_id)
        if not b: raise HTTPException(400,"Token does not belong to this farmer")
    category=data.category.strip().upper(); priority=data.priority.strip().upper()
    if category not in {"SLOT","QUEUE","WEIGHMENT","QUALITY","PAYMENT","STAFF","MSP_RATE","J_FORM","OTHER"}: raise HTTPException(400,"Invalid grievance category")
    if priority not in {"LOW","MEDIUM","HIGH","URGENT"}: priority="MEDIUM"
    payload={"grievance_id":str(uuid.uuid4()),"farmer_id":data.farmer_id,"centre_id":data.centre_id,"token":data.token,"category":category,"subject":data.subject.strip()[:160],"description":data.description.strip()[:2000],"priority":priority,"status":"OPEN"}
    result=db_required().table("grievances").insert(payload).execute().data
    audit("GRIEVANCE_CREATED",centre_id=data.centre_id,farmer_id=data.farmer_id,token=data.token,details={"category":category,"priority":priority})
    return result[0]

@app.get("/api/grievances/{farmer_id}")
def farmer_grievances(farmer_id: str, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, farmer_id)
    return db_required().table("grievances").select("*").eq("farmer_id",farmer_id).order("created_at",desc=True).limit(50).execute().data or []

@app.get("/api/operator/{centre_id}/grievances")
def operator_grievances(centre_id: str, authorization: Optional[str] = Header(None)):
    require_centre(authorization, centre_id)
    return db_required().table("grievances").select("*").eq("centre_id",centre_id).order("created_at",desc=True).limit(100).execute().data or []

@app.patch("/api/operator/{centre_id}/grievances/{grievance_id}")
def update_grievance(centre_id: str, grievance_id: str, data: GrievanceUpdate, authorization: Optional[str] = Header(None)):
    require_centre(authorization, centre_id)
    g=first("grievances", grievance_id=grievance_id)
    if not g or g.get("centre_id")!=centre_id: raise HTTPException(404,"Grievance not found")
    status=data.status.strip().upper()
    if status not in {"OPEN","IN_PROGRESS","RESOLVED","ESCALATED"}: raise HTTPException(400,"Invalid grievance status")
    update={"status":status,"resolution":data.resolution,"assigned_to":data.assigned_to,"updated_at":datetime.now(BIHAR_TZ).isoformat()}
    if status=="RESOLVED": update["resolved_at"]=datetime.now(BIHAR_TZ).isoformat()
    db_required().table("grievances").update(update).eq("grievance_id",grievance_id).execute()
    audit("GRIEVANCE_UPDATED",centre_id=centre_id,farmer_id=g.get("farmer_id"),token=g.get("token"),details={"status":status})
    notify(g["farmer_id"],"Grievance Update",f"Your grievance '{g.get('subject','')}' is now {status.replace('_',' ').title()}.")
    return first("grievances", grievance_id=grievance_id)

@app.post("/api/feedback")
def create_feedback(data: FeedbackIn, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, data.farmer_id)
    if not find_centre(data.centre_id): raise HTTPException(400,"Invalid centre")
    if data.token:
        b=first("bookings", token=data.token, farmer_id=data.farmer_id)
        if not b: raise HTTPException(400,"Token does not belong to this farmer")
    existing=first("feedback",farmer_id=data.farmer_id,token=data.token) if data.token else None
    if existing: return existing
    payload=data.model_dump(); payload["feedback_id"]=str(uuid.uuid4()); payload["comment"]=(data.comment or "").strip()[:1000]
    result=db_required().table("feedback").insert(payload).execute().data
    audit("FARMER_FEEDBACK",centre_id=data.centre_id,farmer_id=data.farmer_id,token=data.token,details={"overall":data.overall_rating})
    return result[0]

@app.get("/api/admin/impact")
def admin_impact(authorization: Optional[str] = Header(None)):
    verify_token(authorization,"admin")
    grievances=rows("grievances")
    feedback=rows("feedback")
    active=[g for g in grievances if g.get("status") not in ("RESOLVED",)]
    resolved=[g for g in grievances if g.get("status")=="RESOLVED"]
    avg_rating=round(sum(float(f.get("overall_rating") or 0) for f in feedback)/max(1,len(feedback)),2) if feedback else 0
    by_cat={}
    for g in grievances: by_cat[g.get("category","OTHER")]=by_cat.get(g.get("category","OTHER"),0)+1
    centre_scores={}
    for f in feedback:
        centre_scores.setdefault(f.get("centre_id"),[]).append(float(f.get("overall_rating") or 0))
    centre_ratings=[{"centre_id":k,"rating":round(sum(v)/len(v),2),"responses":len(v)} for k,v in centre_scores.items()]
    centre_ratings.sort(key=lambda x:x["rating"])
    return {"grievances":{"total":len(grievances),"open":len([g for g in grievances if g.get("status")=="OPEN"]),"in_progress":len([g for g in grievances if g.get("status")=="IN_PROGRESS"]),"escalated":len([g for g in grievances if g.get("status")=="ESCALATED"]),"resolved":len(resolved),"categories":by_cat},"feedback":{"responses":len(feedback),"average_rating":avg_rating,"centre_ratings":centre_ratings}}

@app.on_event("startup")
def startup():
    if not SUPABASE_ENABLED:
        print("[KisanSetu] Supabase is NOT configured. Set backend/.env before using the app.")
        return
    try:
        db_required().table("centres").upsert(CENTRES, on_conflict="centre_id", ignore_duplicates=True).execute()
        print("[KisanSetu] Supabase connected and centres synced")
        threading.Thread(target=auto_skip_worker, daemon=True, name="auto-skip-worker").start()
        threading.Thread(target=email_reminder_worker, daemon=True, name="email-reminder-worker").start()
    except Exception as exc:
        print("[KisanSetu] Supabase startup error:", exc)

@app.get("/")
def root(): return {"app":"KisanSetu", "version":"9.0.0", "status":"running", "database":"supabase" if SUPABASE_ENABLED else "not-configured"}

@app.get("/api/health")
def health():
    if SUPABASE_ENABLED:
        try:
            execute_select("centres")
            return {"status":"ok", "database":"supabase", "centres":len(CENTRES)}
        except Exception as exc: raise HTTPException(503, f"Supabase connection failed: {exc}")
    raise HTTPException(503, "Supabase not configured")

@app.get("/api/centres")
def centres():
    try:
        data = rows("centres")
        return data or CENTRES
    except Exception:
        # Public discovery should still work when Supabase is temporarily down.
        return CENTRES

@app.get("/api/centres/nearest")
def nearest_centres(lat: float, lon: float, limit: int = 5):
    data = centres(); result = [{**c, "distance_km": round(haversine(lat, lon, c["lat"], c["lon"]), 3)} for c in data]
    return sorted(result, key=lambda x: x["distance_km"])[:max(1, min(limit, 38))]

def require_farmer(authorization: Optional[str], farmer_id: str):
    payload = verify_token(authorization, "farmer")
    if payload.get("sub") != farmer_id:
        raise HTTPException(403, "Farmer access denied.")
    return payload

def require_centre(authorization: Optional[str], centre_id: str):
    payload = verify_token(authorization, "centre")
    if payload.get("sub") != centre_id:
        raise HTTPException(403, "Centre access denied.")
    return payload

def require_any_operator(authorization: Optional[str], centre_id: str):
    payload = verify_token(authorization)
    if payload.get("role") == "centre" and payload.get("sub") == centre_id:
        return payload
    if payload.get("role") == "admin":
        return payload
    raise HTTPException(403, "Access denied.")

@app.post("/api/farmers")
def register_farmer(data: FarmerIn):
    mobile = data.mobile.strip()
    district = data.district.strip()
    name = data.name.strip()
    village = data.village.strip()
    if not name or not village:
        raise HTTPException(400, "Name and village are required.")
    centre_id = DISTRICT_TO_CENTRE.get(district)
    if not centre_id: raise HTTPException(400, "Please select a valid Bihar district.")
    existing = first("farmers", mobile=mobile)
    if existing: return existing
    # Keep the familiar F + last-6 format when free; otherwise append a safe suffix.
    base_id = "F" + mobile[-6:]
    farmer_id = base_id
    if first("farmers", farmer_id=farmer_id):
        farmer_id = f"{base_id}{secrets.token_hex(2).upper()}"
    payload = {**data.model_dump(), "mobile": mobile, "district": district, "name": name, "village": village, "farmer_id": farmer_id, "centre_id": centre_id}
    try:
        result = db_required().table("farmers").insert(payload).execute().data
    except Exception as exc: raise HTTPException(400, f"Farmer registration failed: {exc}")
    farmer = result[0]
    notify(farmer_id, "Welcome to KisanSetu", "Aapka farmer account successfully create ho gaya.")
    if farmer.get("email"):
        try:
            send_registration_email(
                farmer["email"],
                farmer.get("name", data.name),
                farmer_id,
                farmer.get("mobile", data.mobile),
            )
        except Exception as exc:
            print("[EMAIL] registration mail error:", exc)
    return farmer

@app.post("/api/centres/register")
def register_centre(data: CentreIn):
    db = db_required()
    district = data.district.strip()
    centre_id = DISTRICT_TO_CENTRE.get(district)
    if not centre_id:
        raise HTTPException(400, "Please select a valid Bihar district.")
    existing = first("centres", centre_id=centre_id)
    if existing and existing.get("registration_status", "approved") == "approved" and existing.get("employee_id"):
        raise HTTPException(409, f"A procurement centre operator is already approved for {district}. Centre Code: {centre_id}")
    # Registration is an application, never an overwrite of the live centre master.
    try:
        pending = db.table("centre_registration_requests").select("*").eq("centre_id", centre_id).eq("status", "pending").limit(1).execute().data or []
        if pending:
            raise HTTPException(409, f"A registration request for {district} is already pending admin validation.")
        request_id = str(uuid.uuid4())
        payload = {
            "request_id": request_id, "centre_id": centre_id, "district": district,
            "name": data.name.strip() or f"{district} Procurement Centre",
            "mobile": data.mobile.strip(), "address": data.address.strip(),
            "counters": int(data.counters), "status": "pending"
        }
        result = db.table("centre_registration_requests").insert(payload).execute().data
        return {**(result[0] if result else payload), "message": "Registration submitted for admin validation."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Centre registration failed: {exc}")

@app.patch("/api/farmers/{farmer_id}")
def update_farmer(farmer_id: str, data: dict, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, farmer_id)
    farmer = first("farmers", farmer_id=farmer_id)
    if not farmer:
        raise HTTPException(404, "Farmer not found")
    allowed = {"name", "email", "village", "district", "crop"}
    payload = {k: v for k, v in data.items() if k in allowed and v is not None}
    if "name" in payload and not str(payload["name"]).strip():
        raise HTTPException(400, "Name is required")
    if "village" in payload and not str(payload["village"]).strip():
        raise HTTPException(400, "Village is required")
    if "district" in payload and not str(payload["district"]).strip():
        raise HTTPException(400, "District is required")
    if "crop" in payload and payload["crop"] not in ("Wheat", "Rice", "Maize", "Mustard"):
        raise HTTPException(400, "Invalid crop")
    if "district" in payload:
        mapped = DISTRICT_TO_CENTRE.get(str(payload["district"]).strip())
        if not mapped:
            raise HTTPException(400, "Invalid Bihar district")
        if mapped != farmer.get("centre_id"):
            active = rows("bookings", farmer_id=farmer_id)
            if any(b.get("status") in ("waiting", "confirmed", "serving", "procurement_pending") for b in active):
                raise HTTPException(409, "District cannot be changed while you have an active booking. Complete or cancel the booking first.")
        payload["centre_id"] = mapped
    try:
        result = db_required().table("farmers").update(payload).eq("farmer_id", farmer_id).execute().data
    except Exception as exc:
        raise HTTPException(400, f"Farmer profile update failed: {exc}")
    return (result or [first("farmers", farmer_id=farmer_id)])[0]

@app.patch("/api/centres/{centre_id}")
def update_centre(centre_id: str, data: dict, authorization: Optional[str] = Header(None)):
    require_centre(authorization, centre_id)
    centre = first("centres", centre_id=centre_id)
    if not centre:
        raise HTTPException(404, "Procurement centre not found")
    allowed = {"name", "address", "counters"}
    payload = {k: v for k, v in data.items() if k in allowed and v is not None}
    if "name" in payload and not str(payload["name"]).strip():
        raise HTTPException(400, "Centre name is required")
    if "district" in payload and not str(payload["district"]).strip():
        raise HTTPException(400, "District is required")
    if "address" in payload and not str(payload["address"]).strip():
        raise HTTPException(400, "Address is required")
    if "counters" in payload:
        try:
            counters = int(payload["counters"])
        except Exception:
            raise HTTPException(400, "Counters must be a number")
        if counters < 1 or counters > 20:
            raise HTTPException(400, "Counters must be between 1 and 20")
        payload["counters"] = counters
    try:
        result = db_required().table("centres").update(payload).eq("centre_id", centre_id).execute().data
    except Exception as exc:
        raise HTTPException(400, f"Centre profile update failed: {exc}")
    return (result or [first("centres", centre_id=centre_id)])[0]

@app.post("/api/auth/login")
def login(data: LoginIn):
    if data.role == "admin":
        expected_user = os.getenv("ADMIN_USERNAME", "admin").strip()
        expected_pass = os.getenv("ADMIN_PASSWORD", "admin123").strip()
        supplied_user = (data.username or "").strip()
        supplied_pass = data.password or ""
        if not supplied_user or not supplied_pass or not secrets.compare_digest(supplied_user, expected_user) or not secrets.compare_digest(supplied_pass, expected_pass):
            raise HTTPException(401, "Invalid admin username or password.")
        return {"user": {"username": supplied_user, "name": "KisanSetu Administrator", "role": "admin"}, "access_token": issue_token("admin", supplied_user)}

    if data.role == "farmer":
        if not data.farmer_id:
            raise HTTPException(400, "Farmer ID is required.")
        user = first("farmers", farmer_id=data.farmer_id)
        if not user:
            raise HTTPException(401, "Invalid Farmer ID.")
        if user.get("mobile") != (data.mobile or "").strip():
            raise HTTPException(401, "Farmer ID and mobile number do not match.")
        return {"user": user, "access_token": issue_token("farmer", user["farmer_id"])}

    if data.role == "centre":
        if not data.employee_id:
            raise HTTPException(400, "Employee ID is required.")
        user = first("centres", employee_id=data.employee_id)
        if not user:
            raise HTTPException(401, "Invalid Employee ID.")
        if user.get("registration_status") == "pending":
            raise HTTPException(403, "Centre registration is pending admin approval.")
        if user.get("registration_status") == "rejected":
            raise HTTPException(403, "Centre registration was rejected by admin.")
        if user.get("mobile") != (data.mobile or "").strip():
            raise HTTPException(401, "Employee ID and mobile number do not match.")
        return {"user": user, "access_token": issue_token("centre", user["centre_id"])}

    raise HTTPException(400, "Invalid role.")

@app.get("/api/admin/dashboard")
def admin_dashboard(authorization: Optional[str] = Header(None)):
    verify_token(authorization, "admin")
    centres = rows("centres"); bookings = rows("bookings"); procurements = rows("procurements")
    centre_map = {c.get("centre_id"): c for c in centres}; today = datetime.now(BIHAR_TZ).date()
    daily=[]
    for i in range(6,-1,-1):
        ds=(today-timedelta(days=i)).isoformat()
        daily.append({"date":ds,"completed":sum(1 for p in procurements if (p.get("completed_at") or p.get("created_at", ""))[:10]==ds)})
    district_map={c["district"]:{"district":c["district"],"centre_id":c["centre_id"],"centres":1,"completed":0,"active":0,"avg_wait_min":0} for c in centres}
    for p in procurements:
        dist=centre_map.get(p.get("centre_id"),{}).get("district","Unknown"); district_map.setdefault(dist,{"district":dist,"centre_id":"","centres":0,"completed":0,"active":0,"avg_wait_min":0})["completed"]+=1
    for b in bookings:
        if b.get("status") in ("waiting","confirmed","serving","procurement_pending"):
            dist=centre_map.get(b.get("centre_id"),{}).get("district","Unknown"); district_map.setdefault(dist,{"district":dist,"centre_id":"","centres":0,"completed":0,"active":0,"avg_wait_min":0})["active"]+=1
    pending = db_required().table("centre_registration_requests").select("*").eq("status","pending").order("created_at", desc=True).execute().data or []
    return {"summary":{"districts":len(district_map),"approved_centres":sum(1 for c in centres if c.get("registration_status","approved")=="approved"),"pending_registrations":len(pending),"total_completed":len(procurements),"active_queue":sum(1 for b in bookings if b.get("status") in ("waiting","confirmed","serving","procurement_pending"))},"districts":sorted(district_map.values(),key=lambda x:x["completed"],reverse=True),"daily":daily,"pending_registrations":pending}

@app.post("/api/admin/centre-requests/{request_id}/approve")
def approve_centre_request(request_id: str, authorization: Optional[str] = Header(None)):
    verify_token(authorization, "admin")
    req=first("centre_registration_requests", request_id=request_id)
    if not req: raise HTTPException(404,"Registration request not found.")
    if req.get("status")!="pending": raise HTTPException(400,"Request is already processed.")
    centre=first("centres", centre_id=req["centre_id"])
    if centre and centre.get("employee_id"): raise HTTPException(409,"This district already has an approved operator.")
    existing_ids={str(c.get("employee_id")) for c in rows("centres") if c.get("employee_id")}
    n=1001
    while f"EMP-{n}" in existing_ids: n+=1
    employee_id=f"EMP-{n}"
    master = next((c for c in CENTRES if c["centre_id"]==req["centre_id"]), {})
    centre_payload={"centre_id":req["centre_id"],"employee_id":employee_id,"name":req.get("name") or master.get("name"),"district":req["district"],"city":master.get("city",req["district"]),"address":req.get("address") or master.get("address",req["district"]),"lat":master.get("lat",25.2),"lon":master.get("lon",85.1),"counters":int(req.get("counters") or master.get("counters",2)),"mobile":req.get("mobile"),"registration_status":"approved"}
    try:
        if centre: result=db_required().table("centres").update(centre_payload).eq("centre_id",req["centre_id"]).execute().data
        else: result=db_required().table("centres").insert(centre_payload).execute().data
        db_required().table("centre_registration_requests").update({"status":"approved","reviewed_at":datetime.now(BIHAR_TZ).isoformat(),"employee_id":employee_id}).eq("request_id",request_id).execute()
        return {"status":"approved","centre_id":req["centre_id"],"employee_id":employee_id,"centre":(result or [centre_payload])[0]}
    except Exception as exc: raise HTTPException(400,f"Approval failed: {exc}")

@app.post("/api/admin/centre-requests/{request_id}/reject")
def reject_centre_request(request_id: str, authorization: Optional[str] = Header(None)):
    verify_token(authorization, "admin")
    req=first("centre_registration_requests", request_id=request_id)
    if not req: raise HTTPException(404,"Registration request not found.")
    if req.get("status")!="pending": raise HTTPException(400,"Request is already processed.")
    result=db_required().table("centre_registration_requests").update({"status":"rejected","reviewed_at":datetime.now(BIHAR_TZ).isoformat()}).eq("request_id",request_id).execute().data
    return {"status":"rejected","request_id":request_id,"request":(result or [req])[0]}

@app.get("/api/slots")
def slots(centre_id: str, booking_date: str, crop: str = "Wheat", quantity_kg: float = 100):
    centre = find_centre(centre_id)
    if not centre: raise HTTPException(404, "Centre not found")
    try:
        selected = datetime.strptime(booking_date, "%Y-%m-%d").date()
    except ValueError: raise HTTPException(400, "Invalid booking date")
    today = datetime.now(BIHAR_TZ).date()
    booked = rows("bookings", centre_id=centre_id, date=booking_date)
    capacity = dynamic_capacity(centre["counters"], crop, quantity_kg)
    out=[]
    for slot in SLOTS:
        count = sum(1 for b in booked if b["slot"] == slot and b["status"] not in ("cancelled", "completed"))
        is_past = selected < today or (selected == today and datetime.strptime(slot.split("-")[0].strip(), "%H:%M").time() <= datetime.now(BIHAR_TZ).time())
        out.append({"slot":slot, "booked":count, "capacity":capacity, "available":max(0, capacity-count), "is_past":is_past,
                    "is_full":count>=capacity, "available_for_booking":(not is_past and count<capacity),
                    "capacity_method":"dynamic", "service_minutes":service_minutes(crop,quantity_kg), "crop":crop, "quantity_kg":quantity_kg})
    return out

@app.post("/api/bookings")
def create_booking(data: BookingIn, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, data.farmer_id)
    farmer = first("farmers", farmer_id=data.farmer_id)
    if not farmer: raise HTTPException(404, "Farmer not found")
    if farmer.get("centre_id") != data.centre_id:
        raise HTTPException(400, "Selected centre does not match your district-assigned procurement centre.")
    centre = find_centre(data.centre_id)
    if not centre: raise HTTPException(404, "Centre not found")
    if data.quantity_kg <= 0: raise HTTPException(400, "Quantity must be greater than 0")
    validate_booking_time(data.date, data.slot)
    capacity = dynamic_capacity(centre["counters"], data.crop, data.quantity_kg)
    # Booking reservation is performed atomically in PostgreSQL so two concurrent
    # requests cannot both consume the last slot or create multiple active bookings.
    try:
        result = db_required().rpc("create_booking_atomic", {
            "p_booking_id": str(uuid.uuid4()),
            "p_farmer_id": data.farmer_id,
            "p_centre_id": data.centre_id,
            "p_crop": data.crop,
            "p_quantity_kg": data.quantity_kg,
            "p_date": data.date,
            "p_slot": data.slot,
            "p_capacity": int(capacity),
        }).execute().data
        booking = result[0] if isinstance(result, list) else result
        if not booking: raise HTTPException(409, "Selected slot could not be reserved. Please try again.")
        token = booking.get("token")
    except HTTPException: raise
    except Exception as exc:
        msg = str(exc)
        if "ACTIVE_BOOKING_EXISTS" in msg:
            raise HTTPException(409, "You already have an active booking. Complete or cancel it before booking another slot.")
        if "SLOT_FULL" in msg:
            raise HTTPException(409, "Selected slot is full. Please choose another slot.")

        # Do not fall back to a non-atomic check-then-insert.
        # A schema-cache/RPC error must be fixed in Supabase; otherwise concurrent
        # farmers can reserve the same last slot.
        if "PGRST202" in msg or ("create_booking_atomic" in msg and "schema cache" in msg):
            raise HTTPException(503, "Booking RPC is unavailable. Run backend/BOOKING_RPC_SCHEMA_FIX.sql in Supabase SQL Editor and reload the schema cache.")
        else:
            raise HTTPException(400, f"Booking failed: {msg}")
    # Booking is already committed at this point. Audit/notification/email are
    # secondary side-effects and must NEVER turn a successful booking into a
    # 500 response (otherwise the farmer sees a crash and may retry into an
    # ACTIVE_BOOKING_EXISTS state).
    try:
        audit("BOOKING_CREATED", centre_id=data.centre_id, farmer_id=data.farmer_id, token=token, details={"date":data.date,"slot":data.slot,"crop":data.crop,"quantity_kg":data.quantity_kg})
    except Exception as exc:
        print("[AUDIT] booking audit failed:", exc)
    try:
        notify(data.farmer_id, "Slot Confirmed", f"Token {token} confirmed for {data.date}, {data.slot}.")
    except Exception as exc:
        print("[NOTIFY] booking notification failed:", exc)
    farmer = first("farmers", farmer_id=data.farmer_id) or {}
    if farmer.get("email"):
        centre_name = (centre.get("name") or f"{centre.get('district', '')} Procurement Centre").strip()
        try:
            send_token_booking_email(
                farmer["email"],
                farmer.get("name", "Kisan"),
                str(token),
                data.date,
                data.slot,
                centre_name,
            )
        except Exception as exc:
            print("[EMAIL] booking mail error:", exc)
    return booking

@app.get("/api/bookings/{token}/token-pdf")
def token_pdf(token: str, authorization: Optional[str] = Header(None)):
    auth, b = resolve_token_booking(token, authorization)
    if auth.get("role") == "farmer" and auth.get("sub") != b.get("farmer_id"):
        raise HTTPException(403, "Farmer access denied.")
    if auth.get("role") == "centre" and auth.get("sub") != b.get("centre_id"):
        raise HTTPException(403, "Centre access denied.")
    if auth.get("role") not in ("farmer", "centre", "admin"):
        raise HTTPException(403, "Access denied.")

    farmer = first("farmers", farmer_id=b.get("farmer_id")) or {}
    centre = find_centre(b.get("centre_id")) or {}
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    left, right = 18*mm, w-18*mm
    pdf.setTitle(f"KisanSetu Token {token}")

    # Clean receipt-style layout: white card, thin border, compact two-column details.
    pdf.setFillColorRGB(0.98, 0.99, 0.98)
    pdf.roundRect(left, 78*mm, right-left, h-96*mm, 5*mm, fill=1, stroke=0)
    pdf.setStrokeColorRGB(0.72, 0.78, 0.75)
    pdf.roundRect(left, 78*mm, right-left, h-96*mm, 5*mm, fill=0, stroke=1)

    top = h-24*mm
    pdf.setFillColorRGB(0.05, 0.35, 0.20)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(28*mm, top, "KISANSETU")
    pdf.setFillColorRGB(0.05, 0.10, 0.08)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(28*mm, top-8*mm, "PROCUREMENT TOKEN")
    pdf.setFillColorRGB(0.35, 0.40, 0.38)
    pdf.setFont("Helvetica", 7.5)
    pdf.drawString(28*mm, top-14*mm, "Smart Procurement • Government Mandi Workflow")
    # Status/check mark
    pdf.setStrokeColorRGB(0.10, 0.45, 0.28)
    pdf.circle(right-17*mm, top-5*mm, 4*mm, fill=0, stroke=1)
    pdf.setFillColorRGB(0.10, 0.45, 0.28)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(right-17*mm, top-7*mm, "✓")

    line_y = top-19*mm
    pdf.setStrokeColorRGB(0.20, 0.25, 0.23)
    pdf.line(28*mm, line_y, right-10*mm, line_y)

    # Token highlight.
    box_top, box_bottom = line_y-7*mm, line_y-34*mm
    pdf.setFillColorRGB(0.94, 0.98, 0.95)
    pdf.setStrokeColorRGB(0.80, 0.88, 0.83)
    pdf.roundRect(28*mm, box_bottom, 76*mm, box_top-box_bottom, 3*mm, fill=1, stroke=1)
    pdf.setFillColorRGB(0.35, 0.40, 0.38)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawString(33*mm, box_top-8*mm, "YOUR TOKEN")
    pdf.setFillColorRGB(0.04, 0.12, 0.08)
    pdf.setFont("Helvetica-Bold", 27)
    pdf.drawString(33*mm, box_top-21*mm, str(token))

    signed_qr = sign_sih_qr({
        "v": 1, "booking_id": str(b.get("booking_id")), "token": str(token),
        "farmer_id": str(b.get("farmer_id", "")), "mandi_id": str(b.get("centre_id", "")),
        "slot": str(b.get("slot", "")), "booking_date": str(b.get("date", "")),
        "exp": int(time.time()) + 60 * 60 * 24 * 3,
    })
    qr_box = 35*mm
    qr_x, qr_y = right-44*mm, box_bottom-3*mm
    pdf.setFillColorRGB(1,1,1)
    pdf.setStrokeColorRGB(0.80,0.84,0.82)
    pdf.roundRect(qr_x, qr_y, qr_box, qr_box, 2*mm, fill=1, stroke=1)
    qr = QrCodeWidget(signed_qr, barWidth=29*mm, barHeight=29*mm, barBorder=4)
    d = Drawing(29*mm, 29*mm); d.add(qr); d.drawOn(pdf, qr_x+3*mm, qr_y+4*mm)
    pdf.setFillColorRGB(0.30, 0.35, 0.33)
    pdf.setFont("Helvetica-Bold", 6.8)
    pdf.drawCentredString(qr_x+qr_box/2, qr_y-4*mm, "SCAN TO VERIFY")

    # Two-column booking details.
    rows = [
        ("Farmer Name", farmer.get("name","—"), "Farmer ID", farmer.get("farmer_id","—")),
        ("Centre", centre.get("name", b.get("centre_id","—")), "Centre ID", b.get("centre_id","—")),
        ("District", centre.get("district","—"), "Date", b.get("date","—")),
        ("Booking Slot", b.get("slot","—"), "Crop", b.get("crop","—")),
        ("Quantity", f'{b.get("quantity_kg","—")} kg', "Status", str(b.get("status","Confirmed")).title()),
    ]
    y = line_y-46*mm
    for l1,v1,l2,v2 in rows:
        pdf.setFillColorRGB(0.40,0.44,0.42); pdf.setFont("Helvetica",7.5)
        pdf.drawString(30*mm, y, l1)
        pdf.drawString(110*mm, y, l2)
        pdf.setFillColorRGB(0.06,0.12,0.09); pdf.setFont("Helvetica-Bold",8)
        pdf.drawString(48*mm, y, str(v1)[:34])
        pdf.drawString(130*mm, y, str(v2)[:28])
        y -= 9*mm

    # Instruction footer inside the card.
    foot_y = 91*mm
    pdf.setFillColorRGB(0.93, 0.97, 0.94)
    pdf.roundRect(28*mm, foot_y, right-28*mm, 20*mm, 3*mm, fill=1, stroke=0)
    pdf.setFillColorRGB(0.05, 0.35, 0.20)
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.drawString(33*mm, foot_y+13*mm, "GATE INSTRUCTION")
    pdf.setFillColorRGB(0.15, 0.20, 0.18)
    pdf.setFont("Helvetica", 7)
    pdf.drawString(33*mm, foot_y+7*mm, "Carry this token with your Farmer ID and show it at the procurement centre gate.")
    pdf.drawString(33*mm, foot_y+3*mm, "Arrive near your booked slot for quick verification.")

    pdf.setFillColorRGB(0.45,0.45,0.45)
    pdf.setFont("Helvetica",6.5)
    pdf.drawString(18*mm, 18*mm, "KisanSetu • Digitally generated procurement document")
    pdf.drawRightString(w-18*mm, 18*mm, "1/1")
    pdf.showPage()
    pdf.save(); buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
        headers={"Content-Disposition":f'attachment; filename="KisanSetu_Token_{token}.pdf"'})

@app.get("/api/bookings/{farmer_id}")
def farmer_bookings(farmer_id: str, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, farmer_id)
    return db_required().table("bookings").select("*").eq("farmer_id", farmer_id).order("created_at", desc=False).execute().data or []

@app.get("/api/bookings/{token}/gate-pass")
def gate_pass(token: str, authorization: Optional[str] = Header(None)):
    auth, b = resolve_token_booking(token, authorization)
    if auth.get("role") == "farmer" and auth.get("sub") != b.get("farmer_id"):
        raise HTTPException(403, "Farmer access denied.")
    if auth.get("role") == "centre" and auth.get("sub") != b.get("centre_id"):
        raise HTTPException(403, "Centre access denied.")
    if auth.get("role") not in ("farmer", "centre", "admin"):
        raise HTTPException(403, "Access denied.")

    farmer = first("farmers", farmer_id=b.get("farmer_id")) or {}
    centre = find_centre(b.get("centre_id")) or {}
    buf = BytesIO(); pdf = canvas.Canvas(buf, pagesize=A4); w, h = A4
    left, right = 18*mm, w-18*mm
    pdf.setTitle(f"KisanSetu Gate Pass {token}")

    pdf.setFillColorRGB(0.04,0.35,0.20)
    pdf.roundRect(left, h-55*mm, right-left, 37*mm, 6*mm, fill=1, stroke=0)
    pdf.setFillColorRGB(1,1,1); pdf.setFont("Helvetica-Bold",24)
    pdf.drawString(28*mm,h-33*mm,"KisanSetu")
    pdf.setFont("Helvetica-Bold",13); pdf.drawString(28*mm,h-43*mm,"MANDI GATE PASS")
    pdf.setFont("Helvetica",9); pdf.drawRightString(right-10*mm,h-33*mm,"Valid for booked mandi visit")

    # QR and token are side-by-side inside a dedicated card.
    card_top, card_bottom = h-65*mm, h-133*mm
    pdf.setFillColorRGB(0.97,0.99,0.98); pdf.setStrokeColorRGB(0.84,0.91,0.87)
    pdf.roundRect(left,card_bottom,right-left,card_top-card_bottom,5*mm,fill=1,stroke=1)
    pdf.setFillColorRGB(0.35,0.40,0.38); pdf.setFont("Helvetica-Bold",9)
    pdf.drawString(28*mm,card_top-10*mm,"GATE TOKEN")
    pdf.setFillColorRGB(0.05,0.12,0.08); pdf.setFont("Helvetica-Bold",32)
    pdf.drawString(28*mm,card_top-28*mm,str(b.get("token","—")))
    pdf.setFillColorRGB(0.35,0.40,0.38); pdf.setFont("Helvetica",9)
    pdf.drawString(28*mm,card_top-37*mm,"Keep this pass ready for gate verification.")
    signed_qr = sign_sih_qr({"v":1,"booking_id":str(b.get("booking_id")),"token":str(b.get("token","")),"farmer_id":str(b.get("farmer_id","")),"mandi_id":str(b.get("centre_id","")),"slot":str(b.get("slot","")),"booking_date":str(b.get("date","")),"exp":int(time.time())+60*60*24*3})
    qr_box = 38*mm; qr_x = right-44*mm; qr_y = card_bottom+10*mm
    pdf.setFillColorRGB(1,1,1); pdf.roundRect(qr_x,qr_y,qr_box,qr_box,3*mm,fill=1,stroke=0)
    qr = QrCodeWidget(signed_qr, barWidth=32*mm, barHeight=32*mm, barBorder=4)
    d=Drawing(32*mm,32*mm); d.add(qr); d.drawOn(pdf,qr_x+3*mm,qr_y+4*mm)
    pdf.setFillColorRGB(0.35,0.40,0.38); pdf.setFont("Helvetica-Bold",7.5)
    pdf.drawCentredString(qr_x+qr_box/2,card_bottom+5*mm,"SCAN TO VERIFY")

    rows_pdf=[
        ("Farmer ID",farmer.get("farmer_id","—")),
        ("Farmer Name",farmer.get("name","—")),
        ("Centre",f'{centre.get("name",b.get("centre_id","—"))} ({b.get("centre_id","—")})'),
        ("District",centre.get("district","—")),
        ("Date",b.get("date","—")),("Slot",b.get("slot","—")),
        ("Crop",b.get("crop","—")),("Quantity",f'{b.get("quantity_kg","—")} kg'),
    ]
    y=h-146*mm
    for label,value in rows_pdf:
        pdf.setFillColorRGB(0.35,0.40,0.38); pdf.setFont("Helvetica",9); pdf.drawString(30*mm,y,label)
        pdf.setFillColorRGB(0.05,0.12,0.08); pdf.setFont("Helvetica-Bold",9); pdf.drawRightString(right-10*mm,y,str(value)[:80]); y-=8*mm

    box_y=28*mm
    pdf.setFillColorRGB(0.92,0.97,0.94); pdf.roundRect(25*mm,box_y,w-50*mm,25*mm,4*mm,fill=1,stroke=0)
    pdf.setFillColorRGB(0.05,0.35,0.20); pdf.setFont("Helvetica-Bold",10); pdf.drawString(32*mm,box_y+16*mm,"GATE INSTRUCTION")
    pdf.setFillColorRGB(0.10,0.16,0.13); pdf.setFont("Helvetica",8.5)
    pdf.drawString(32*mm,box_y+9*mm,"Show this pass with your Farmer ID at the procurement centre gate.")
    pdf.drawString(32*mm,box_y+4*mm,"Arrive near your booked slot; staff will verify the token before entry.")
    pdf.setFillColorRGB(0.45,0.45,0.45); pdf.setFont("Helvetica",7.5)
    pdf.drawCentredString(w/2,16*mm,"Digitally generated by KisanSetu • Gate verification pass")
    pdf.showPage(); pdf.save(); buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition":f'inline; filename="KisanSetu_GatePass_{token}.pdf"'})

@app.get("/api/qr/verify")
def verify_qr(token: str, centre_id: str, authorization: Optional[str] = Header(None)):
    auth = verify_token(authorization, "centre")
    if auth.get("sub") != centre_id:
        raise HTTPException(403, "Centre access denied.")
    raw_token = token.strip()
    signed_payload = None
    if raw_token.startswith("KSQR1."):
        try:
            signed_payload = verify_sih_qr(raw_token)
            if signed_payload.get("mandi_id") != centre_id:
                return {"valid": False, "message": "Signed QR belongs to another procurement centre."}
            token = str(signed_payload.get("token") or "")
            if not token:
                return {"valid": False, "message": "Signed QR does not contain a booking token."}
        except HTTPException as exc:
            return {"valid": False, "message": str(exc.detail)}
    booking = first("bookings", token=token, centre_id=centre_id)
    if not booking:
        return {"valid": False, "message": "Invalid token for this procurement centre."}
    farmer = first("farmers", farmer_id=booking.get("farmer_id")) or {}
    if booking.get("status") in ("cancelled", "skipped", "completed"):
        return {"valid": False, "message": f"Token is {booking.get('status')}.", "booking": booking, "farmer": farmer, "signed": bool(signed_payload)}
    return {"valid": True, "message": "Token verified successfully.", "booking": booking, "farmer": farmer, "signed": bool(signed_payload)}

@app.get("/api/queue/{centre_id}")
def get_queue(centre_id: str, user_token: Optional[str] = None, authorization: Optional[str] = Header(None)):
    auth = verify_token(authorization)
    if auth.get("role") == "centre":
        if auth.get("sub") != centre_id: raise HTTPException(403, "Centre access denied.")
    elif auth.get("role") == "admin":
        pass
    elif auth.get("role") == "farmer":
        own = first("farmers", farmer_id=auth.get("sub"))
        if not own or own.get("centre_id") != centre_id: raise HTTPException(403, "Farmer access denied.")
        if user_token:
            own_booking = first("bookings", token=user_token, farmer_id=auth.get("sub"), centre_id=centre_id)
            if not own_booking: raise HTTPException(403, "Farmer access denied.")
    else: raise HTTPException(403, "Access denied.")
    if user_token:
        booking = first("bookings", token=user_token, centre_id=centre_id)
        if not booking:
            raise HTTPException(404, "Token not found.")
        # Farmer callers are already scoped to their own booking above.
        # Centre/admin callers may inspect a token within their centre scope;
        # do not incorrectly run a farmer-role check against their operator token.
        if auth.get("role") == "farmer":
            if booking.get("farmer_id") != auth.get("sub"):
                raise HTTPException(403, "Farmer access denied.")
        elif auth.get("role") not in ("centre", "admin"):
            raise HTTPException(403, "Access denied.")
    else:
        require_any_operator(authorization, centre_id)
    return queue_state(centre_id, user_token)


@app.get("/api/v1/land/{farmer_id}")
def verified_land_records(farmer_id: str, authorization: Optional[str] = Header(None)):
    auth = verify_token(authorization, "farmer")
    if auth.get("sub") != farmer_id:
        raise HTTPException(403, "Farmer access denied.")
    try:
        return db_required().table("land_records").select("land_record_id,survey_khasra_no,land_area_acre,crop,max_crop_quantity_kg,verified_source,verified_at").eq("farmer_id", farmer_id).order("crop").execute().data or []
    except Exception as exc:
        raise HTTPException(503, "Land verification service is not configured. Apply SIH_V10_PRODUCTION.sql first.") from exc

@app.websocket("/api/ws/queue/{centre_id}")
async def legacy_queue_ws(ws: WebSocket, centre_id: str):
    await ws.accept()
    try:
        hello = await ws.receive_json()
        auth = verify_token(f"Bearer {hello.get('access_token','')}")
        if auth.get("role") == "farmer":
            farmer = first("farmers", farmer_id=auth.get("sub"))
            if not farmer or farmer.get("centre_id") != centre_id:
                await ws.close(code=1008, reason="Farmer access denied")
                return
        elif auth.get("role") == "centre":
            if auth.get("sub") != centre_id:
                await ws.close(code=1008, reason="Centre access denied")
                return
        elif auth.get("role") != "admin":
            await ws.close(code=1008, reason="Access denied")
            return
        user_token = hello.get("user_token")
        if auth.get("role") == "farmer" and user_token:
            own = first("bookings", token=user_token, farmer_id=auth.get("sub"), centre_id=centre_id)
            if not own:
                await ws.close(code=1008, reason="Token access denied")
                return
        while True:
            payload = await asyncio.to_thread(queue_state, centre_id, user_token if auth.get("role") == "farmer" else None)
            await ws.send_json({"event":"QUEUE_SNAPSHOT", **payload})
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        return
    except Exception:
        try: await ws.close(code=1011)
        except Exception: pass

@app.get("/api/notifications/{farmer_id}")
def notifications(farmer_id: str, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, farmer_id)
    return db_required().table("notifications").select("*").eq("farmer_id", farmer_id).order("created_at", desc=True).execute().data or []

@app.get("/api/operator/{centre_id}/bookings")
def operator_bookings(centre_id: str, authorization: Optional[str] = Header(None)):
    payload_auth = verify_token(authorization, "centre")
    if payload_auth.get("sub") != centre_id: raise HTTPException(403, "Centre access denied.")
    auto_skip_expired_waiting(centre_id)
    today = datetime.now(BIHAR_TZ).date().isoformat()
    bookings = db_required().table("bookings").select("*").eq("centre_id", centre_id).eq("date", today).execute().data or []
    bookings = _decorate_queue(bookings)
    farmer_ids = list({b.get("farmer_id") for b in bookings if b.get("farmer_id")})
    farmers = {}
    for fid in farmer_ids:
        f = first("farmers", farmer_id=fid)
        if f: farmers[fid] = f
    for b in bookings:
        b["farmer"] = farmers.get(b.get("farmer_id"))
    return bookings

@app.get("/api/operator/{centre_id}/history")
def operator_history(centre_id: str, authorization: Optional[str] = Header(None)):
    payload_auth = verify_token(authorization, "centre")
    if payload_auth.get("sub") != centre_id: raise HTTPException(403, "Centre access denied.")
    """Audit-friendly completed/skipped history for the procurement operator."""
    data = db_required().table("bookings").select("*").eq("centre_id", centre_id).in_("status", ["completed", "skipped", "cancelled"]).order("created_at", desc=True).limit(200).execute().data or []
    farmer_ids = list({b.get("farmer_id") for b in data if b.get("farmer_id")})
    farmers = {fid: first("farmers", farmer_id=fid) for fid in farmer_ids}
    for b in data: b["farmer"] = farmers.get(b.get("farmer_id"))
    return data

@app.post("/api/queue/{centre_id}/action")
def queue_action(centre_id: str, data: QueueAction, authorization: Optional[str] = Header(None)):
    payload_auth = verify_token(authorization, "centre")
    if payload_auth.get("sub") != centre_id: raise HTTPException(403, "Centre access denied.")
    booking = first("bookings", centre_id=centre_id, token=data.token)
    if not booking: raise HTTPException(404, "Token not found")
    if booking["date"] != datetime.now(BIHAR_TZ).date().isoformat(): raise HTTPException(400, "Only today's queue can be operated.")
    action = data.action.lower().strip()
    status_map = {"accept":"serving", "serve":"serving", "serving":"serving", "complete":"procurement_pending", "next":"procurement_pending", "defer":"waiting"}
    allowed = {
        "accept": {"waiting", "confirmed"}, "serve": {"waiting", "confirmed"}, "serving": {"waiting", "confirmed", "serving"},
        "complete": {"serving"}, "next": {"serving"},
        "defer": {"waiting", "serving"}, "skip": {"waiting", "serving"}, "cancel": {"waiting", "confirmed"},
    }
    if action not in allowed: raise HTTPException(400, "Unknown queue action")
    if booking.get("status") not in allowed[action]:
        raise HTTPException(409, f"Invalid queue transition: {booking.get('status')} -> {action}.")
    if action in ("accept", "serve", "serving"):
        if action == "accept":
            # Accepting a farmer at the procurement centre also records check-in.
            # This prevents the old UX dead-end where the operator could not move
            # a waiting booking because checked_in was false.
            booking["checked_in"] = True
        if booking.get("deferred_at") and not booking.get("checked_in"):
            raise HTTPException(409, "Deferred token must check in again before being served.")
        if not booking.get("checked_in"):
            raise HTTPException(409, "Farmer must be checked in before being called to serve.")
    if action == "defer":
        update = {"status":"waiting", "called_at":None, "deferred_at": datetime.now(BIHAR_TZ).isoformat(), "defer_reason": "Skipped for now by procurement centre operator."}
        db_required().table("bookings").update(update).eq("booking_id", booking["booking_id"]).execute()
        notify(booking["farmer_id"], "Queue Update", f"Token {booking['token']} was skipped for now. Your booking remains active.")
        return first("bookings", booking_id=booking["booking_id"])
    if action in ("skip", "cancel"):
        new_queue_status = "cancelled" if action == "cancel" else "skipped"
        update = {"status": new_queue_status, "skipped_at": datetime.now(BIHAR_TZ).isoformat(), "skip_reason": "Manually cancelled by procurement centre operator." if action == "cancel" else "Manually skipped by procurement centre operator."}
        db_required().table("bookings").update(update).eq("booking_id", booking["booking_id"]).execute()
        notify(booking["farmer_id"], "Queue Update", f"Token {booking['token']} status: {new_queue_status}.")
        return first("bookings", booking_id=booking["booking_id"])
    new_status = status_map[action]
    update = {"status":new_status}
    if action == "accept":
        # Acceptance must be durable. The previous implementation only changed
        # the in-memory booking object, so the response looked accepted while
        # Supabase still had checked_in=false.
        now = datetime.now(BIHAR_TZ).isoformat()
        update["checked_in"] = True
        update["arrived_at"] = booking.get("arrived_at") or now
        update["deferred_at"] = None
        update["defer_reason"] = None
    if action in ("accept", "serve", "serving") and not booking.get("called_at"):
        update["called_at"] = datetime.now(BIHAR_TZ).isoformat()
    if new_status == "procurement_pending":
        update["procurement_started_at"] = datetime.now(BIHAR_TZ).isoformat()
    db_required().table("bookings").update(update).eq("booking_id", booking["booking_id"]).execute()
    audit(f"QUEUE_{new_status.upper()}", centre_id=centre_id, farmer_id=booking.get("farmer_id"), token=booking.get("token"), details={"action":action})
    notify(booking["farmer_id"], "Queue Update", f"Token {booking['token']} status: {new_status}.")
    return first("bookings", booking_id=booking["booking_id"])

@app.post("/api/procurements")
def create_procurement(data: ProcurementIn, authorization: Optional[str] = Header(None)):
    require_centre(authorization, data.centre_id)
    booking = first("bookings", token=data.token, farmer_id=data.farmer_id, centre_id=data.centre_id)
    if not booking: raise HTTPException(404, "Booking not found for this token.")
    if booking.get("status") != "procurement_pending":
        raise HTTPException(409, f"Token {data.token} is not ready for procurement. Current status: {booking.get('status')}.")
    existing = first("procurements", token=booking["token"], farmer_id=data.farmer_id)
    if existing: return existing
    if data.crop.strip().lower() != str(booking.get("crop") or "").strip().lower(): raise HTTPException(400, "Procurement crop must match the booked crop.")
    # Procurement settlement uses the latest centrally managed Admin rate.
    managed = _current_admin_rates(data.crop.strip())
    if not managed:
        raise HTTPException(503, "Admin procurement rate is not configured for this crop. Ask the Admin to update the rate.")
    rate = float(managed[0].get("rate_per_kg") or 0)
    if rate <= 0: raise HTTPException(400, "Rate must be positive")
    if float(data.quantity_kg) > float(booking.get("quantity_kg") or 0): raise HTTPException(400, "Procurement quantity cannot exceed the booked quantity.")
    if data.quantity_kg > 100000: raise HTTPException(400, "Quantity exceeds the allowed demo limit.")
    if rate > 100000: raise HTTPException(400, "Rate exceeds the allowed limit.")
    auth = require_centre(authorization, data.centre_id)
    centre_user = first("centres", centre_id=data.centre_id) or {}
    gross = float(data.gross_weight_kg if data.gross_weight_kg is not None else data.quantity_kg)
    tare = float(data.tare_weight_kg or 0)
    net = round(gross - tare, 2)
    if gross <= 0 or tare < 0 or net <= 0: raise HTTPException(400, "Invalid gross/tare weights.")
    if data.moisture_percent is not None and not (0 <= data.moisture_percent <= 100): raise HTTPException(400, "Moisture must be between 0 and 100%.")
    amount = round(net * rate, 2)
    payload = {"procurement_id":str(uuid.uuid4()), "farmer_id":data.farmer_id, "centre_id":data.centre_id, "crop":data.crop,
               "quantity_kg":net, "gross_weight_kg":gross, "tare_weight_kg":tare, "moisture_percent":data.moisture_percent,
               "quality_grade":data.quality_grade, "rate_per_kg":rate, "amount":amount, "token":booking["token"],
               "employee_id": centre_user.get("employee_id"), "completed_at": datetime.now(BIHAR_TZ).isoformat()}
    completed_at = datetime.now(BIHAR_TZ)
    try:
        result = db_required().rpc("complete_procurement_atomic", {
            "p_procurement_id": payload["procurement_id"],
            "p_farmer_id": data.farmer_id,
            "p_centre_id": data.centre_id,
            "p_crop": data.crop,
            "p_quantity_kg": net,
            "p_gross_weight_kg": gross,
            "p_tare_weight_kg": tare,
            "p_moisture_percent": data.moisture_percent,
            "p_quality_grade": data.quality_grade,
            "p_rate_per_kg": rate,
            "p_token": booking["token"],
            "p_employee_id": centre_user.get("employee_id"),
            "p_completed_at": completed_at.isoformat(),
        }).execute().data
    except Exception as exc:
        print("[PROCUREMENT RPC ERROR]", repr(exc))
        raise HTTPException(503, "Atomic procurement service is unavailable. Run backend/PROCUREMENT_ATOMIC_FIX.sql in Supabase SQL Editor and reload the schema cache.")
    if not result:
        raise HTTPException(500, "Procurement transaction returned no record.")
    # Create the DBT payment ledger entry as part of the completion flow.
    # The actual credit remains an operator-settled step, but the farmer must
    # immediately see the payable amount after procurement is completed.
    try:
        payment = first("payments", farmer_id=data.farmer_id, token=booking["token"])
        if not payment:
            payment_payload = {
                "payment_id": f"DBT-{uuid.uuid4().hex[:12].upper()}",
                "farmer_id": data.farmer_id,
                "token": booking["token"],
                "status": "processing",
                "amount": amount,
            }
            try:
                db_required().table("payments").insert(payment_payload).execute()
            except Exception:
                # Unique(farmer_id, token) protects against concurrent retries.
                payment = first("payments", farmer_id=data.farmer_id, token=booking["token"])
                if not payment:
                    raise
    except Exception as exc:
        print("[PAYMENT LEDGER ERROR]", repr(exc))
        raise HTTPException(503, "Procurement completed but DBT ledger could not be created. Please retry after checking the payments table migration.")

    audit("PROCUREMENT_COMPLETED", centre_id=data.centre_id, farmer_id=data.farmer_id, token=booking["token"], details={"gross_kg":gross,"tare_kg":tare,"net_kg":net,"moisture":data.moisture_percent,"amount":amount})
    notify(data.farmer_id, "Procurement Completed", f"Token {booking['token']}: {net:.2f} kg procured for ₹{amount:.2f}. DBT ledger created.")
    farmer = first("farmers", farmer_id=data.farmer_id) or {}
    if farmer.get("email"):
        try:
            send_completion_email(
                farmer["email"],
                farmer.get("name", "Kisan"),
                str(booking["token"]),
                f"{net:.2f} kg",
                f"₹{amount:.2f}",
                completed_at.strftime("%d-%m-%Y %I:%M %p"),
            )
        except Exception as exc:
            print("[EMAIL] completion mail error:", exc)
    return result[0]

@app.get("/api/procurements/{farmer_id}")
def farmer_procurements(farmer_id: str, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, farmer_id)
    return db_required().table("procurements").select("*").eq("farmer_id", farmer_id).order("created_at", desc=True).execute().data or []

@app.get("/api/payments/{farmer_id}")
def farmer_payments(farmer_id: str, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, farmer_id)
    return db_required().table("payments").select("*").eq("farmer_id", farmer_id).execute().data or []

@app.post("/api/payments")
def initiate_payment(data: PaymentIn, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, data.farmer_id)
    procurement = first("procurements", farmer_id=data.farmer_id, token=data.token)
    if not procurement: raise HTTPException(400, "Procurement not found for this token.")
    existing = first("payments", farmer_id=data.farmer_id, token=data.token)
    if existing: return existing
    payload = {"payment_id":f"DBT-{uuid.uuid4().hex[:12].upper()}", "farmer_id":data.farmer_id, "token":data.token, "status":"processing", "amount":procurement["amount"]}
    try:
        result = db_required().table("payments").insert(payload).execute().data
    except Exception as exc:
        # Two rapid clicks/tabs can race the unique (farmer_id, token) payment row.
        # Return the already-created payment instead of surfacing a false 500.
        existing = first("payments", farmer_id=data.farmer_id, token=data.token)
        if existing:
            return existing
        raise HTTPException(400, f"DBT initiation failed: {exc}")
    if not result:
        existing = first("payments", farmer_id=data.farmer_id, token=data.token)
        if existing:
            return existing
        raise HTTPException(500, "DBT initiation returned no payment record.")
    audit("DBT_INITIATED", farmer_id=data.farmer_id, token=data.token, details={"payment_id":payload["payment_id"],"amount":procurement["amount"]})
    notify(data.farmer_id, "DBT Initiated", f"DBT payment of ₹{float(procurement['amount']):.2f} is processing.")
    return result[0]

def _settle_payment(payment_id: str):
    payment = first("payments", payment_id=payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment["status"] == "credited":
        return payment
    utr = f"KS{datetime.now(BIHAR_TZ).strftime('%y%m%d')}{secrets.token_hex(4).upper()}"
    db_required().table("payments").update({
        "status":"credited", "completed_at":datetime.now(BIHAR_TZ).isoformat(),
        "utr":utr, "settlement_mode":"SIMULATED_DBT"
    }).eq("payment_id", payment_id).execute()
    audit("DBT_CREDITED", farmer_id=payment["farmer_id"], token=payment["token"],
          details={"payment_id":payment_id,"utr":utr,"amount":payment.get("amount")})
    notify(payment["farmer_id"], "DBT Credited",
           f"₹{float(payment.get('amount') or 0):.2f} credited for token {payment['token']}. UTR: {utr}")
    return first("payments", payment_id=payment_id)

@app.post("/api/payments/{payment_id}/complete")
def complete_payment(payment_id: str, authorization: Optional[str] = Header(None)):
    payment = first("payments", payment_id=payment_id)
    if not payment: raise HTTPException(404, "Payment not found")
    auth = verify_token(authorization)
    booking = first("bookings", farmer_id=payment["farmer_id"], token=payment["token"])
    if not booking: raise HTTPException(404, "Booking not found for payment.")
    if auth.get("role") == "centre":
        if auth.get("sub") != booking["centre_id"]:
            raise HTTPException(403, "Centre access denied.")
    elif auth.get("role") != "admin":
        raise HTTPException(403, "Only centre operator or admin can settle DBT.")
    return _settle_payment(payment_id)

@app.get("/api/operator/{centre_id}/payments")
def operator_payments(centre_id: str, authorization: Optional[str] = Header(None)):
    require_centre(authorization, centre_id)
    payments = db_required().table("payments").select("*").order("created_at", desc=True).limit(200).execute().data or []
    out=[]
    for p in payments:
        b=first("bookings", farmer_id=p.get("farmer_id"), token=p.get("token"))
        if b and b.get("centre_id")==centre_id:
            out.append(p)
    return out

@app.post("/api/operator/{centre_id}/payments/{payment_id}/complete")
def operator_complete_payment(centre_id: str, payment_id: str, authorization: Optional[str] = Header(None)):
    require_centre(authorization, centre_id)
    payment=first("payments", payment_id=payment_id)
    if not payment: raise HTTPException(404,"Payment not found")
    booking=first("bookings", farmer_id=payment.get("farmer_id"), token=payment.get("token"))
    if not booking or booking.get("centre_id")!=centre_id:
        raise HTTPException(403,"Payment does not belong to this centre.")
    return _settle_payment(payment_id)

def _after_cancel_side_effects(booking):
    """Non-critical post-cancel work; never block the farmer's response."""
    try:
        audit("BOOKING_CANCELLED", centre_id=booking.get("centre_id"), farmer_id=booking.get("farmer_id"), token=booking.get("token"), details={"cancelled_by":"farmer"})
        notify(booking["farmer_id"], "Booking Cancelled", f"Token {booking['token']} booking has been cancelled.")
    except Exception as exc:
        print("cancel notification error:", exc)
    try:
        waiters = db_required().table("waitlist").select("*").eq("centre_id", booking["centre_id"]).eq("booking_date", booking["date"]).eq("slot", booking["slot"]).eq("status", "waiting").order("created_at", desc=False).limit(10).execute().data or []
        for w in waiters:
            existing = rows("bookings", farmer_id=w["farmer_id"])
            if any(x.get("status") in ("waiting", "confirmed", "serving", "procurement_pending") for x in existing):
                continue
            try:
                token_res = db_required().rpc("next_mandi_token", {"p_centre_id": booking["centre_id"]}).execute()
                new_token = token_res.data[0] if isinstance(token_res.data, list) else token_res.data
                new_booking = {"booking_id":str(uuid.uuid4()), "farmer_id":w["farmer_id"], "centre_id":w["centre_id"], "crop":w["crop"], "quantity_kg":w["quantity_kg"], "date":w["booking_date"], "slot":w["slot"], "token":new_token, "status":"waiting", "checked_in":False}
                created = db_required().table("bookings").insert(new_booking).execute().data
                if created:
                    db_required().table("waitlist").update({"status":"promoted"}).eq("waitlist_id",w["waitlist_id"]).execute()
                    audit("WAITLIST_PROMOTED", centre_id=w["centre_id"], farmer_id=w["farmer_id"], token=new_token, details={"slot":w["slot"],"date":w["booking_date"]})
                    notify(w["farmer_id"], "Slot Opened — Booking Confirmed", f"A slot opened for {w['booking_date']}, {w['slot']}. Your new token is {new_token}.")
                break
            except Exception as exc:
                print("waitlist promotion error:", exc)
    except Exception as exc:
        print("waitlist lookup error:", exc)

@app.post("/api/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: str, authorization: Optional[str] = Header(None)):
    booking = first("bookings", booking_id=booking_id)
    if not booking: raise HTTPException(404, "Booking not found")
    require_farmer(authorization, booking["farmer_id"])
    if booking["status"] not in ("waiting", "confirmed"):
        raise HTTPException(400, "Only waiting or confirmed bookings can be cancelled. Once processing starts, cancellation is not allowed.")
    result = db_required().table("bookings").update({"status": "cancelled"}).eq("booking_id", booking_id).in_("status", ["waiting", "confirmed"]).execute()
    updated = result.data or []
    if updated:
        try: _QUEUE_SNAPSHOT_CACHE.pop(booking.get("centre_id"), None)
        except Exception: pass
    if not updated:
        latest = first("bookings", booking_id=booking_id)
        if latest and latest.get("status") != "waiting":
            raise HTTPException(409, "Token can no longer be cancelled because the procurement centre has already started processing it.")
        raise HTTPException(409, "Token cancellation failed. Please refresh and try again.")
    # Return immediately. Audit/notification/waitlist promotion are non-critical
    # side effects and previously made cancellation feel slow.
    _BACKGROUND.submit(_after_cancel_side_effects, booking)
    return {**booking, "status": "cancelled"}

@app.post("/api/bookings/{booking_id}/checkin")
def checkin_booking(booking_id: str, authorization: Optional[str] = Header(None)):
    booking = first("bookings", booking_id=booking_id)
    if not booking: raise HTTPException(404, "Booking not found")
    require_farmer(authorization, booking["farmer_id"])
    if booking["date"] != datetime.now(BIHAR_TZ).date().isoformat(): raise HTTPException(400, "Check-in is available only on the booking date.")
    if booking["status"] != "waiting": raise HTTPException(400, "Only waiting bookings can be checked in.")
    db_required().table("bookings").update({"checked_in":True, "arrived_at": datetime.now(BIHAR_TZ).isoformat(), "deferred_at": None, "defer_reason": None}).eq("booking_id", booking_id).execute()
    audit("FARMER_CHECKED_IN", centre_id=booking.get("centre_id"), farmer_id=booking.get("farmer_id"), token=booking.get("token"))
    notify(booking["farmer_id"], "Check-in Confirmed", f"Token {booking['token']} is checked in.")
    return first("bookings", booking_id=booking_id)

@app.get("/api/operator/{centre_id}/stats")
def operator_stats(centre_id: str, authorization: Optional[str] = Header(None)):
    payload_auth = verify_token(authorization, "centre")
    if payload_auth.get("sub") != centre_id: raise HTTPException(403, "Centre access denied.")
    today = datetime.now(BIHAR_TZ).date().isoformat(); data = rows("bookings", centre_id=centre_id, date=today)
    return {"total":len(data), "waiting":sum(b["status"]=="waiting" for b in data), "serving":sum(b["status"]=="serving" for b in data),
            "procurement_pending":sum(b["status"]=="procurement_pending" for b in data), "completed":sum(b["status"]=="completed" for b in data),
            "cancelled":sum(b["status"]=="cancelled" for b in data)}

@app.post("/api/waitlist")
def join_waitlist(data: BookingIn, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, data.farmer_id)
    farmer=first("farmers", farmer_id=data.farmer_id)
    if not farmer or farmer.get("centre_id") != data.centre_id: raise HTTPException(400,"Centre does not match your district assignment.")
    if data.quantity_kg <= 0: raise HTTPException(400,"Quantity must be greater than 0")
    validate_booking_time(data.date, data.slot)
    existing=first("waitlist", farmer_id=data.farmer_id, booking_date=data.date, slot=data.slot, status="waiting")
    if existing: return existing
    result=db_required().table("waitlist").insert({"waitlist_id":str(uuid.uuid4()),"farmer_id":data.farmer_id,"centre_id":data.centre_id,"booking_date":data.date,"slot":data.slot,"crop":data.crop,"quantity_kg":data.quantity_kg,"status":"waiting"}).execute().data
    audit("WAITLIST_JOINED", centre_id=data.centre_id, farmer_id=data.farmer_id, details={"date":data.date,"slot":data.slot})
    notify(data.farmer_id,"Waitlist Joined",f"You are on the waitlist for {data.date}, {data.slot}. You will be notified if capacity opens.")
    return result[0]

@app.get("/api/waitlist/{farmer_id}")
def farmer_waitlist(farmer_id: str, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, farmer_id)
    return db_required().table("waitlist").select("*").eq("farmer_id",farmer_id).order("created_at", desc=True).limit(30).execute().data or []

@app.get("/api/audit/{farmer_id}")
def farmer_audit(farmer_id: str, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, farmer_id)
    return db_required().table("audit_logs").select("*").eq("farmer_id", farmer_id).order("created_at", desc=True).limit(50).execute().data or []

@app.get("/api/operator/{centre_id}/audit")
def operator_audit(centre_id: str, authorization: Optional[str] = Header(None)):
    require_centre(authorization, centre_id)
    return db_required().table("audit_logs").select("*").eq("centre_id", centre_id).order("created_at", desc=True).limit(100).execute().data or []

@app.get("/api/operator/{centre_id}/no-show")
def operator_no_show(centre_id: str, authorization: Optional[str] = Header(None)):
    require_centre(authorization, centre_id)
    today=datetime.now(BIHAR_TZ).date().isoformat()
    waiting=rows("bookings", centre_id=centre_id, date=today)
    return [{**b, "no_show_prediction":no_show_prediction(b)} for b in waiting if b.get("status")=="waiting"]

@app.get("/api/admin/state-command")
def admin_state_command(authorization: Optional[str] = Header(None)):
    verify_token(authorization, "admin")
    today=datetime.now(BIHAR_TZ).date().isoformat()
    district_rows=[]
    all_today=rows("bookings", date=today)
    live_centres = rows("centres") or []
    centre_source = {c.get("centre_id"): c for c in live_centres}
    for master in CENTRES:
        c = {**master, **centre_source.get(master["centre_id"], {})}
        bs=[b for b in all_today if b.get("centre_id")==c["centre_id"]]
        active=[b for b in bs if b.get("status") in ("waiting","confirmed","serving","procurement_pending")]
        completed=sum(b.get("status")=="completed" for b in bs)
        risks=[no_show_prediction(b) for b in active if b.get("status")=="waiting"]
        cap=dynamic_capacity(c.get("counters",1))
        district_rows.append({"centre_id":c["centre_id"],"district":c["district"],"city":c["city"],"counters":c.get("counters",1),"active":len(active),"completed":completed,"capacity":cap,"utilization_percent":round(min(100,len(active)/max(1,cap)*100)),"congestion":"HIGH" if len(active)>=cap*0.8 else ("MEDIUM" if len(active)>=cap*0.5 else "LOW"),"no_show_high":sum(x["risk"]=="HIGH" for x in risks)})
    return {"date":today,"districts":district_rows,"totals":{"active":sum(x["active"] for x in district_rows),"completed":sum(x["completed"] for x in district_rows),"high_congestion":sum(x["congestion"]=="HIGH" for x in district_rows),"high_no_show":sum(x["no_show_high"] for x in district_rows)},"message":"State command center derived from live centre queues."}

@app.post("/api/demo/seed")
def demo_seed(authorization: Optional[str] = Header(None)):
    verify_token(authorization, "admin")
    farmer_id = "F900001"; mobile = "9000000001"
    if not first("farmers", farmer_id=farmer_id):
        db_required().table("farmers").insert({"farmer_id":farmer_id,"mobile":mobile,"email":None,"name":"Demo Farmer","village":"Demo Village","district":"Jehanabad","crop":"Wheat","centre_id":"C014"}).execute()
    today = datetime.now(BIHAR_TZ).date().isoformat()
    existing = rows("bookings", farmer_id=farmer_id, date=today)
    if not existing:
        for i, slot in enumerate(SLOTS[:3]):
            token = db_required().rpc("next_mandi_token", {"p_centre_id":"C014"}).execute().data
            if isinstance(token, list): token=token[0]
            db_required().table("bookings").insert({"booking_id":str(uuid.uuid4()),"farmer_id":farmer_id,"centre_id":"C014","crop":"Wheat","quantity_kg":200+i*50,"date":today,"slot":slot,"token":token,"status":"serving" if i==0 else "waiting","checked_in":i<2}).execute()
    return {"farmer_id":farmer_id,"mobile":mobile,"centre_id":"C014","message":"Demo data seeded in Supabase"}

@app.get("/api/receipts/{farmer_id}/pdf")
def receipt_pdf(farmer_id: str, authorization: Optional[str] = Header(None)):
    require_farmer(authorization, farmer_id)
    try:
        procurements = db_required().table("procurements").select("*").eq("farmer_id", farmer_id).order("created_at", desc=True).execute().data or []
        farmer = first("farmers", farmer_id=farmer_id) or {}
        payments = db_required().table("payments").select("*").eq("farmer_id", farmer_id).execute().data or []
        payment_by_token = {str(x.get("token")): x for x in payments if x.get("token")}

        buf = BytesIO()
        pdf = canvas.Canvas(buf, pagesize=A4)
        w, h = A4
        pdf.setTitle(f"KisanSetu Payment Receipt {farmer_id}")

        if not procurements:
            pdf.setFillColorRGB(0.98,0.99,0.98)
            pdf.roundRect(18*mm, 90*mm, w-36*mm, 115*mm, 5*mm, fill=1, stroke=0)
            pdf.setStrokeColorRGB(0.72,0.78,0.75)
            pdf.roundRect(18*mm, 90*mm, w-36*mm, 115*mm, 5*mm, fill=0, stroke=1)
            pdf.setFillColorRGB(0.05,0.35,0.20); pdf.setFont("Helvetica-Bold",8)
            pdf.drawString(28*mm, h-42*mm, "KISANSETU")
            pdf.setFillColorRGB(0.05,0.10,0.08); pdf.setFont("Helvetica-Bold",16)
            pdf.drawString(28*mm, h-51*mm, "PAYMENT RECEIPT")
            pdf.setFillColorRGB(0.35,0.40,0.38); pdf.setFont("Helvetica",9)
            pdf.drawString(28*mm, h-68*mm, "No completed procurement found yet.")
        else:
            # One clean receipt page per completed procurement; prevents crowding when history grows.
            for page_no, p in enumerate(procurements, 1):
                if page_no > 1:
                    pdf.showPage()
                centre = find_centre(p.get("centre_id")) or {}
                payment = payment_by_token.get(str(p.get("token")), {})
                amount = p.get("amount", 0)
                rate = p.get("rate_per_kg", 0)
                net = p.get("quantity_kg", 0)
                status = str(payment.get("status") or "PAYMENT PENDING").replace("_"," ").upper()
                utr = payment.get("utr") or "—"

                left, right = 18*mm, w-18*mm
                pdf.setFillColorRGB(0.98,0.99,0.98)
                pdf.roundRect(left, 58*mm, right-left, h-76*mm, 5*mm, fill=1, stroke=0)
                pdf.setStrokeColorRGB(0.72,0.78,0.75)
                pdf.roundRect(left, 58*mm, right-left, h-76*mm, 5*mm, fill=0, stroke=1)

                top = h-24*mm
                pdf.setFillColorRGB(0.05,0.35,0.20); pdf.setFont("Helvetica-Bold",8)
                pdf.drawString(28*mm, top, "KISANSETU")
                pdf.setFillColorRGB(0.05,0.10,0.08); pdf.setFont("Helvetica-Bold",16)
                pdf.drawString(28*mm, top-8*mm, "PAYMENT RECEIPT")
                pdf.setFillColorRGB(0.35,0.40,0.38); pdf.setFont("Helvetica",7.5)
                pdf.drawString(28*mm, top-14*mm, "Smart Procurement • Direct Benefit Transfer Record")
                pdf.setStrokeColorRGB(0.10,0.45,0.28)
                pdf.circle(right-17*mm, top-5*mm, 4*mm, fill=0, stroke=1)
                pdf.setFillColorRGB(0.10,0.45,0.28); pdf.setFont("Helvetica-Bold",9)
                pdf.drawCentredString(right-17*mm, top-7*mm, "✓")

                line_y = top-19*mm
                pdf.setStrokeColorRGB(0.20,0.25,0.23); pdf.line(28*mm,line_y,right-10*mm,line_y)

                # Amount card.
                pdf.setFillColorRGB(0.94,0.98,0.95)
                pdf.setStrokeColorRGB(0.80,0.88,0.83)
                pdf.roundRect(28*mm,line_y-34*mm,76*mm,27*mm,3*mm,fill=1,stroke=1)
                pdf.setFillColorRGB(0.35,0.40,0.38); pdf.setFont("Helvetica-Bold",7.5)
                pdf.drawString(33*mm,line_y-15*mm,"TOTAL AMOUNT")
                pdf.setFillColorRGB(0.04,0.12,0.08); pdf.setFont("Helvetica-Bold",22)
                pdf.drawString(33*mm,line_y-27*mm,f"Rs {float(amount or 0):,.2f}")

                # QR identifies the signed procurement/token.
                signed_qr = sign_sih_qr({
                    "v":1, "type":"payment_receipt", "procurement_id":str(p.get("procurement_id","")),
                    "booking_id":str(p.get("booking_id","")), "token":str(p.get("token","")),
                    "farmer_id":str(farmer_id), "mandi_id":str(p.get("centre_id","")),
                    "exp":int(time.time()) + 60*60*24*365,
                })
                qr_box=35*mm; qr_x=right-44*mm; qr_y=line_y-34*mm
                pdf.setFillColorRGB(1,1,1); pdf.setStrokeColorRGB(0.80,0.84,0.82)
                pdf.roundRect(qr_x,qr_y,qr_box,qr_box,2*mm,fill=1,stroke=1)
                qr=QrCodeWidget(signed_qr,barWidth=29*mm,barHeight=29*mm,barBorder=4)
                d=Drawing(29*mm,29*mm); d.add(qr); d.drawOn(pdf,qr_x+3*mm,qr_y+4*mm)
                pdf.setFillColorRGB(0.30,0.35,0.33); pdf.setFont("Helvetica-Bold",6.8)
                pdf.drawCentredString(qr_x+qr_box/2,qr_y-4*mm,"SCAN TO VERIFY")

                rows=[
                    ("Farmer Name",farmer.get("name","—"),"Farmer ID",farmer_id),
                    ("Token",p.get("token","—"),"Crop",p.get("crop","—")),
                    ("Centre",centre.get("name",p.get("centre_id","—")),"Centre ID",p.get("centre_id","—")),
                    ("Net Quantity",f'{net} kg',"Mandi Rate",f'Rs {float(rate or 0):,.2f} / kg'),
                    ("Quality",p.get("quality_grade","FAQ"),"Gross Weight",f'{p.get("gross_weight_kg") or net} kg'),
                    ("Tare Weight",f'{p.get("tare_weight_kg") or 0} kg',"Moisture",f'{p.get("moisture_percent") or "—"}%'),
                    ("Payment Status",status,"UTR",utr),
                ]
                y=line_y-45*mm
                for l1,v1,l2,v2 in rows:
                    pdf.setFillColorRGB(0.40,0.44,0.42); pdf.setFont("Helvetica",7.5)
                    pdf.drawString(30*mm,y,l1); pdf.drawString(110*mm,y,l2)
                    pdf.setFillColorRGB(0.06,0.12,0.09); pdf.setFont("Helvetica-Bold",8)
                    pdf.drawString(48*mm,y,str(v1)[:34]); pdf.drawString(130*mm,y,str(v2)[:28])
                    y-=8*mm

                foot_y=67*mm
                pdf.setFillColorRGB(0.93,0.97,0.94)
                pdf.roundRect(28*mm,foot_y,right-28*mm,20*mm,3*mm,fill=1,stroke=0)
                pdf.setFillColorRGB(0.05,0.35,0.20); pdf.setFont("Helvetica-Bold",8.5)
                pdf.drawString(33*mm,foot_y+13*mm,"PAYMENT NOTE")
                pdf.setFillColorRGB(0.15,0.20,0.18); pdf.setFont("Helvetica",7)
                pdf.drawString(33*mm,foot_y+7*mm,"This e-receipt records the completed procurement amount and DBT settlement status.")
                pdf.drawString(33*mm,foot_y+3*mm,"Keep the receipt for your records and verify the token/QR when required.")

                pdf.setFillColorRGB(0.45,0.45,0.45); pdf.setFont("Helvetica",6.5)
                pdf.drawString(18*mm,18*mm,"KisanSetu • Digitally generated payment document")
                pdf.drawRightString(w-18*mm,18*mm,f"{page_no}/{len(procurements)}")
        pdf.showPage()
        pdf.save(); buf.seek(0)
        return StreamingResponse(buf,media_type="application/pdf",
            headers={"Content-Disposition":'attachment; filename="kisansetu_payment_receipt.pdf"'})
    except Exception as exc:
        raise HTTPException(500, f"Receipt generation failed: {exc}")

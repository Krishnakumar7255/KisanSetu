"""SIH production extension: Redis-backed booking, signed offline QR, WebSocket queue.
PostgreSQL/Supabase remains the source of truth; Redis is only the short-lived capacity lock.
"""
import os, time, json, base64, hashlib, hmac, uuid, asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Set

from fastapi import APIRouter, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from db import require_db

router = APIRouter(prefix="/api/v1", tags=["SIH Production"])

AUTH_SECRET = os.getenv("AUTH_SECRET", "").strip()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    from redis import Redis
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2)
except Exception:
    redis_client = None

BOOK_LUA = """
local total_key = KEYS[1]
local reservations_key = KEYS[2]
local cap = tonumber(ARGV[1])
local qty = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local rid = ARGV[4]
local existing = redis.call('HGET', reservations_key, rid)
if existing then return -2 end
local used = tonumber(redis.call('GET', total_key) or '0')
if used + qty > cap then return -1 end
redis.call('INCRBYFLOAT', total_key, qty)
redis.call('HSET', reservations_key, rid, qty)
redis.call('EXPIRE', total_key, ttl)
redis.call('EXPIRE', reservations_key, ttl)
return used + qty
"""

RELEASE_LUA = """
local total_key = KEYS[1]
local reservations_key = KEYS[2]
local rid = ARGV[1]
local qty = tonumber(redis.call('HGET', reservations_key, rid) or '0')
if qty <= 0 then return 0 end
redis.call('HDEL', reservations_key, rid)
local used = tonumber(redis.call('GET', total_key) or '0')
local nextv = math.max(0, used - qty)
redis.call('SET', total_key, nextv)
return nextv
"""


class SlotBookIn(BaseModel):
    farmer_id: str
    mandi_id: str
    crop: str = Field(min_length=2, max_length=40)
    quantity_kg: float = Field(gt=0, le=100000)
    slot_id: str
    booking_date: str

class GateScanIn(BaseModel):
    qr_token: str
    mandi_id: str
    offline: bool = False

class QueueManager:
    def __init__(self):
        self.clients: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()
    async def connect(self, mandi: str, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.clients.setdefault(mandi, set()).add(ws)
    async def remove(self, mandi: str, ws: WebSocket):
        async with self.lock:
            self.clients.get(mandi, set()).discard(ws)
    async def broadcast(self, mandi: str, payload: dict):
        async with self.lock:
            targets = list(self.clients.get(mandi, set()))
        dead=[]
        for ws in targets:
            try: await ws.send_json(payload)
            except Exception: dead.append(ws)
        for ws in dead: await self.remove(mandi, ws)

queue_manager = QueueManager()

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")
def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def sign_qr(payload: dict) -> str:
    if not AUTH_SECRET:
        raise RuntimeError("AUTH_SECRET is required")
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(AUTH_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"KSQR1.{body}.{sig}"

def verify_qr(raw: str) -> dict:
    try:
        prefix, body, sig = raw.split(".", 2)
        if prefix != "KSQR1": raise ValueError("format")
        expected = hmac.new(AUTH_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected): raise ValueError("signature")
        payload = json.loads(_unb64(body))
        if int(payload.get("exp", 0)) < int(time.time()): raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(400, "Invalid, tampered, or expired offline QR token.")

def _redis_reserve(key: str, reservations_key: str, capacity: float, quantity: float, ttl: int, reservation_id: str):
    if redis_client is None:
        raise HTTPException(503, "Redis is not installed. Install backend requirements and start Redis.")
    try:
        result = redis_client.eval(BOOK_LUA, 2, key, reservations_key, capacity, quantity, ttl, reservation_id)
        if int(result) == -1:
            raise HTTPException(409, "Slot capacity is currently full.")
        if int(result) == -2:
            raise HTTPException(409, "Duplicate capacity reservation request.")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"Redis capacity service unavailable: {type(exc).__name__}")

def _redis_release(key: str, reservations_key: str, reservation_id: str):
    if redis_client is None:
        return
    try:
        redis_client.eval(RELEASE_LUA, 2, key, reservations_key, reservation_id)
    except Exception:
        pass

@router.post("/slots/book")
def book_slot(data: SlotBookIn, authorization: Optional[str] = Header(None)):
    # Existing KisanSetu auth token format is reused here without exposing the secret.
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentication required.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        raw, sig = token.split(".", 1)
        expected = hmac.new(AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
        payload = json.loads(_unb64(raw))
        if not hmac.compare_digest(sig, expected) or payload.get("role") != "farmer" or payload.get("sub") != data.farmer_id:
            raise ValueError()
    except Exception:
        raise HTTPException(401, "Invalid farmer session.")

    db = require_db()
    farmer_rows = db.table("farmers").select("farmer_id,centre_id").eq("farmer_id", data.farmer_id).limit(1).execute().data or []
    if not farmer_rows:
        raise HTTPException(404, "Farmer profile not found.")
    if farmer_rows[0].get("centre_id") and farmer_rows[0].get("centre_id") != data.mandi_id:
        raise HTTPException(403, "Booking centre does not match the farmer's assigned procurement centre.")

    land = db.table("land_records").select("max_crop_quantity_kg,crop").eq("farmer_id", data.farmer_id).eq("crop", data.crop).limit(1).execute().data or []
    if not land:
        raise HTTPException(403, "Verified land record for this crop is required before booking.")
    quota = float(land[0].get("max_crop_quantity_kg") or 0)
    existing = db.table("token_bookings").select("quantity_kg").eq("farmer_id", data.farmer_id).in_("status", ["BOOKED","ARRIVED","QC_PASSED","WEIGHED","DISPATCHED"]).execute().data or []
    used = sum(float(x.get("quantity_kg") or 0) for x in existing)
    if used + data.quantity_kg > quota:
        raise HTTPException(409, f"Land-verified quota exceeded. Remaining: {max(0, quota-used):.2f} kg.")

    cap_row = db.table("procurement_slots").select("capacity_kg,buffer_kg,booking_date,state").eq("slot_id", data.slot_id).eq("mandi_id", data.mandi_id).limit(1).execute().data or []
    if not cap_row: raise HTTPException(404, "Procurement slot not found.")
    if str(cap_row[0].get("booking_date")) != data.booking_date:
        raise HTTPException(409, "Slot date does not match booking date.")
    if cap_row[0].get("state") not in (None, "OPEN"):
        raise HTTPException(409, "This procurement slot is not open for booking.")
    capacity = max(0, float(cap_row[0].get("capacity_kg") or 0) - float(cap_row[0].get("buffer_kg") or 0))
    key = f"ks:slot:{data.mandi_id}:{data.booking_date}:{data.slot_id}:kg"
    reservations_key = f"{key}:reservations"
    booking_id = str(uuid.uuid4())
    reserved = _redis_reserve(key, reservations_key, capacity, data.quantity_kg, 60 * 60 * 24, booking_id)

    signed = sign_qr({"v":1,"booking_id":booking_id,"farmer_id":data.farmer_id,"mandi_id":data.mandi_id,"slot_id":data.slot_id,"crop":data.crop,"booking_date":data.booking_date,"qty":data.quantity_kg,"exp":int(time.time())+60*60*24*3})
    row = {"booking_id":booking_id,"farmer_id":data.farmer_id,"mandi_id":data.mandi_id,"crop":data.crop,"quantity_kg":data.quantity_kg,"slot_id":data.slot_id,"booking_date":data.booking_date,"status":"BOOKED","qr_hash":hashlib.sha256(signed.encode()).hexdigest()}
    try:
        created = require_db().table("token_bookings").insert(row).execute().data
    except Exception:
        _redis_release(key, reservations_key, booking_id)
        raise HTTPException(503, "Booking database write failed; Redis reservation was rolled back where possible.")
    return {"booking": created[0] if created else row, "signed_qr": signed, "reserved_kg": reserved}

@router.post("/gate/scan")
async def gate_scan(data: GateScanIn):
    payload = verify_qr(data.qr_token)
    if payload.get("mandi_id") != data.mandi_id:
        raise HTTPException(403, "QR token belongs to another mandi.")
    if not payload.get("booking_id") or not payload.get("farmer_id") or not payload.get("slot_id") or not payload.get("booking_date"):
        raise HTTPException(400, "QR token payload is incomplete.")
    if data.offline:
        # Cryptographic authenticity can be checked offline. Replay/consumption must reconcile online later.
        return {"verified":True,"offline":True,"booking_id":payload["booking_id"],"farmer_id":payload["farmer_id"],"mandi_id":payload["mandi_id"],"reconcile_required":True}
    rows = require_db().table("token_bookings").select("*").eq("booking_id", payload["booking_id"]).limit(1).execute().data or []
    if not rows: raise HTTPException(404, "Booking not found.")
    row=rows[0]
    if row.get("qr_hash") != hashlib.sha256(data.qr_token.encode()).hexdigest(): raise HTTPException(409,"QR does not match booking record.")
    if row.get("status") not in ("BOOKED","ARRIVED"): raise HTTPException(409,"Token has already progressed or is not admissible at gate.")
    updated=require_db().table("token_bookings").update({"status":"ARRIVED","arrived_at":datetime.now(timezone.utc).isoformat()}).eq("booking_id",payload["booking_id"]).execute().data
    await queue_manager.broadcast(data.mandi_id,{"event":"ARRIVAL","booking_id":payload["booking_id"]})
    return {"verified":True,"offline":False,"booking":updated[0] if updated else row}

@router.websocket("/ws/queue/{mandi_id}")
async def queue_ws(ws: WebSocket, mandi_id: str):
    await queue_manager.connect(mandi_id, ws)
    try:
        while True:
            rows = require_db().table("token_bookings").select("booking_id,status").eq("mandi_id", mandi_id).in_("status", ["BOOKED","ARRIVED","QC_PASSED","WEIGHED"]).execute().data or []
            waiting=sum(1 for r in rows if r.get("status") in ("BOOKED","ARRIVED"))
            serving=next((r.get("booking_id") for r in rows if r.get("status")=="QC_PASSED"), None)
            await ws.send_json({"mandi_id":mandi_id,"queue_length":waiting,"current_booking":serving,"estimated_wait_minutes":waiting*10})
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        await queue_manager.remove(mandi_id, ws)
    except Exception:
        await queue_manager.remove(mandi_id, ws)

@router.get("/capacity/calculate")
def calculate_capacity(weighbridges: int, avg_turnaround_minutes: float = 10, weather_buffer_pct: float = 10, rated_daily_kg: float = 10000):
    """Judge-demo capacity model: throughput * operating hours, reduced by buffers."""
    if weighbridges < 1 or avg_turnaround_minutes <= 0 or not (0 <= weather_buffer_pct < 100):
        raise HTTPException(400, "Invalid capacity parameters.")
    operating_minutes = 8 * 60
    gross_units = weighbridges * (operating_minutes / avg_turnaround_minutes)
    weather_factor = 1 - weather_buffer_pct / 100
    effective_units = gross_units * weather_factor
    effective_kg = min(rated_daily_kg, effective_units * 1000)
    return {"theoretical_trucks": round(gross_units,2), "weather_adjusted_trucks": round(effective_units,2), "effective_daily_capacity_kg": round(effective_kg,2), "formula":"min(rated_daily_kg, weighbridges * operating_minutes / turnaround * avg_load_kg * (1-weather_buffer))"}

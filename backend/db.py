import os
import threading
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Always load the .env that lives next to this file.
# This works whether FastAPI is started from backend/ or the project root.
ENV_FILE = Path(__file__).resolve().parent / ".env"
PROJECT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
# Backend .env has priority; project-root .env is supported as a fallback.
load_dotenv(dotenv_path=ENV_FILE, override=False)
load_dotenv(dotenv_path=PROJECT_ENV_FILE, override=False)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_ENABLED = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)

supabase = None
_client_lock = threading.Lock()

def _create_client():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

if SUPABASE_ENABLED:
    supabase = _create_client()

def reconnect():
    """Recreate the Supabase client after a dropped HTTP connection.
    The Supabase Python client owns an HTTP connection pool, so a fresh
    client is intentionally created after transport-level failures.
    """
    global supabase
    if not SUPABASE_ENABLED:
        return None
    with _client_lock:
        try:
            supabase = _create_client()
        except Exception as exc:
            print("[KisanSetu] Supabase client recreation failed:", repr(exc))
            raise
        return supabase

_TRANSPORT_ERRORS = (
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.NetworkError,
)

def _is_transport_error(exc):
    return isinstance(exc, _TRANSPORT_ERRORS)

def execute_select(table, filters=None, retries=4):
    """Run a SELECT with fresh-client recovery for transient HTTP failures."""
    if filters is None:
        filters = {}
    last_exc = None
    for attempt in range(max(1, retries)):
        try:
            client = require_db()
            q = client.table(table).select("*")
            for key, value in filters.items():
                q = q.eq(key, value)
            return q.execute().data or []
        except Exception as exc:
            last_exc = exc
            # Supabase/PostgREST can surface an invalid credential as a 401.
            # Do not retry an authentication failure; retries only make the
            # endpoint slower and can turn a clear configuration problem into
            # repeated 500s.  Convert it into a descriptive RuntimeError that
            # the API layer can expose as HTTP 503.
            message = str(exc)
            if "Invalid API key" in message or "Invalid JWT" in message or "401" in message and "api key" in message.lower():
                raise RuntimeError(
                    "Supabase authentication failed: the configured SUPABASE_SERVICE_ROLE_KEY "
                    "is invalid or expired. Update backend/.env with the current Supabase "
                    "service-role/secret key and restart the backend."
                ) from exc
            if not _is_transport_error(exc) or attempt >= retries - 1:
                raise
            print(
                f"[KisanSetu] transient Supabase error on {table}; "
                f"reconnecting ({attempt + 1}/{retries}): {type(exc).__name__}"
            )
            try:
                reconnect()
            except Exception:
                pass
            time.sleep(min(2.0, 0.4 * (attempt + 1)))
    raise last_exc

def require_db():
    if not SUPABASE_ENABLED or supabase is None:
        raise RuntimeError(
            f"Supabase is not configured. Expected SUPABASE_URL and "
            f"SUPABASE_SERVICE_ROLE_KEY in {ENV_FILE}"
        )
    return supabase

"""Offline QR verifier for mandi gate demo.
Usage: python offline_qr.py '<SIGNED_QR>'
Only authenticates the signature and expiry. Replay/consumption must reconcile online.
"""
import os, sys, json, base64, hashlib, hmac
from dotenv import load_dotenv
from pathlib import Path

# Load the backend .env regardless of the directory from which this script is run.
load_dotenv(dotenv_path=Path(__file__).resolve().parent / '.env', override=False)
secret=os.getenv('AUTH_SECRET','').strip()
if not secret: raise SystemExit('Set AUTH_SECRET before offline verification.')
raw=sys.argv[1] if len(sys.argv)>1 else input('Signed QR: ').strip()
try:
    prefix, body, sig=raw.split('.',2)
    expected=hmac.new(secret.encode(),body.encode(),hashlib.sha256).hexdigest()
    if prefix!='KSQR1' or not hmac.compare_digest(sig,expected): raise ValueError('bad signature')
    payload=json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
    import time
    if int(payload.get('exp',0)) < int(time.time()): raise ValueError('expired')
    print(json.dumps({'verified':True,'offline':True,'payload':payload}, indent=2))
except Exception as exc:
    print(json.dumps({'verified':False,'reason':str(exc)}))
    raise SystemExit(1)

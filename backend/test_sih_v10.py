import os, time
os.environ.setdefault('AUTH_SECRET','test-secret-for-local-regression')
from sih_v10 import sign_qr, verify_qr

def main():
    token = sign_qr({'v':1,'booking_id':'b1','farmer_id':'f1','mandi_id':'C001','slot_id':'S1','crop':'Wheat','booking_date':'2026-09-06','qty':100,'exp':int(time.time())+60})
    payload = verify_qr(token)
    assert payload['booking_id']=='b1'
    tampered = token[:-1] + ('0' if token[-1] != '0' else '1')
    try:
        verify_qr(tampered)
    except Exception:
        pass
    else:
        raise AssertionError('tampered QR accepted')
    print('SIH V10 crypto regression: PASS')
if __name__ == '__main__': main()

# KisanSetu V6 Backend

## Run

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --port 8000
```

API:
- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

This demo stores data in memory so MongoDB is optional for the SIH prototype.
Restarting FastAPI clears demo data.

The 38 district entries are district-level representative locations. Replace
their coordinates/address with a verified official procurement-centre dataset
before production deployment.

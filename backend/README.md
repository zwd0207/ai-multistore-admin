# Codex 1 Backend

FastAPI backend for the AI multi-store operations and environment management system.

## Current Scope

This skeleton provides:

- FastAPI application entry point
- SQLite-ready SQLAlchemy database setup
- UTF-8 friendly configuration loading
- Health check endpoint
- Swagger documentation at `/docs`

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
uvicorn app.main:app --reload
```

Then open:

- API root: http://127.0.0.1:8000/
- Health check: http://127.0.0.1:8000/health
- Swagger docs: http://127.0.0.1:8000/docs

## Local Files

Do not commit local secrets or runtime data:

- `.env`
- SQLite database files such as `*.db`, `*.sqlite`, `*.sqlite3`
- virtual environments
- logs and raw API response files

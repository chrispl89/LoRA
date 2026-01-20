# Backend API

FastAPI backend dla LoRA Person MVP.

## Struktura

```
backend/
├── app/
│   ├── api/          # FastAPI endpoints
│   ├── core/         # Config, security, guardrails
│   ├── db/           # SQLAlchemy models, session
│   ├── services/     # Business logic (S3, trainer, inference)
│   ├── workers/      # Celery tasks
│   └── main.py       # FastAPI app
├── alembic/          # Migracje DB
├── tests/            # Testy pytest
└── requirements.txt
```

## Uruchomienie

```bash
# Instalacja
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Migracje
alembic upgrade head

# API
uvicorn app.main:app --reload

# Worker CPU
celery -A app.celery_app worker --loglevel=info --pool=solo -Q cpu_tasks

# Worker GPU
celery -A app.celery_app worker --loglevel=info --pool=solo -Q gpu_tasks
```

## Testy

```bash
pytest -v
```

## Dokumentacja API

Po uruchomieniu API:
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

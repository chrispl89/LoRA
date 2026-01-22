# LoRA Person MVP

Aplikacja do trenowania LoRA dla jednej osoby i generowania obrazów.

## ⚠️ OSTRZEŻENIA I WYMAGANIA PRAWNE

**WAŻNE:** Ta aplikacja wymaga:
- **Zgody osoby** (`consent_confirmed=true`) przed treningiem
- **Potwierdzenia, że osoba jest pełnoletnia** (`subject_is_adult=true`)
- **Zabrania trenowania/generowania treści naruszających prawo**
- System blokuje słowa kluczowe związane z dziećmi i treściami NSFW

## Architektura

- **Frontend**: Next.js (TypeScript)
- **Backend API**: FastAPI
- **Kolejka**: Redis + Celery
- **Baza danych**: PostgreSQL
- **Object Storage**: MinIO (S3-compatible)
- **Workers**: 
  - CPU worker (preprocessing)
  - GPU worker (training + inference) - obecnie stub/pluggable

## Wymagania

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 6+
- MinIO (lub kompatybilny S3)
- (Opcjonalnie) NVIDIA GPU z CUDA dla treningu/inferencji

## Instalacja i uruchomienie (lokalne, bez Dockera)

### 1. Wymagania wstępne

Zainstaluj i uruchom lokalnie:
- **PostgreSQL**: `brew install postgresql` (macOS) lub użyj instalatora dla Windows
- **Redis**: `brew install redis` (macOS) lub pobierz z https://redis.io/download
- **MinIO**: Pobierz z https://min.io/download lub użyj `brew install minio/stable/minio`

Uruchom usługi:
```bash
# PostgreSQL (macOS)
brew services start postgresql

# Redis (macOS)
brew services start redis

# MinIO (w katalogu projektu)
mkdir -p minio-data
minio server minio-data --console-address ":9001"
# MinIO będzie dostępne na http://localhost:9000
# Console na http://localhost:9001 (domyślne: minioadmin/minioadmin)
```

### 2. Konfiguracja środowiska

```bash
# Skopiuj plik środowiskowy (w tym repo nie używamy `.env.example`, bo pliki `.env*`
# bywają blokowane przez ustawienia bezpieczeństwa w niektórych środowiskach)
cp backend/env.example backend/.env

# Edytuj `backend/.env` i ustaw:
# - DATABASE_URL=postgresql://postgres:postgres@localhost:5432/lora_person
# - REDIS_URL=redis://localhost:6379/0
# - MINIO_ENDPOINT=localhost:9000
# - MINIO_ACCESS_KEY=minioadmin
# - MINIO_SECRET_KEY=minioadmin
```

### 3. Backend

```bash
cd backend

# Utwórz virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Zainstaluj zależności
pip install -r requirements.txt

# Utwórz bazę danych
createdb lora_person  # lub przez psql

# Uruchom migracje
make migrate
# lub: alembic upgrade head

# (Opcjonalnie) Dodaj seed data
make seed
```

### 4. Frontend

```bash
cd frontend

# Zainstaluj zależności
npm install

# Uruchom dev server
npm run dev
# Frontend będzie dostępny na http://localhost:3000
```

### 5. Uruchomienie usług

W osobnych terminalach:

**Terminal 1 - API Server:**
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - CPU Worker:**
```bash
cd backend
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info --pool=solo -Q cpu_tasks
```

**Terminal 3 - GPU Worker (opcjonalnie):**
```bash
cd backend
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info --pool=solo -Q gpu_tasks
```

**Terminal 4 - Frontend:**
```bash
cd frontend
npm run dev
```

## Makefile

```bash
make up          # Uruchom wszystkie usługi (wymaga docker-compose - pominięte)
make down        # Zatrzymaj usługi
make migrate     # Uruchom migracje Alembic
make seed        # Dodaj seed data
make api-shell   # Otwórz shell API
make test        # Uruchom testy
```

## Flow użytkownika

1. **Utwórz profil osoby** (`POST /v1/persons`)
   - Wymagane: `name`, `consent_confirmed=true`, `subject_is_adult=true`

2. **Upload zdjęć** (`POST /v1/persons/{id}/uploads/presign`)
   - Pobierz presigned URL
   - Upload pliku bezpośrednio do MinIO
   - Zarejestruj zdjęcie (`POST /v1/persons/{id}/photos/complete`)

3. **Preprocessing** (`POST /v1/persons/{id}/preprocess`)
   - CPU worker: deduplikacja, normalizacja, wykrycie twarzy (stub)

4. **Trening modelu** (`POST /v1/models`)
   - GPU worker: trening LoRA (obecnie stub/placeholder)

5. **Generowanie obrazów** (`POST /v1/generations`)
   - GPU service: generowanie z promptem (obecnie stub)

## API Endpoints

### Health
- `GET /health` - Status aplikacji

### Persons
- `POST /v1/persons` - Utwórz profil osoby
- `GET /v1/persons` - Lista profili
- `GET /v1/persons/{id}` - Szczegóły profilu
- `DELETE /v1/persons/{id}` - Usuń dane (soft delete + S3 cleanup)

### Photos
- `POST /v1/persons/{id}/uploads/presign` - Presigned URL do uploadu
- `POST /v1/persons/{id}/photos/complete` - Zarejestruj zdjęcie

### Preprocessing
- `POST /v1/persons/{id}/preprocess` - Rozpocznij preprocessing

### Models
- `POST /v1/models` - Utwórz model (trening)
- `GET /v1/models` - Lista modeli
- `GET /v1/models/{id}` - Szczegóły modelu
- `GET /v1/model-versions/{id}` - Szczegóły wersji modelu

### Generations
- `POST /v1/generations` - Generuj obraz
- `GET /v1/generations/{id}` - Status i wynik generacji

## Dokumentacja API

Po uruchomieniu API, dokumentacja Swagger dostępna pod:
- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Struktura projektu

```
lora-person-mvp/
├── backend/
│   ├── app/
│   │   ├── api/          # Endpoints FastAPI
│   │   ├── core/         # Config, security, guardrails
│   │   ├── db/           # SQLAlchemy models, session
│   │   ├── services/     # Business logic
│   │   │   ├── s3.py     # MinIO/S3 client
│   │   │   ├── trainer/  # GPU training (stub)
│   │   │   └── inference/ # GPU inference (stub)
│   │   ├── workers/      # Celery tasks
│   │   │   ├── cpu/      # Preprocessing tasks
│   │   │   └── gpu/      # Training/inference tasks
│   │   └── main.py       # FastAPI app
│   ├── alembic/          # Migracje DB
│   ├── tests/            # Testy pytest
│   └── requirements.txt
├── frontend/
│   ├── app/              # Next.js app router
│   ├── components/       # React components
│   └── package.json
└── README.md
```

## Bezpieczeństwo

### Guardrails
- Blokada słów związanych z dziećmi: "child", "kid", "minor", "teenager", etc.
- Blokada słów NSFW (MVP: prosta lista)
- Walidacja zgody przed treningiem

### Usuwanie danych
- `DELETE /v1/persons/{id}` wykonuje:
  - Soft delete w DB
  - Usunięcie zdjęć z S3
  - Usunięcie modeli z S3
  - Logowanie operacji

## Status implementacji

- ✅ Backend API (FastAPI)
- ✅ Modele DB (SQLAlchemy + Alembic)
- ✅ CPU Worker (preprocessing)
- ⚠️ GPU Worker (training) - **STUB** (placeholder)
- ⚠️ GPU Service (inference) - **STUB** (placeholder)
- ✅ Frontend (Next.js)
- ✅ Guardrails i bezpieczeństwo
- ✅ Testy podstawowe

## TODO

- [ ] Implementacja prawdziwego treningu LoRA (diffusers)
- [ ] Implementacja prawdziwej inferencji (diffusers + LoRA injection)
- [ ] Wykrycie twarzy (mediapipe/opencv)
- [ ] Lepsze guardrails (ML-based content filtering)
- [ ] Autentykacja użytkowników (obecnie dev auth)

## Licencja

MIT

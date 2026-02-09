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
- **Baza danych**: SQLite (lokalnie)
- **Object Storage**: MinIO (S3-compatible)
- **Workers**: 
  - CPU worker (preprocessing)
  - GPU worker (training + inference) - działa też na CPU (wolno)

## Wymagania

- Python 3.11+
- Node.js 18+
- Redis 6+
- MinIO (lub kompatybilny S3)
- (Opcjonalnie) NVIDIA GPU z CUDA dla treningu/inferencji

## Hugging Face: tylko bootstrap (offline runtime)

W tej konfiguracji Hugging Face jest **wyłącznie źródłem plików** (jednorazowy download modeli).
Runtime (API + Celery) działa **offline** i ładuje modele **tylko** z:

- dysku (`<repo>/models/base/...`, `<repo>/models/lora/...`)
- MinIO (`s3://<bucket>/models/base/...`, `s3://<bucket>/models/lora/...`)

Repo trzyma cache HF w `.<repo>/.cache/huggingface`.

### Struktura katalogów

```
.cache/
  huggingface/
models/
  base/
    <slug>/
  lora/
    <person_id>/
      <version>/
```

`<slug>` to bezpieczna nazwa katalogu wyliczana z `base_model_name`, np.:
- `sd15` -> `sd15`
- `runwayml/stable-diffusion-v1-5` -> `runwayml__stable-diffusion-v1-5`

### Jednorazowy download bazowego modelu (developer)

Przykład (SD 1.5 do aliasu `sd15`):

```bash
# (uruchom w katalogu repo, NIE w backend/)
pip install -U "huggingface_hub[cli]"
huggingface-cli login  # tylko jeśli model gated

huggingface-cli download runwayml/stable-diffusion-v1-5 \
  --local-dir models/base/sd15 \
  --local-dir-use-symlinks False
```

Alternatywnie (bez instalowania `huggingface-cli`), możesz użyć skryptu w venv backendu:

```bash
cd backend
venv\Scripts\python.exe scripts\download_base_model.py --repo-id runwayml/stable-diffusion-v1-5 --base-model-name sd15 --token <HF_TOKEN>
```

### Upload bazowego modelu do MinIO (zalecane)

```bash
cd backend
venv\Scripts\python.exe scripts\upload_base_model.py --base-model-name sd15 --local-dir ..\models\base\sd15
```

Po tym runtime (offline) w razie braku na dysku pobierze model z MinIO spod:
`models/base/sd15/**`.

## Instalacja i uruchomienie (lokalne, bez Dockera)

### 0. TL;DR (idiotoodpornie, A → Z)

To jest najprostsza ścieżka, jeśli chcesz “po prostu odpalić i używać”.

**A) Start aplikacji**

1. Zainstaluj: **Python 3.11**, **Node 18**, **Redis**.
2. W repo uruchom:

```powershell
cd .\LoRA
.\start-services.ps1
```

3. Otwórz UI: `http://localhost:3000`

**B) Jednorazowo przygotuj bazowy model SD1.5 (online)**

SD 1.5 jest najpraktyczniejszym wyborem na CPU (SDXL będzie bardzo wolny).

1. Załóż konto na HF, zaakceptuj warunki modelu (często “gated”) i wygeneruj token.
2. Pobierz bazowy model do `models/base/sd15`:

```powershell
cd .\LoRA\backend
.\venv\Scripts\python.exe .\scripts\download_base_model.py `
  --repo-id runwayml/stable-diffusion-v1-5 `
  --base-model-name sd15 `
  --token <TWÓJ_HF_TOKEN>
```

3. (Zalecane) Wyślij bazowy model do MinIO, żeby runtime mógł go pobierać offline:

```powershell
cd .\LoRA\backend
.\venv\Scripts\python.exe .\scripts\upload_base_model.py --base-model-name sd15 --local-dir ..\models\base\sd15 --clean
```

**C) Użycie w UI (trening i generowanie)**

1. W UI utwórz profil osoby i zaznacz zgody.
2. Dodaj **3–30** zdjęć (multi-select działa).
3. Kliknij **Start Preprocessing** i poczekaj aż status będzie `finished`.
4. Wejdź w **Models → Create model**:
   - **Base model**: `sd15`
   - **Trigger token**: np. `sks person`
   - **CPU**: zacznij od `steps=200`, `rank=8`, `lr=1e-4`, `resolution=512` (na CPU to może trwać długo).
5. Poczekaj aż wersja modelu będzie `completed`.
6. W **Generate image** wpisz prompt zawierający trigger token, np. `portrait photo of sks person, studio lighting` i kliknij **Generate**.

Gotowe.

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

### 2. Konfiguracja środowiska (skrypt robi to za Ciebie)

Skrypt `start-services.ps1` generuje `backend/.env` (UTF-8 bez BOM) i ustawia zmienne offline dla runtime:
- `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`
- `HF_HOME`, `HF_HUB_CACHE`, `TRANSFORMERS_CACHE`, `DIFFUSERS_CACHE` w `.cache/huggingface`
- `MODELS_DIR=<repo>/models`

Ważne: `HUGGINGFACE_HUB_TOKEN` jest zachowywany (skrypt nie nadpisuje go pustą wartością).

## Jakie są “modele” i czym się różnią?

W tym projekcie “model” to:

- **Base model** (bazowy Stable Diffusion) – duży, ogólny model do generowania obrazów.
- **LoRA** – mały “adapter” trenowany na Twoich zdjęciach, który “uczy” base model Twojej osoby.

### Polecane bazowe modele (praktycznie)

- **SD 1.5 (Stable Diffusion 1.5)**: najlepszy kompromis na CPU.
  - **Plusy**: względnie szybki, stabilny ekosystem, 512×512.
  - **Minusy**: jakość niższa niż SDXL.
  - **Repo (często gated)**: `runwayml/stable-diffusion-v1-5`
  - **Alias w projekcie**: `sd15` (zalecane)

- **SDXL**: lepsza jakość, ale znacznie cięższy.
  - **Plusy**: wyraźnie lepsze detale.
  - **Minusy**: bardzo wolny na CPU, większy storage, większe wymagania RAM/VRAM.

- **Tiny test model** (do debugowania / smoke-testów): szybki, ale jakościowo tylko do testów.
  - Repo: `hf-internal-testing/tiny-stable-diffusion-pipe`

### Co wybrać?

Jeśli działasz na CPU i chcesz “żeby działało”: **SD 1.5**.
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
   - Celery worker: trening LoRA (działa też na CPU, ale wolno)

5. **Generowanie obrazów** (`POST /v1/generations`)
   - Celery worker: generowanie z promptem (diffusers + LoRA)

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
- ✅ Trening LoRA (diffusers + peft) (CPU ok, GPU opcjonalnie)
- ✅ Generowanie obrazów (diffusers + LoRA) (CPU ok, GPU opcjonalnie)
- ✅ Frontend (Next.js)
- ✅ Guardrails i bezpieczeństwo
- ✅ Testy podstawowe

## TODO

- [ ] Ulepszenie jakości treningu (np. captioning / lepszy dataset / scheduler)
- [ ] Ulepszenie jakości inferencji (np. SDXL pipeline, lepsze parametry)
- [ ] Wykrycie twarzy (mediapipe/opencv)
- [ ] Lepsze guardrails (ML-based content filtering)
- [ ] Autentykacja użytkowników (obecnie dev auth)

## Licencja

MIT

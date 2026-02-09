# start-services.ps1
# Uruchamia uslugi dla LoRA Person MVP (BEZ Dockera):
# - MinIO (S3) na 9000/9001 (pobierany automatycznie do katalogu projektu)
# - Redis na 6379 (jesli zainstalowany lokalnie)
# - Backend (FastAPI) na 8000
# - CPU Worker (Celery) dla preprocessingu
# - Frontend (Next.js) na 3000

$ErrorActionPreference = "Stop"

function Write-Section([string]$title) {
  Write-Host ""
  Write-Host "================================================" -ForegroundColor Cyan
  Write-Host ("  " + $title) -ForegroundColor Cyan
  Write-Host "================================================" -ForegroundColor Cyan
  Write-Host ""
}

function Test-Port([int]$port) {
  return (Test-NetConnection -ComputerName "127.0.0.1" -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue)
}

Write-Section "LoRA Person MVP - Start Services (no Docker)"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$runDir = Join-Path $RepoRoot ".run"
if (-not (Test-Path $runDir)) { New-Item -ItemType Directory -Path $runDir | Out-Null }

#
# 0) Offline runtime + persistent storage root (default: D:\LoRa)
#
$DataRoot = $env:LORA_DATA_ROOT
if (-not $DataRoot -or $DataRoot.Trim() -eq "") {
  $DataRoot = "D:\LoRa"
}
if (-not (Test-Path $DataRoot)) {
  New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
}

$cacheRoot = Join-Path $DataRoot ".cache\huggingface"
$modelsRoot = Join-Path $DataRoot "models"
$dbRoot = Join-Path $DataRoot "db"
$dbPath = Join-Path $dbRoot "lora_person.db"
$modelsBase = Join-Path $modelsRoot "base"
$modelsLora = Join-Path $modelsRoot "lora"

# For .env files, prefer forward slashes to avoid python-dotenv escaping issues on Windows (e.g. \U in C:\Users\...)
$repoRootEnv = ($RepoRoot -replace '\\', '/')
$dataRootEnv = ($DataRoot -replace '\\', '/')
$modelsRootEnv = ($modelsRoot -replace '\\', '/')
$cacheRootEnv = ($cacheRoot -replace '\\', '/')
$hfHubCache = (Join-Path $cacheRoot "hub")
$transformersCache = (Join-Path $cacheRoot "transformers")
$diffusersCache = (Join-Path $cacheRoot "diffusers")
$hfHubCacheEnv = ($hfHubCache -replace '\\', '/')
$transformersCacheEnv = ($transformersCache -replace '\\', '/')
$diffusersCacheEnv = ($diffusersCache -replace '\\', '/')
$dbPathEnv = ($dbPath -replace '\\', '/')

if (-not (Test-Path $cacheRoot)) { New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null }
if (-not (Test-Path $dbRoot)) { New-Item -ItemType Directory -Path $dbRoot -Force | Out-Null }
if (-not (Test-Path $modelsBase)) { New-Item -ItemType Directory -Path $modelsBase -Force | Out-Null }
if (-not (Test-Path $modelsLora)) { New-Item -ItemType Directory -Path $modelsLora -Force | Out-Null }

# Force offline mode for runtime (API + Celery). Hugging Face is only a downloader.
$env:PROJECT_ROOT = $RepoRoot
$env:MODELS_DIR = $modelsRoot
$env:HF_RUNTIME_OFFLINE = "1"

$env:HF_HOME = $cacheRoot
$env:HF_HUB_CACHE = $hfHubCache
$env:TRANSFORMERS_CACHE = $transformersCache
$env:DIFFUSERS_CACHE = $diffusersCache
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_HUB_DISABLE_TELEMETRY = "1"

#
# 1) MinIO
#
Write-Host "== MinIO ==" -ForegroundColor Yellow
$minioPath = Join-Path $RepoRoot "minio.exe"
$minioData = Join-Path $DataRoot "minio-data"
if (-not (Test-Path $minioData)) { New-Item -ItemType Directory -Path $minioData | Out-Null }

if (-not (Test-Path $minioPath)) {
  Write-Host "[INFO] minio.exe nie znaleziony - pobieram official MinIO..." -ForegroundColor Yellow
  $url = "https://dl.min.io/server/minio/release/windows-amd64/minio.exe"
  Invoke-WebRequest -Uri $url -OutFile $minioPath -UseBasicParsing
  Unblock-File $minioPath -ErrorAction SilentlyContinue
}

if (-not (Test-Port 9000)) {
  Write-Host "[INFO] Startuje MinIO..." -ForegroundColor Yellow
  $minioProc = Start-Process -FilePath $minioPath -ArgumentList @("server", $minioData, "--console-address", ":9001") -WorkingDirectory $RepoRoot -WindowStyle Minimized -PassThru
  # Daj MinIO czas na start
  for ($i = 0; $i -lt 10 -and -not (Test-Port 9000); $i++) { Start-Sleep -Seconds 1 }
  if (-not (Test-Port 9000)) {
    Write-Host "[ERROR] MinIO nie wystartowal na porcie 9000." -ForegroundColor Red
    exit 1
  }
  Write-Host ("[OK] MinIO: http://localhost:9000 (PID {0})" -f $minioProc.Id) -ForegroundColor Green
} else {
  Write-Host "[OK] MinIO juz dziala na porcie 9000" -ForegroundColor Green
  $minioProc = $null
}

#
# 2) Redis
#
Write-Host ""
Write-Host "== Redis ==" -ForegroundColor Yellow
if (-not (Test-Port 6379)) {
  $redisExe = "C:\Program Files\Redis\redis-server.exe"
  if (Test-Path $redisExe) {
    Write-Host "[INFO] Startuje Redis..." -ForegroundColor Yellow
    $redisProc = Start-Process -FilePath $redisExe -WindowStyle Minimized -PassThru
    Start-Sleep -Seconds 2
    if (-not (Test-Port 6379)) {
      Write-Host "[ERROR] Redis nie wystartowal na porcie 6379." -ForegroundColor Red
      Write-Host "Zainstaluj Redis np. przez: winget install -e --id Redis.Redis" -ForegroundColor Yellow
      exit 1
    }
    Write-Host ("[OK] Redis: localhost:6379 (PID {0})" -f $redisProc.Id) -ForegroundColor Green
  } else {
    Write-Host "[ERROR] Redis nie dziala i nie znaleziono redis-server.exe." -ForegroundColor Red
    Write-Host "Zainstaluj Redis, np.: winget install -e --id Redis.Redis" -ForegroundColor Yellow
    exit 1
  }
} else {
  Write-Host "[OK] Redis juz dziala na porcie 6379" -ForegroundColor Green
  $redisProc = $null
}

#
# 3) Backend env + venv + deps
#
Write-Host ""
Write-Host "== Backend ==" -ForegroundColor Yellow
$backendDir = Join-Path $RepoRoot "backend"
$backendEnvPath = Join-Path $backendDir ".env"

# UWAGA: PowerShell Out-File -Encoding utf8 dodaje BOM -> uzywamy UTF8 bez BOM
$existingToken = ""
if (Test-Path $backendEnvPath) {
  try {
    $existingLine = (Get-Content -Path $backendEnvPath -ErrorAction SilentlyContinue | Where-Object { $_ -like "HUGGINGFACE_HUB_TOKEN=*" } | Select-Object -First 1)
    if ($existingLine) { $existingToken = ($existingLine -replace "^HUGGINGFACE_HUB_TOKEN=", "") }
  } catch {}
}
$backendEnv = @"
DATABASE_URL=sqlite:///$dbPathEnv
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=lora-person-data
MINIO_USE_SSL=false
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=false
# Offline runtime: keep models/cache on $dataRootEnv (repo code stays in $repoRootEnv)
PROJECT_ROOT=$repoRootEnv
MODELS_DIR=$modelsRootEnv
HF_RUNTIME_OFFLINE=1
HF_HOME=$cacheRootEnv
HF_HUB_CACHE=$hfHubCacheEnv
TRANSFORMERS_CACHE=$transformersCacheEnv
DIFFUSERS_CACHE=$diffusersCacheEnv
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
# Hugging Face token (ONLY for bootstrap downloads; runtime is offline)
HUGGINGFACE_HUB_TOKEN=$existingToken
JWT_SECRET=dev-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
CORS_ORIGINS=["http://localhost:3000","http://localhost:3001"]
LOG_LEVEL=INFO
MAX_PHOTO_SIZE_MB=15
MIN_PHOTOS=3
MAX_PHOTOS=30
PRESIGNED_URL_EXPIRATION_SECONDS=3600
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
USE_GPU=false
CUDA_VISIBLE_DEVICES=0
"@
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($backendEnvPath, $backendEnv, $utf8NoBom)
Write-Host "[OK] backend/.env zapisany (UTF-8 bez BOM)" -ForegroundColor Green

$venvDir = Join-Path $backendDir "venv"
function Ensure-Python311 {
  # Prefer Python 3.11/3.12 for torch/diffusers compatibility on Windows
  $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
  if ($pyLauncher) {
    try {
      $out = (py -3.11 -V 2>&1 | Out-String).Trim()
      if ($out -and ($out -notmatch "No suitable Python runtime found")) { return "py -3.11" }
    } catch {}
    try {
      $out = (py -3.12 -V 2>&1 | Out-String).Trim()
      if ($out -and ($out -notmatch "No suitable Python runtime found")) { return "py -3.12" }
    } catch {}
  }
  # Fallback: plain python if it's 3.11/3.12
  try {
    $ver = (python -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null).Trim()
    if ($ver -eq "3.11" -or $ver -eq "3.12") { return "python" }
  } catch {}

  # Auto-install Python 3.11 if winget is available
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if ($winget) {
    Write-Host "[INFO] Instaluję Python 3.11 (wymagany do trenowania diffusers)..." -ForegroundColor Yellow
    winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    # Re-check via launcher
    try {
      $out = (py -3.11 -V 2>&1 | Out-String).Trim()
      if ($out -and ($out -notmatch "No suitable Python runtime found")) { return "py -3.11" }
    } catch {}
  }

  throw "Python 3.11/3.12 nie jest dostępny. Zainstaluj Python 3.11 i uruchom ponownie start-services.ps1."
}

$pyForVenv = Ensure-Python311

if (Test-Path $venvDir) {
  $venvPy = Join-Path $backendDir "venv\\Scripts\\python.exe"
  if (Test-Path $venvPy) {
    $venvVer = (& $venvPy -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null).Trim()
    if ($venvVer -ne "3.11" -and $venvVer -ne "3.12") {
      Write-Host "[WARN] venv jest na Python $venvVer - usuwam i tworzę na 3.11/3.12..." -ForegroundColor Yellow
      Remove-Item -Recurse -Force $venvDir
    }
  }
}

if (-not (Test-Path $venvDir)) {
  Write-Host "[INFO] Tworze venv ($pyForVenv)..." -ForegroundColor Yellow
  Set-Location $backendDir
  if ($pyForVenv -like "py -*") {
    & py ($pyForVenv.Split(" ")[1]) -m venv venv
  } else {
    & $pyForVenv -m venv venv
  }
}

$pyExe = Join-Path $backendDir "venv\Scripts\python.exe"
if (-not (Test-Path $pyExe)) {
  Write-Host "[ERROR] Nie znaleziono $pyExe" -ForegroundColor Red
  exit 1
}

Set-Location $backendDir

# Jeśli deps już są, nie rób ponownej instalacji (oszczędza dużo czasu)
$depsOk = $false
$depsCheckCmd = '""' + $pyExe + '"" -c "import fastapi,uvicorn,sqlalchemy,alembic,pydantic,celery,redis,boto3,PIL" >nul 2>nul'
cmd /c $depsCheckCmd
if ($LASTEXITCODE -eq 0) { $depsOk = $true } else { $depsOk = $false }

if (-not $depsOk) {
  Write-Host "[INFO] Instalowanie zaleznosci backend (pierwsze uruchomienie moze chwile potrwac)..." -ForegroundColor Yellow
  & $pyExe -m pip install --upgrade pip setuptools wheel
  try {
    & $pyExe -m pip install -r requirements.txt
  } catch {
    Write-Host "[WARN] pip install -r requirements.txt nie powiodl sie. Instaluje zestaw minimalny..." -ForegroundColor Yellow
    & $pyExe -m pip install fastapi uvicorn sqlalchemy alembic psycopg2-binary pydantic pydantic-settings celery redis boto3 Pillow imagehash python-jose passlib structlog python-dotenv
  }
  Write-Host "[OK] Backend deps zainstalowane" -ForegroundColor Green
} else {
  Write-Host "[OK] Backend deps juz sa zainstalowane (pomijam pip install)" -ForegroundColor Green
}

#
# 4) Frontend env + deps
#
Write-Host ""
Write-Host "== Frontend ==" -ForegroundColor Yellow
$frontendDir = Join-Path $RepoRoot "frontend"
$frontendEnvPath = Join-Path $frontendDir ".env.local"
[System.IO.File]::WriteAllText($frontendEnvPath, "NEXT_PUBLIC_API_URL=http://localhost:8000`n", $utf8NoBom)
Write-Host "[OK] frontend/.env.local zapisany" -ForegroundColor Green

Set-Location $frontendDir
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
  Write-Host "[INFO] npm install..." -ForegroundColor Yellow
  npm install
}

#
# 5) Start app processes
#
Write-Host ""
Write-Host "== Start procesow aplikacji ==" -ForegroundColor Yellow

Set-Location $backendDir
if (-not (Test-Port 8000)) {
  # Binding to 127.0.0.1 is the most reliable on Windows dev setups
  $apiProc = Start-Process -FilePath $pyExe -ArgumentList @("-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000") -WorkingDirectory $backendDir -WindowStyle Minimized -PassThru
  # Daj aplikacji czas na start (Windows/AV potrafi spowolnic uruchomienie)
  for ($i = 0; $i -lt 20 -and -not (Test-Port 8000); $i++) { Start-Sleep -Seconds 1 }
  if (-not (Test-Port 8000)) {
    Write-Host "[ERROR] Backend nie wystartowal na porcie 8000." -ForegroundColor Red
    exit 1
  }
  Write-Host ("[OK] Backend API: http://localhost:8000 (PID {0})" -f $apiProc.Id) -ForegroundColor Green
} else {
  Write-Host "[OK] Backend juz dziala na porcie 8000" -ForegroundColor Green
  $apiProc = $null
}

# Listen on cpu_tasks + gpu_tasks + celery (legacy default queue) so all tasks get picked up
$celeryProc = Start-Process -FilePath $pyExe -ArgumentList @("-m","celery","-A","app.celery_app","worker","--loglevel=info","--pool=solo","-Q","cpu_tasks,gpu_tasks,celery") -WorkingDirectory $backendDir -WindowStyle Minimized -PassThru
Write-Host ("[OK] Celery worker (cpu+gpu) start (PID {0})" -f $celeryProc.Id) -ForegroundColor Green

Set-Location $frontendDir
if (-not (Test-Port 3000)) {
  # Start npm via cmd.exe (bardziej niezawodne na Windows niż Start-Process na npm.ps1)
  $feProc = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c","npm","run","dev","--","--port","3000") -WorkingDirectory $frontendDir -WindowStyle Minimized -PassThru
  for ($i = 0; $i -lt 25 -and -not (Test-Port 3000); $i++) { Start-Sleep -Seconds 1 }
  Write-Host ("[OK] Frontend: http://localhost:3000 (PID {0})" -f $feProc.Id) -ForegroundColor Green
} else {
  Write-Host "[OK] Frontend juz dziala na porcie 3000" -ForegroundColor Green
  $feProc = $null
}

# Save PIDs for stop script
$pids = [ordered]@{
  minio = if ($minioProc) { $minioProc.Id } else { $null }
  redis = if ($redisProc) { $redisProc.Id } else { $null }
  api   = if ($apiProc)   { $apiProc.Id } else { $null }
  celery= $celeryProc.Id
  frontend = if ($feProc) { $feProc.Id } else { $null }
}
$pidsPath = Join-Path $runDir "pids.json"
($pids | ConvertTo-Json) | Out-File -FilePath $pidsPath -Encoding ascii

Write-Host ""
Write-Host "== GOTOWE ==" -ForegroundColor Green
Write-Host "[OK] UI:        http://localhost:3000" -ForegroundColor Green
Write-Host "[OK] API:       http://localhost:8000/docs" -ForegroundColor Green
Write-Host "[OK] MinIO:     http://localhost:9000 (console: http://localhost:9001)" -ForegroundColor Green
Write-Host ""
Write-Host "Aby zatrzymac: .\\stop-services.ps1" -ForegroundColor Yellow

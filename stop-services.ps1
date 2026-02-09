# stop-services.ps1
# Zatrzymuje uslugi dla LoRA Person MVP (BEZ Dockera)

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  LoRA Person MVP - Stop Services" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Zatrzymywanie uslug..." -ForegroundColor Yellow

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidsPath = Join-Path $RepoRoot ".run\\pids.json"

function Stop-ByPid($pid, $label) {
  if (-not $pid) { return }
  try {
    $p = Get-Process -Id $pid -ErrorAction Stop
    Stop-Process -Id $pid -Force -ErrorAction Stop
    Write-Host ("[OK] Zatrzymano {0} (PID {1})" -f $label, $pid) -ForegroundColor Green
  } catch {
    Write-Host ("[WARN] Nie udalo sie zatrzymac {0} (PID {1}) - moze juz nie dziala." -f $label, $pid) -ForegroundColor Yellow
  }
}

if (Test-Path $pidsPath) {
  try {
    $pids = Get-Content $pidsPath -Raw | ConvertFrom-Json
    Stop-ByPid $pids.frontend "frontend"
    Stop-ByPid $pids.celery "celery"
    Stop-ByPid $pids.api "backend api"
    Stop-ByPid $pids.minio "minio"
    Stop-ByPid $pids.redis "redis"
    Remove-Item $pidsPath -ErrorAction SilentlyContinue
  } catch {
    Write-Host "[WARN] Nie udalo sie odczytac pids.json - robie fallback po nazwach procesow." -ForegroundColor Yellow
  }
}

# Fallback: kill known commandlines (safe for dev)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'uvicorn' -or $_.CommandLine -match 'celery' } | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Host ("[OK] Zatrzymano python (PID {0})" -f $_.ProcessId) -ForegroundColor Green
}
Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -match 'next' -or $_.CommandLine -match 'next dev' } | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Host ("[OK] Zatrzymano node/next (PID {0})" -f $_.ProcessId) -ForegroundColor Green
}
Get-Process -Name minio -ErrorAction SilentlyContinue | ForEach-Object {
  Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
  Write-Host ("[OK] Zatrzymano minio (PID {0})" -f $_.Id) -ForegroundColor Green
}

Write-Host ""
Write-Host "[OK] Zatrzymywanie zakonczone." -ForegroundColor Green

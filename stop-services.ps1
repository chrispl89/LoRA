# stop-services.ps1
# Zatrzymuje wszystkie usługi dla LoRA Person MVP

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  LoRA Person MVP - Stop Services" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Zatrzymywanie uslug..." -ForegroundColor Yellow
docker-compose down

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[OK] Uslugi zatrzymane pomyslnie!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[ERROR] Nie udalo sie zatrzymac uslug!" -ForegroundColor Red
    exit 1
}

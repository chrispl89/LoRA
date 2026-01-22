# start-services.ps1
# Uruchamia wszystkie wymagane usługi dla LoRA Person MVP

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  LoRA Person MVP - Start Services" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Sprawdz czy Docker jest uruchomiony
try {
    docker info | Out-Null
    Write-Host "[OK] Docker jest uruchomiony" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker nie jest uruchomiony!" -ForegroundColor Red
    Write-Host "Uruchom Docker Desktop i sprobuj ponownie." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Uruchamianie Docker Compose (PostgreSQL, Redis, MinIO)..." -ForegroundColor Yellow
Write-Host ""

# Uruchom docker-compose
docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[OK] Uslugi uruchomione pomyslnie!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Status kontenerow:" -ForegroundColor Cyan
    docker-compose ps
    Write-Host ""
    Write-Host "[OK] PostgreSQL: localhost:5432" -ForegroundColor Green
    Write-Host "   Database: lora_person" -ForegroundColor Gray
    Write-Host "   User: postgres / Password: postgres" -ForegroundColor Gray
    Write-Host ""
    Write-Host "[OK] Redis: localhost:6379" -ForegroundColor Green
    Write-Host ""
    Write-Host "[OK] MinIO: http://localhost:9000" -ForegroundColor Green
    Write-Host "   Console: http://localhost:9001" -ForegroundColor Green
    Write-Host "   Access Key: minioadmin" -ForegroundColor Gray
    Write-Host "   Secret Key: minioadmin" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Czekam 5 sekund na uruchomienie uslug..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    Write-Host ""
    Write-Host "Aby zobaczyc logi:" -ForegroundColor Yellow
    Write-Host "  docker-compose logs -f" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Aby zatrzymac uslugi:" -ForegroundColor Yellow
    Write-Host "  docker-compose down" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Aby sprawdzic status:" -ForegroundColor Yellow
    Write-Host "  docker-compose ps" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "[ERROR] Nie udalo sie uruchomic uslug!" -ForegroundColor Red
    Write-Host "Sprawdz logi: docker-compose logs" -ForegroundColor Yellow
    exit 1
}

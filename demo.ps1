# NSEC Cache Datastore Demo - PowerShell Script
# Alternative to Makefile for Windows users

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

function Show-Help {
    Write-Host "NSEC Cache Datastore Demo" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\demo.ps1 [command]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  init          Initialize .env from env.example"
    Write-Host "  up            Start all containers"
    Write-Host "  down          Stop and remove containers"
    Write-Host "  demo          Run the complete demo"
    Write-Host "  prime         Run priming phase only"
    Write-Host "  verify        Run verification phase only"
    Write-Host "  report        Generate and display report"
    Write-Host "  test          Run unit tests"
    Write-Host "  logs-auth     Show authoritative server logs"
    Write-Host "  logs-rec      Show recursive resolver logs"
    Write-Host "  clean         Remove containers and generated files"
    Write-Host ""
}

function Initialize-Env {
    if (-not (Test-Path ".env")) {
        Copy-Item "env.example" ".env"
        Write-Host "[+] Created .env from env.example" -ForegroundColor Green
    } else {
        Write-Host "[*] .env already exists" -ForegroundColor Yellow
    }
}

function Start-Containers {
    Initialize-Env
    Write-Host "[+] Starting NSEC Cache Datastore Demo..." -ForegroundColor Cyan
    docker compose up -d --build
    Write-Host "[+] Waiting for services to be healthy..." -ForegroundColor Cyan
    Start-Sleep -Seconds 10
    docker compose ps
}

function Stop-Containers {
    Write-Host "[+] Stopping containers..." -ForegroundColor Cyan
    docker compose down --remove-orphans
}

function Run-Demo {
    Start-Containers
    Write-Host ""
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host "    NSEC Cache Datastore Demo" -ForegroundColor Cyan
    Write-Host "==============================================" -ForegroundColor Cyan
    Write-Host ""
    Start-Sleep -Seconds 5
    Write-Host "[+] Running priming phase..." -ForegroundColor Cyan
    docker compose exec -T client python3 /app/scripts/prime.py
    Write-Host ""
    Start-Sleep -Seconds 2
    Write-Host "[+] Running verification phase..." -ForegroundColor Cyan
    docker compose exec -T client python3 /app/scripts/verify_synthesis.py
    Write-Host ""
    Write-Host "[+] Generating report..." -ForegroundColor Cyan
    Write-Host ""
    docker compose exec -T client python3 /app/scripts/report.py
}

function Run-Prime {
    docker compose exec -T client python3 /app/scripts/prime.py
}

function Run-Verify {
    docker compose exec -T client python3 /app/scripts/verify_synthesis.py
}

function Show-Report {
    docker compose exec -T client python3 /app/scripts/report.py
}

function Run-Tests {
    Write-Host "[+] Running unit tests..." -ForegroundColor Cyan
    docker compose exec -T client pytest /app/tests/test_encoder.py /app/tests/test_ordering.py -v
}

function Show-AuthLogs {
    Write-Host "[+] Authoritative Server Query Log:" -ForegroundColor Cyan
    Write-Host "-----------------------------------" -ForegroundColor Cyan
    docker compose exec auth cat /var/log/named/query.log 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "(no queries yet)" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "[+] Authoritative Server Named Log:" -ForegroundColor Cyan
    Write-Host "-----------------------------------" -ForegroundColor Cyan
    docker compose logs auth --tail=50
}

function Show-RecursorLogs {
    Write-Host "[+] Recursive Resolver Log:" -ForegroundColor Cyan
    Write-Host "---------------------------" -ForegroundColor Cyan
    docker compose exec recursor cat /var/log/unbound/unbound.log 2>$null | Select-Object -Last 50
    if ($LASTEXITCODE -ne 0) {
        Write-Host "(no logs yet)" -ForegroundColor Yellow
    }
    Write-Host ""
    docker compose logs recursor --tail=50
}

function Clean-All {
    Write-Host "[+] Cleaning up..." -ForegroundColor Cyan
    docker compose down --remove-orphans -v
    if (Test-Path "results") { Remove-Item -Recurse -Force "results" }
    if (Test-Path "auth\logs") { Remove-Item -Recurse -Force "auth\logs" }
    if (Test-Path "auth\zones") { Remove-Item -Recurse -Force "auth\zones" }
    if (Test-Path "auth\keys") { Remove-Item -Recurse -Force "auth\keys" }
    if (Test-Path "recursor\logs") { Remove-Item -Recurse -Force "recursor\logs" }
    New-Item -ItemType Directory -Force -Path "results", "auth\logs", "auth\zones", "auth\keys", "recursor\logs" | Out-Null
    Write-Host "[+] Cleaned" -ForegroundColor Green
}

# Main command dispatcher
switch ($Command.ToLower()) {
    "help" { Show-Help }
    "init" { Initialize-Env }
    "up" { Start-Containers }
    "down" { Stop-Containers }
    "demo" { Run-Demo }
    "prime" { Run-Prime }
    "verify" { Run-Verify }
    "report" { Show-Report }
    "test" { Run-Tests }
    "logs-auth" { Show-AuthLogs }
    "logs-rec" { Show-RecursorLogs }
    "clean" { Clean-All }
    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host ""
        Show-Help
        exit 1
    }
}

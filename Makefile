# NSEC Cache Datastore Demo
# =========================
# 
# Demonstrates DNSSEC NSEC-chain as a datastore using RFC 8198
# aggressive negative caching.

.PHONY: help up down demo test test-unit test-integration logs-auth logs-rec prime verify report clean init

# Default target
help:
	@echo "NSEC Cache Datastore Demo"
	@echo "========================="
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Setup:"
	@echo "  init          Initialize .env from env.example"
	@echo ""
	@echo "Docker:"
	@echo "  up            Start all containers"
	@echo "  down          Stop and remove containers"
	@echo "  build         Rebuild containers"
	@echo ""
	@echo "Demo:"
	@echo "  demo          Run the complete demo (up + prime + verify + report)"
	@echo "  prime         Run priming phase only"
	@echo "  verify        Run verification phase only"
	@echo "  report        Generate and display report"
	@echo ""
	@echo "Testing:"
	@echo "  test          Run all tests"
	@echo "  test-unit     Run unit tests only"
	@echo "  test-integration  Run integration tests"
	@echo ""
	@echo "Debugging:"
	@echo "  logs-auth     Show authoritative server logs"
	@echo "  logs-rec      Show recursive resolver logs"
	@echo "  shell         Open shell in client container"
	@echo "  dig           Interactive dig against resolver"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean         Remove containers, volumes, and generated files"

# Initialize .env file (Windows-compatible)
init:
	@powershell -Command "if (-not (Test-Path '.env')) { Copy-Item 'env.example' '.env'; Write-Host '[+] Created .env from env.example' } else { Write-Host '[*] .env already exists' }"

# Start Docker environment
up: init
	@echo "[+] Starting NSEC Cache Datastore Demo..."
	docker compose up -d --build
	@echo "[+] Waiting for services to be healthy..."
	@powershell -Command "Start-Sleep -Seconds 10"
	@docker compose ps

# Stop Docker environment
down:
	@echo "[+] Stopping containers..."
	docker compose down --remove-orphans

# Rebuild containers
build: init
	docker compose build --no-cache

# Run the complete demo
demo: up
	@echo ""
	@echo "=============================================="
	@echo "    NSEC Cache Datastore Demo"
	@echo "=============================================="
	@echo ""
	@powershell -Command "Start-Sleep -Seconds 5"
	@echo "[+] Running priming phase..."
	docker compose exec -T client python3 /app/scripts/prime.py
	@echo ""
	@powershell -Command "Start-Sleep -Seconds 2"
	@echo "[+] Running verification phase..."
	docker compose exec -T client python3 /app/scripts/verify_synthesis.py
	@echo ""
	@echo "[+] Generating report..."
	@echo ""
	docker compose exec -T client python3 /app/scripts/report.py

# Run priming only
prime:
	docker compose exec -T client python3 /app/scripts/prime.py

# Run verification only
verify:
	docker compose exec -T client python3 /app/scripts/verify_synthesis.py

# Generate report
report:
	docker compose exec -T client python3 /app/scripts/report.py

# Run all tests
test: test-unit

# Run unit tests
test-unit:
	@echo "[+] Running unit tests..."
	docker compose exec -T client pytest /app/tests/test_encoder.py /app/tests/test_ordering.py -v

# Run integration tests
test-integration: up
	@echo "[+] Running integration tests..."
	@powershell -Command "Start-Sleep -Seconds 5"
	docker compose exec -T client pytest /app/tests/test_integration.py -v --tb=short

# Show auth server logs
logs-auth:
	@echo "[+] Authoritative Server Query Log:"
	@echo "-----------------------------------"
	@docker compose exec auth cat /var/log/named/query.log 2>nul || echo (no queries yet^)
	@echo ""
	@echo "[+] Authoritative Server Named Log:"
	@echo "-----------------------------------"
	docker compose logs auth --tail=50

# Show recursive resolver logs
logs-rec:
	@echo "[+] Recursive Resolver Log:"
	@echo "---------------------------"
	@docker compose exec recursor cat /var/log/unbound/unbound.log 2>nul | powershell -Command "$input | Select-Object -Last 50" || echo (no logs yet^)
	@echo ""
	docker compose logs recursor --tail=50

# Open shell in client container
shell:
	docker compose exec client bash

# Interactive dig
dig:
	@echo "Usage: dig @172.28.0.3 <name> <type> [options]"
	@echo "Example: dig @172.28.0.3 zone.test. SOA +dnssec"
	@echo ""
	docker compose exec client bash

# Clean up everything
clean:
	@echo "[+] Cleaning up..."
	docker compose down --remove-orphans -v
	@powershell -Command "if (Test-Path 'results') { Remove-Item -Recurse -Force 'results' }; if (Test-Path 'auth\logs') { Remove-Item -Recurse -Force 'auth\logs' }; if (Test-Path 'auth\zones') { Remove-Item -Recurse -Force 'auth\zones' }; if (Test-Path 'auth\keys') { Remove-Item -Recurse -Force 'auth\keys' }; if (Test-Path 'recursor\logs') { Remove-Item -Recurse -Force 'recursor\logs' }; New-Item -ItemType Directory -Force -Path 'results','auth\logs','auth\zones','auth\keys','recursor\logs' | Out-Null"
	@echo "[+] Cleaned"

# Show container status
status:
	docker compose ps
	@echo ""
	@echo "Networks:"
	docker network ls | findstr nsec || echo.

# Quick smoke test
smoke: up
	@echo "[+] Smoke test: querying zone SOA..."
	docker compose exec -T client dig @172.28.0.3 zone.test. SOA +short
	@echo "[+] Smoke test: checking DNSSEC..."
	docker compose exec -T client dig @172.28.0.3 zone.test. DNSKEY +short | powershell -Command "$input | Select-Object -First 2"
	@echo "[+] Smoke test passed"

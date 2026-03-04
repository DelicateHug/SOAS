#Requires -Version 5.1
<#
.SYNOPSIS
    Start SOC on a Stick - full platform bootstrap & launch.

.DESCRIPTION
    This script handles first-time setup and ongoing startup:
      1. Checks prerequisites (Docker, OpenSSL, Node.js)
      2. Generates JWT signing keys if missing
      3. Creates .env from .env.example if missing
      4. Installs frontend npm dependencies if needed
      5. Builds and starts all Docker containers

.PARAMETER Dev
    Start in development mode with hot-reload (volume mounts + vite dev server).

.PARAMETER Build
    Force rebuild of all Docker images before starting.

.PARAMETER Down
    Stop and remove all containers instead of starting.

.PARAMETER Rebuild
    Stop all containers, force rebuild all images, then start everything.

.EXAMPLE
    .\start.ps1            # Production-like start
    .\start.ps1 -Dev       # Dev mode with hot reload
    .\start.ps1 -Build     # Force rebuild all images
    .\start.ps1 -Down      # Stop everything
    .\start.ps1 -Rebuild   # Down + rebuild + start
#>

param(
    [switch]$Dev,
    [switch]$Build,
    [switch]$Down,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# --- Colors ---
function Write-Step($msg)    { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)      { Write-Host "   [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)    { Write-Host "   [!] $msg" -ForegroundColor Yellow }
function Write-Fail($msg)    { Write-Host "   [X] $msg" -ForegroundColor Red }

# -------------------------------------------------------------------
# 0. Handle -Down
# -------------------------------------------------------------------
if ($Down) {
    Write-Step "Stopping all containers..."
    Push-Location $ProjectRoot
    docker compose down
    Pop-Location
    Write-Ok "All containers stopped."
    exit 0
}

# -------------------------------------------------------------------
# 0b. Handle -Rebuild (down + force build + start)
# -------------------------------------------------------------------
if ($Rebuild) {
    Write-Step "Stopping all containers for rebuild..."
    Push-Location $ProjectRoot
    docker compose down
    Pop-Location
    Write-Ok "Containers stopped. Will rebuild all images."
    $Build = $true
}

# -------------------------------------------------------------------
# 1. Check prerequisites
# -------------------------------------------------------------------
Write-Step "Checking prerequisites..."

$missing = @()

# Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $missing += "docker"
} else {
    $dockerRunning = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Docker is installed but not running. Please start Docker Desktop."
        exit 1
    }
    Write-Ok "Docker $(docker --version)"
}

# Docker Compose (v2 plugin)
$composeCheck = docker compose version 2>&1
if ($LASTEXITCODE -ne 0) {
    $missing += "docker-compose-plugin"
} else {
    Write-Ok "Docker Compose $($composeCheck)"
}

# OpenSSL (for JWT key generation)
if (-not (Get-Command openssl -ErrorAction SilentlyContinue)) {
    Write-Warn "OpenSSL not found. JWT keys must be generated manually if missing."
} else {
    Write-Ok "OpenSSL available"
}

# Node.js (for frontend dev mode or initial npm install)
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Warn "Node.js not found. Needed for frontend dev mode."
} else {
    Write-Ok "Node $(node --version)"
}

if ($missing.Count -gt 0) {
    Write-Fail "Missing required tools: $($missing -join ', ')"
    Write-Host "   Install Docker Desktop: https://www.docker.com/products/docker-desktop/" -ForegroundColor Gray
    exit 1
}

# -------------------------------------------------------------------
# 2. Generate JWT keys if missing
# -------------------------------------------------------------------
Write-Step "Checking JWT signing keys..."

$secretsDir = Join-Path $ProjectRoot "secrets"
$privateKey  = Join-Path $secretsDir "jwt_private.pem"
$publicKey   = Join-Path $secretsDir "jwt_public.pem"

if ((Test-Path $privateKey) -and (Test-Path $publicKey)) {
    Write-Ok "JWT keys already exist."
} else {
    if (-not (Get-Command openssl -ErrorAction SilentlyContinue)) {
        Write-Fail "Cannot generate JWT keys - OpenSSL is not installed."
        Write-Host "   Install OpenSSL or run: bash scripts/generate-jwt-keys.sh" -ForegroundColor Gray
        exit 1
    }

    Write-Host "   Generating RSA 2048-bit key pair..." -ForegroundColor Gray
    if (-not (Test-Path $secretsDir)) {
        New-Item -ItemType Directory -Path $secretsDir -Force | Out-Null
    }

    openssl genrsa -out $privateKey 2048 2>$null
    openssl rsa -in $privateKey -pubout -out $publicKey 2>$null

    if ((Test-Path $privateKey) -and (Test-Path $publicKey)) {
        Write-Ok "JWT keys generated in secrets/"
    } else {
        Write-Fail "Failed to generate JWT keys."
        exit 1
    }
}

# -------------------------------------------------------------------
# 3. Create .env if missing
# -------------------------------------------------------------------
Write-Step "Checking environment file..."

$envFile = Join-Path $ProjectRoot ".env"
$envExample = Join-Path $ProjectRoot ".env.example"

if (Test-Path $envFile) {
    Write-Ok ".env file exists."
} elseif (Test-Path $envExample) {
    Copy-Item $envExample $envFile
    Write-Ok "Created .env from .env.example (edit with your values if needed)."
} else {
    Write-Warn "No .env or .env.example found. Docker Compose will use defaults."
}

# -------------------------------------------------------------------
# 4. Install frontend dependencies if needed
# -------------------------------------------------------------------
Write-Step "Checking frontend dependencies..."

$frontendDir = Join-Path $ProjectRoot "frontend"
$nodeModules = Join-Path $frontendDir "node_modules"

if (Test-Path $nodeModules) {
    Write-Ok "Frontend node_modules exists."
} else {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Write-Host "   Running npm install..." -ForegroundColor Gray
        Push-Location $frontendDir
        npm install --loglevel=warn 2>&1 | Out-Null
        Pop-Location
        if (Test-Path $nodeModules) {
            Write-Ok "Frontend dependencies installed."
        } else {
            Write-Warn "npm install may have failed - check manually."
        }
    } else {
        Write-Warn "npm not found. Skipping frontend dependency install."
        Write-Host "   The Docker build will handle it, but dev mode requires local deps." -ForegroundColor Gray
    }
}

# -------------------------------------------------------------------
# 5. Build and start containers
# -------------------------------------------------------------------
Write-Step "Starting SOC on a Stick..."

Push-Location $ProjectRoot

$composeFiles = @("-f", "docker-compose.yml")
if ($Dev) {
    $composeFiles += @("-f", "docker-compose.dev.yml")
    Write-Host "   Mode: DEVELOPMENT (hot reload enabled)" -ForegroundColor Yellow
} else {
    Write-Host "   Mode: PRODUCTION-LIKE" -ForegroundColor Green
}

$composeArgs = @("compose") + $composeFiles + @("up", "-d")

if ($Build) {
    $composeArgs += "--build"
    Write-Host "   Forcing image rebuild..." -ForegroundColor Gray
}

Write-Host "   Running: docker $($composeArgs -join ' ')" -ForegroundColor Gray
& docker @composeArgs

if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Fail "Docker Compose failed. Check the output above."
    exit 1
}

Pop-Location

# -------------------------------------------------------------------
# 6. Wait for services and print status
# -------------------------------------------------------------------
Write-Step "Waiting for services to be healthy..."

$maxWait = 60
$elapsed = 0

while ($elapsed -lt $maxWait) {
    Start-Sleep -Seconds 2
    $elapsed += 2

    $health = docker compose -f (Join-Path $ProjectRoot "docker-compose.yml") ps --format json 2>$null |
        ConvertFrom-Json -ErrorAction SilentlyContinue

    if (-not $health) { continue }

    $allUp = $true
    foreach ($svc in $health) {
        if ($svc.State -ne "running") { $allUp = $false; break }
    }

    if ($allUp) { break }
    Write-Host "   Waiting... ($elapsed/$maxWait sec)" -ForegroundColor Gray
}

# Show final status
Write-Host ""
Push-Location $ProjectRoot
docker compose ps
Pop-Location

# -------------------------------------------------------------------
# 7. Print access info
# -------------------------------------------------------------------
$frontendPort = if ($Dev) { "5173" } else { "3000" }

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SOC on a Stick is running!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend:     http://localhost:$frontendPort" -ForegroundColor White
Write-Host "  Backend API:  http://localhost:8000/api/docs" -ForegroundColor White
Write-Host "  Health check: http://localhost:8000/api/health" -ForegroundColor White
Write-Host ""
Write-Host "  PostgreSQL:   localhost:5432  (soas/changeme)" -ForegroundColor Gray
Write-Host "  Redis:        localhost:6379" -ForegroundColor Gray
Write-Host ""
if ($Dev) {
    Write-Host "  Dev mode: source changes hot-reload automatically." -ForegroundColor Yellow
}
Write-Host "  Stop with:    .\start.ps1 -Down" -ForegroundColor Gray
Write-Host "  Rebuild with: .\start.ps1 -Build" -ForegroundColor Gray
Write-Host "  Full rebuild: .\start.ps1 -Rebuild" -ForegroundColor Gray
Write-Host "  View logs:    docker compose logs -f [service]" -ForegroundColor Gray
Write-Host ""

#Requires -Version 5.1
<#
.SYNOPSIS
    Start SOC on a Stick - full platform bootstrap & launch.

.DESCRIPTION
    This script handles first-time setup and ongoing startup:
      1. Validates git branch for dev/prod mode
      2. Checks prerequisites (Docker, OpenSSL, Node.js)
      3. Generates JWT signing keys if missing
      4. Creates .env from .env.example if missing
      5. Installs frontend npm dependencies if needed
      6. Builds and starts all Docker containers

.PARAMETER Dev
    Start in development mode with hot-reload (volume mounts + vite dev server).
    Expects the 'dev' branch by default but allows any branch with local changes.

.PARAMETER Build
    Force rebuild of all Docker images before starting.

.PARAMETER Down
    Stop and remove all containers instead of starting.

.PARAMETER Rebuild
    Stop all containers, force rebuild all images, then start everything.

.PARAMETER Reset
    Factory reset: destroy ALL containers AND volumes (database, Redis, etc.),
    rebuild from scratch, and create a default admin/admin user.

.PARAMETER NoAdmin
    Use with -Reset to skip creating the default admin user. The first user
    can then register through the app's registration page.

.PARAMETER Sync
    Pull latest changes from the remote before starting.
    In dev mode: uses pull --rebase, auto-stashes local changes.
    In prod mode: uses pull --ff-only (fails if diverged).

.PARAMETER InitBranches
    Create 'dev' branch from the current branch, push to origin, and install
    git hooks. Safe to run multiple times (idempotent).

.PARAMETER Branch
    Override the expected branch name for validation.
    Default: 'dev' for -Dev mode, 'main' for prod mode.

.EXAMPLE
    .\start.ps1                     # Production start (must be on main, clean tree)
    .\start.ps1 -Dev                # Dev mode with hot reload
    .\start.ps1 -Dev -Sync          # Dev mode: sync with remote, then start
    .\start.ps1 -Sync               # Prod mode: sync with remote, then start
    .\start.ps1 -Build              # Force rebuild all images
    .\start.ps1 -Down               # Stop everything
    .\start.ps1 -Rebuild            # Down + rebuild + start
    .\start.ps1 -Reset              # Factory reset + admin user
    .\start.ps1 -Reset -NoAdmin     # Factory reset, register first user via app
    .\start.ps1 -InitBranches       # One-time setup: create dev branch + git hooks
    .\start.ps1 -Branch main -Dev   # Dev mode but allow running from main branch
#>

param(
    [switch]$Dev,
    [switch]$Build,
    [switch]$Down,
    [switch]$Rebuild,
    [switch]$Reset,
    [switch]$NoAdmin,
    [switch]$Sync,
    [switch]$InitBranches,
    [string]$Branch
)

$CreateAdmin = $false

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
# 0b. Handle -Reset (destroy everything + rebuild fresh)
# -------------------------------------------------------------------
if ($Reset) {
    Write-Step "RESET: Destroying all containers and volumes..."
    Push-Location $ProjectRoot
    docker compose down -v
    Pop-Location
    Write-Ok "All containers and volumes removed."
    $Build = $true
    if (-not $NoAdmin) { $CreateAdmin = $true }
}

# -------------------------------------------------------------------
# 0c. Handle -Rebuild (down + force build + start)
# -------------------------------------------------------------------
if ($Rebuild -and -not $Reset) {
    Write-Step "Stopping all containers for rebuild..."
    Push-Location $ProjectRoot
    docker compose down
    Pop-Location
    Write-Ok "Containers stopped. Will rebuild all images."
    $Build = $true
}

# -------------------------------------------------------------------
# 0d. Handle -InitBranches (create dev branch + install hooks)
# -------------------------------------------------------------------
if ($InitBranches) {
    Write-Step "Initializing branch structure..."

    $gitCheck = git rev-parse --is-inside-work-tree 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Not a git repository. Cannot initialize branches."
        exit 1
    }

    $status = git status --porcelain 2>&1
    if ($status) {
        Write-Fail "Working tree has uncommitted changes. Commit or stash before initializing branches."
        exit 1
    }

    Write-Host "   Fetching from remote..." -ForegroundColor Gray
    git fetch origin 2>&1 | Out-Null

    # Create dev branch if it doesn't exist
    $devExists = git branch --list "dev" 2>&1
    $devRemoteExists = git ls-remote --heads origin dev 2>&1
    if (-not $devExists.Trim()) {
        if ($devRemoteExists.Trim()) {
            git checkout -b dev origin/dev 2>&1 | Out-Null
            Write-Ok "Checked out existing remote 'dev' branch."
        } else {
            git checkout -b dev 2>&1 | Out-Null
            git push -u origin dev 2>&1 | Out-Null
            Write-Ok "Created and pushed 'dev' branch."
        }
    } else {
        Write-Ok "'dev' branch already exists locally."
    }

    # Switch back to main
    git checkout main 2>&1 | Out-Null

    # Install pre-commit hook
    $hooksDir = Join-Path $ProjectRoot "hooks"
    $hookSource = Join-Path $hooksDir "pre-commit"
    $hookDest = Join-Path $ProjectRoot ".git" "hooks" "pre-commit"
    if (Test-Path $hookSource) {
        Copy-Item $hookSource $hookDest -Force
        Write-Ok "Installed pre-commit hook (production branch warning)."
    } else {
        Write-Warn "No hooks/pre-commit found. Skipping hook install."
    }

    Write-Host ""
    Write-Ok "Branch structure initialized:"
    Write-Host "   dev  - for development (use with -Dev)" -ForegroundColor Yellow
    Write-Host "   main - production branch (use without -Dev)" -ForegroundColor Green
    Write-Host ""
    Write-Host "   Next steps:" -ForegroundColor Gray
    Write-Host "     Dev mode:  git checkout dev && .\start.ps1 -Dev" -ForegroundColor Gray
    Write-Host "     Prod mode: git checkout main && .\start.ps1" -ForegroundColor Gray

    if (-not $Dev -and -not $Build -and -not $Down -and -not $Rebuild -and -not $Reset) {
        exit 0
    }
}

# -------------------------------------------------------------------
# 0e. Git branch validation & sync
# -------------------------------------------------------------------
$isGitRepo = $false
$currentBranch = ""
$gitCheck = git rev-parse --is-inside-work-tree 2>&1
if ($LASTEXITCODE -eq 0) { $isGitRepo = $true }

if ($isGitRepo) {
    $currentBranch = (git rev-parse --abbrev-ref HEAD 2>&1).Trim()

    if ($Dev) {
        # --- DEV MODE BRANCH LOGIC ---
        $expectedBranch = if ($Branch) { $Branch } else { "dev" }

        Write-Step "Git branch: $currentBranch"

        if ($currentBranch -ne $expectedBranch) {
            Write-Warn "Dev mode expects branch '$expectedBranch', currently on '$currentBranch'."
            Write-Host "   Continuing anyway (dev mode allows any branch)." -ForegroundColor Gray
            Write-Host "   Switch with: git checkout $expectedBranch" -ForegroundColor Gray
        } else {
            Write-Ok "On expected dev branch: $currentBranch"
        }

        # Sync in dev mode: pull with rebase to keep local commits on top
        if ($Sync) {
            Write-Step "Syncing with remote (dev mode)..."
            $trackingBranch = git rev-parse --abbrev-ref "@{upstream}" 2>&1
            if ($LASTEXITCODE -eq 0) {
                git fetch origin 2>&1 | Out-Null
                $localChanges = git status --porcelain 2>&1
                if ($localChanges) {
                    Write-Warn "Local changes detected. Stashing before pull..."
                    git stash push -m "auto-stash before sync $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" 2>&1 | Out-Null
                    git pull --rebase origin $currentBranch 2>&1
                    if ($LASTEXITCODE -ne 0) {
                        Write-Fail "Pull --rebase failed. Resolve conflicts, then re-run."
                        Write-Host "   Your changes are in: git stash list" -ForegroundColor Gray
                        exit 1
                    }
                    git stash pop 2>&1
                    if ($LASTEXITCODE -ne 0) {
                        Write-Warn "Stash pop had conflicts. Resolve manually after startup."
                    } else {
                        Write-Ok "Synced and restored local changes."
                    }
                } else {
                    git pull --rebase origin $currentBranch 2>&1
                    if ($LASTEXITCODE -ne 0) {
                        Write-Fail "Pull --rebase failed. Resolve conflicts, then re-run."
                        exit 1
                    }
                    Write-Ok "Synced with remote."
                }
            } else {
                Write-Warn "No upstream tracking branch. Skipping sync."
                Write-Host "   Set with: git push -u origin $currentBranch" -ForegroundColor Gray
            }
        }

    } else {
        # --- PROD MODE BRANCH LOGIC ---
        $expectedBranch = if ($Branch) { $Branch } else { "main" }

        Write-Step "Git branch: $currentBranch (production mode)"

        # STRICT: Must be on the production branch
        if ($currentBranch -ne $expectedBranch) {
            Write-Fail "Production mode requires branch '$expectedBranch', but currently on '$currentBranch'."
            Write-Host ""
            Write-Host "   Options:" -ForegroundColor Gray
            Write-Host "     1. Switch branch:  git checkout $expectedBranch" -ForegroundColor Gray
            Write-Host "     2. Use dev mode:   .\start.ps1 -Dev" -ForegroundColor Gray
            Write-Host "     3. Override branch: .\start.ps1 -Branch $currentBranch" -ForegroundColor Gray
            exit 1
        }

        # STRICT: Working tree must be clean
        $dirtyFiles = git status --porcelain 2>&1
        if ($dirtyFiles) {
            Write-Fail "Production mode requires a clean working tree."
            Write-Host ""
            Write-Host "   Uncommitted changes detected:" -ForegroundColor Red
            git status --short | ForEach-Object { Write-Host "     $_" -ForegroundColor Gray }
            Write-Host ""
            Write-Host "   Options:" -ForegroundColor Gray
            Write-Host "     1. Commit changes:  git add . && git commit" -ForegroundColor Gray
            Write-Host "     2. Stash changes:   git stash" -ForegroundColor Gray
            Write-Host "     3. Use dev mode:    .\start.ps1 -Dev" -ForegroundColor Gray
            exit 1
        }
        Write-Ok "Working tree is clean."

        # STRICT: Check local branch is not ahead of remote (unpushed commits)
        git fetch origin 2>&1 | Out-Null
        $ahead = git rev-list "origin/$expectedBranch..HEAD" --count 2>&1
        if ($LASTEXITCODE -eq 0 -and [int]$ahead -gt 0) {
            Write-Fail "Local '$expectedBranch' is $ahead commit(s) ahead of remote."
            Write-Host "   Production code must come from git. Push or reset your local branch." -ForegroundColor Gray
            exit 1
        }
        Write-Ok "Branch is in sync with remote."

        # Sync in prod mode: fast-forward only
        if ($Sync) {
            Write-Step "Syncing with remote (production mode)..."
            git pull --ff-only origin $expectedBranch 2>&1
            if ($LASTEXITCODE -ne 0) {
                Write-Fail "Fast-forward pull failed. Local branch has diverged from remote."
                Write-Host "   Reset with: git reset --hard origin/$expectedBranch" -ForegroundColor Gray
                exit 1
            }
            Write-Ok "Production branch updated to latest."
        }
    }
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
$opensslCmd = $null
if (Get-Command openssl -ErrorAction SilentlyContinue) {
    $opensslCmd = "openssl"
} else {
    # Fallback: Git for Windows ships openssl under mingw64\bin but doesn't add it to PATH
    $gitOpensslCandidates = @(
        "$env:ProgramFiles\Git\mingw64\bin\openssl.exe",
        "$env:ProgramFiles\Git\usr\bin\openssl.exe",
        "${env:ProgramFiles(x86)}\Git\mingw64\bin\openssl.exe"
    )
    foreach ($cand in $gitOpensslCandidates) {
        if ($cand -and (Test-Path $cand)) { $opensslCmd = $cand; break }
    }
}
if ($opensslCmd) {
    Write-Ok "OpenSSL available ($opensslCmd)"
} else {
    Write-Warn "OpenSSL not found. JWT keys must be generated manually if missing."
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
    if (-not $opensslCmd) {
        Write-Fail "Cannot generate JWT keys - OpenSSL is not installed."
        Write-Host "   Install OpenSSL or run: bash scripts/generate-jwt-keys.sh" -ForegroundColor Gray
        exit 1
    }

    Write-Host "   Generating RSA 2048-bit key pair (using $opensslCmd)..." -ForegroundColor Gray
    if (-not (Test-Path $secretsDir)) {
        New-Item -ItemType Directory -Path $secretsDir -Force | Out-Null
    }

    $savedPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $opensslCmd genrsa -out $privateKey 2048 2>$null
    & $opensslCmd rsa -in $privateKey -pubout -out $publicKey 2>$null
    $ErrorActionPreference = $savedPref

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

# Auto-fill .env placeholders left by .env.example.
# Runs whenever the .env still contains a placeholder, regardless of whether the file is fresh or
# was edited by hand. Each key is fixed independently so partial edits aren't clobbered.
function Resolve-PythonCommand {
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    if (Get-Command python3 -ErrorAction SilentlyContinue) { return "python3" }
    return $null
}

function Get-RandomToken([int]$Length) {
    $bytes = New-Object byte[] $Length
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    # URL-safe base64, trimmed to requested length so .env values stay predictable
    return ([Convert]::ToBase64String($bytes) -replace '\+','-' -replace '/','_' -replace '=','').Substring(0, $Length)
}

if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw
    $envChanged = $false
    $pythonCmd = Resolve-PythonCommand

    # 1. POSTGRES_PASSWORD — also flows into DATABASE_URL, replace both occurrences.
    if ($envContent -match "<your-secure-password-here>") {
        $pgPass = Get-RandomToken 32
        $envContent = $envContent -replace "<your-secure-password-here>", $pgPass
        $envChanged = $true
        Write-Ok "Generated POSTGRES_PASSWORD in .env (also wired into DATABASE_URL)"
    }

    # 2. SOAS_API_TOKEN — inter-service token.
    if ($envContent -match "SOAS_API_TOKEN=<generate-a-secure-token>") {
        $apiToken = Get-RandomToken 48
        $envContent = $envContent -replace "SOAS_API_TOKEN=<generate-a-secure-token>", "SOAS_API_TOKEN=$apiToken"
        $envChanged = $true
        Write-Ok "Generated SOAS_API_TOKEN in .env"
    }

    # 3. USER_SECRET_ENCRYPTION_KEY — must be a real Fernet key (32-byte url-safe b64).
    if ($envContent -match "USER_SECRET_ENCRYPTION_KEY=<generate-a-fernet-key>") {
        $fernetKey = $null
        if ($pythonCmd) {
            $savedPref = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            $fernetKey = & $pythonCmd -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>$null
            # If cryptography isn't installed, install it on the fly. Pip is bundled with Python on Windows.
            if (-not $fernetKey) {
                Write-Host "   cryptography module missing - running pip install cryptography..." -ForegroundColor Gray
                & $pythonCmd -m pip install --quiet --disable-pip-version-check cryptography 2>&1 | Out-Null
                $fernetKey = & $pythonCmd -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>$null
            }
            $ErrorActionPreference = $savedPref
        }
        if ($fernetKey) {
            $fernetKey = $fernetKey.Trim()
            $envContent = $envContent -replace "USER_SECRET_ENCRYPTION_KEY=<generate-a-fernet-key>", "USER_SECRET_ENCRYPTION_KEY=$fernetKey"
            $envChanged = $true
            Write-Ok "Generated USER_SECRET_ENCRYPTION_KEY in .env"
        } else {
            Write-Warn "Python or cryptography unavailable - could not auto-generate Fernet key."
            Write-Host "   Set USER_SECRET_ENCRYPTION_KEY in .env manually:" -ForegroundColor Gray
            Write-Host "   python -m pip install cryptography" -ForegroundColor Gray
            Write-Host "   python -c `"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())`"" -ForegroundColor Gray
        }
    }

    if ($envChanged) {
        Set-Content $envFile $envContent -NoNewline
    }
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
        $savedPref = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        npm install --loglevel=warn 2>&1 | Out-Null
        $ErrorActionPreference = $savedPref
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
    if ($isGitRepo) { Write-Host "   Branch: $currentBranch" -ForegroundColor Yellow }

    # Find an available host port for the frontend (start at 5173, increment if busy)
    $frontendPort = 5173
    while ($frontendPort -lt 5183) {
        $listener = Get-NetTCPConnection -LocalPort $frontendPort -ErrorAction SilentlyContinue
        if (-not $listener) { break }
        Write-Warn "Port $frontendPort is in use, trying $($frontendPort + 1)..."
        $frontendPort++
    }
    $env:FRONTEND_PORT = $frontendPort
} else {
    Write-Host "   Mode: PRODUCTION" -ForegroundColor Green
    if ($isGitRepo) { Write-Host "   Branch: $currentBranch" -ForegroundColor Green }
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
# 7a. Create admin user on -Reset
# -------------------------------------------------------------------
if ($CreateAdmin) {
    Write-Step "Creating default admin user..."

    # Wait for backend API to be fully ready (migrations + startup)
    $backendReady = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $health = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -Method Get -ErrorAction Stop
            if ($health.status -eq "healthy") { $backendReady = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }

    if ($backendReady) {
        try {
            $regBody = @{
                username     = "admin"
                email        = "admin@soas.app"
                display_name = "Administrator"
                password     = "adminadmin"
            } | ConvertTo-Json

            $null = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/register" `
                -Method Post -Body $regBody -ContentType "application/json" -ErrorAction Stop

            Write-Ok "Admin user created  (username: admin / password: adminadmin)"
            Write-Warn "Change this password on first login!"
        } catch {
            Write-Warn "Could not create admin user: $($_.Exception.Message)"
        }
    } else {
        Write-Warn "Backend not ready after 60s. Create admin user manually via the registration page."
    }
}

# -------------------------------------------------------------------
# 7b. Print access info
# -------------------------------------------------------------------
$frontendPort = if ($Dev) { if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" } } else { "3000" }

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SOC on a Stick is running!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend:     http://localhost:$frontendPort" -ForegroundColor White
Write-Host "  Backend API:  http://localhost:8000/api/docs" -ForegroundColor White
Write-Host "  Health check: http://localhost:8000/api/health" -ForegroundColor White
Write-Host "  MCP server:   http://localhost:8765/mcp" -ForegroundColor White
Write-Host "  Embeddings:   internal only (http://embeddings:8200)" -ForegroundColor Gray
Write-Host ""
Write-Host "  PostgreSQL:   localhost:5432  (soas/changeme)" -ForegroundColor Gray
Write-Host "  Redis:        localhost:6379" -ForegroundColor Gray
Write-Host ""

# -------------------------------------------------------------------
# 7c. Surface the MCP service token
# -------------------------------------------------------------------
# The backend seeded an `sst_…` token into the shared mcp_secrets volume on startup.
# Copy a host-side mirror into secrets/mcp_token so editor configs that point at the
# stdio variant (and any non-Docker tooling) can read it without docker exec.
$mcpTokenLocal = Join-Path $ProjectRoot "secrets/mcp_token"
$mcpTokenReady = $false
$mcpToken = ""

for ($i = 0; $i -lt 30; $i++) {
    $tokenRaw = docker exec soas-backend cat /run/mcp/mcp_token 2>$null
    if ($LASTEXITCODE -eq 0 -and $tokenRaw -and $tokenRaw.Trim()) {
        $mcpToken = $tokenRaw.Trim()
        $mcpTokenReady = $true
        break
    }
    Start-Sleep -Seconds 1
}

if ($mcpTokenReady) {
    if (-not (Test-Path (Split-Path $mcpTokenLocal -Parent))) {
        New-Item -ItemType Directory -Path (Split-Path $mcpTokenLocal -Parent) -Force | Out-Null
    }
    Set-Content -Path $mcpTokenLocal -Value $mcpToken -NoNewline -Encoding ASCII
    Write-Host "  MCP token:    $($mcpToken.Substring(0, [Math]::Min(12, $mcpToken.Length)))..." -ForegroundColor Yellow
    Write-Host "                Full token saved to secrets/mcp_token (gitignored)" -ForegroundColor Gray
    Write-Host "                Use this as a Bearer when calling http://localhost:8765/mcp" -ForegroundColor Gray
} else {
    Write-Warn "Could not read MCP token from backend. Try: docker exec soas-backend cat /run/mcp/mcp_token"
}

Write-Host ""
if ($Dev) {
    Write-Host "  Dev mode: source changes hot-reload automatically." -ForegroundColor Yellow
}
if ($isGitRepo) {
    Write-Host "  Git branch: $currentBranch" -ForegroundColor Gray
}
Write-Host ""
Write-Host "  Stop with:        .\start.ps1 -Down" -ForegroundColor Gray
Write-Host "  Rebuild with:     .\start.ps1 -Build" -ForegroundColor Gray
Write-Host "  Full rebuild:     .\start.ps1 -Rebuild" -ForegroundColor Gray
Write-Host "  Factory reset:    .\start.ps1 -Reset" -ForegroundColor Gray
Write-Host "  Init branches:    .\start.ps1 -InitBranches" -ForegroundColor Gray
Write-Host "  Sync & start:     .\start.ps1 -Sync" -ForegroundColor Gray
Write-Host "  Dev + sync:       .\start.ps1 -Dev -Sync" -ForegroundColor Gray
Write-Host "  View logs:        docker compose logs -f [service]" -ForegroundColor Gray
Write-Host ""

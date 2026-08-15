# Generate the SOAS internal CA + per-service certs for mTLS between containers.
# Flat script (no functions) to avoid PS 5.1 scoping quirks when invoked via & path\script.ps1.
#
# Layout (all under ./secrets/mtls/):
#   ca/{ca.key, ca.crt}              the SOAS-services CA
#   <service>/{server.key, server.crt}    server cert (for services that listen)
#   <service>/{client.key, client.crt}    client cert (for services that dial)
#
# Idempotent: skips certs that have > 30 days of life left. Use -Force to regenerate.

param(
    [switch]$Force
)

$ErrorActionPreference = "Continue"

$root = Join-Path $PSScriptRoot "..\..\secrets\mtls"
$caDir = Join-Path $root "ca"

# Resolve OpenSSL with full path to avoid PATH lookup surprises.
$opensslExe = $null
foreach ($c in @(
    "openssl",
    "openssl.exe",
    "C:\Program Files\Git\mingw64\bin\openssl.exe",
    "C:\Program Files\Git\usr\bin\openssl.exe",
    "C:\Program Files\OpenSSL-Win64\bin\openssl.exe"
)) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { $opensslExe = $cmd.Source; break }
}
if (-not $opensslExe) {
    Write-Error "openssl not found on PATH. Install Git for Windows or OpenSSL for Windows."
    exit 1
}
Write-Host "[mtls] Using openssl at $opensslExe"

$services = @("proxy", "backend", "mcp", "frontend", "embeddings", "worker", "worker-beat")
$days = 365

New-Item -ItemType Directory -Force -Path $root | Out-Null
New-Item -ItemType Directory -Force -Path $caDir | Out-Null

$caCert = Join-Path $caDir "ca.crt"
$caKey  = Join-Path $caDir "ca.key"

# ---- CA ----------------------------------------------------------------------
$caHealthy = $false
if ((Test-Path $caCert) -and -not $Force) {
    $endLine = (& $opensslExe x509 -in $caCert -noout -enddate 2>&1) | Select-Object -First 1
    $notAfter = ($endLine -replace "^notAfter=", "").Trim()
    try {
        $expiry = [datetime]::ParseExact($notAfter, "MMM d HH:mm:ss yyyy 'GMT'", $null)
        if (($expiry - (Get-Date)).TotalDays -gt 60) { $caHealthy = $true }
    } catch {}
}

if ($caHealthy) {
    Write-Host "[mtls] CA already healthy -- skipping."
} else {
    Write-Host "[mtls] Generating SOAS-services CA..."
    & $opensslExe genrsa -out $caKey 4096 2>&1 | Out-Null
    & $opensslExe req -x509 -new -nodes -key $caKey -sha256 -days ($days * 5) `
        -subj "/CN=SOAS Internal Services CA/O=SOC on a Stick" `
        -out $caCert 2>&1 | Out-Null
    if (-not (Test-Path $caCert)) {
        Write-Error "Failed to generate CA cert at $caCert"
        exit 1
    }
}

# ---- Per-service certs (server + client) -------------------------------------
foreach ($service in $services) {
    foreach ($kind in @("server", "client")) {
        $svcDir = Join-Path $root $service
        New-Item -ItemType Directory -Force -Path $svcDir | Out-Null

        $keyPath = Join-Path $svcDir "$kind.key"
        $crtPath = Join-Path $svcDir "$kind.crt"
        $csrPath = Join-Path $svcDir "$kind.csr"
        $extPath = Join-Path $svcDir "$kind.ext"

        # Skip if cert has > 30 days left.
        $healthy = $false
        if ((Test-Path $crtPath) -and -not $Force) {
            $endLine = (& $opensslExe x509 -in $crtPath -noout -enddate 2>&1) | Select-Object -First 1
            $notAfter = ($endLine -replace "^notAfter=", "").Trim()
            try {
                $expiry = [datetime]::ParseExact($notAfter, "MMM d HH:mm:ss yyyy 'GMT'", $null)
                if (($expiry - (Get-Date)).TotalDays -gt 30) { $healthy = $true }
            } catch {}
        }
        if ($healthy) {
            Write-Host "[mtls]   $service/$kind.crt healthy -- skipping."
            continue
        }

        Write-Host "[mtls]   issuing $service/$kind..."

        # Write the v3 extensions file (SAN + EKU per cert role).
        if ($kind -eq "server") {
            $extContent = "subjectAltName=DNS:$service,DNS:localhost`nextendedKeyUsage=serverAuth`nkeyUsage=digitalSignature,keyEncipherment"
        } else {
            $extContent = "extendedKeyUsage=clientAuth`nkeyUsage=digitalSignature"
        }
        Set-Content -Path $extPath -Value $extContent -Encoding Ascii

        & $opensslExe genrsa -out $keyPath 2048 2>&1 | Out-Null
        & $opensslExe req -new -key $keyPath `
            -subj "/CN=$service/O=SOC on a Stick/OU=$kind" `
            -out $csrPath 2>&1 | Out-Null
        & $opensslExe x509 -req -in $csrPath `
            -CA $caCert -CAkey $caKey -CAcreateserial `
            -out $crtPath -days $days -sha256 `
            -extfile $extPath 2>&1 | Out-Null

        if (-not (Test-Path $crtPath)) {
            Write-Error "Failed to issue $service/$kind cert"
            exit 1
        }

        Remove-Item $csrPath, $extPath -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "[mtls] Done. Certs at $root"

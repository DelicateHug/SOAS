#Requires -Version 5.1
# Stop SOAS PRECISELY. NEVER kill by image name (e.g. Stop-Process -Name node/python) —
# that would take down unrelated processes, including StudyPC itself. Target EXACT PIDs only:
#   -ProcessId : the PID StudyPC launched; we kill its whole TREE (taskkill /T -> children).
#   -Port      : fallback — the PID actually listening on the dev port (and its tree).
param([int]$ProcessId = 0, [int]$Port = 0)
$ErrorActionPreference = 'SilentlyContinue'

function Stop-Tree([int]$id) {
    if ($id -le 0) { return $false }
    if (-not (Get-Process -Id $id -ErrorAction SilentlyContinue)) { return $false }
    taskkill /PID $id /T /F | Out-Null      # by PID + child tree, never by name
    return $true
}

$killed = $false
if (Stop-Tree $ProcessId) { $killed = $true; Write-Host "Stopped PID tree $ProcessId" }
if ($Port -gt 0) {
    $owners = (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue).OwningProcess |
              Sort-Object -Unique
    foreach ($owner in $owners) {
        if (Stop-Tree ([int]$owner)) { $killed = $true; Write-Host "Stopped PID tree $owner on port $Port" }
    }
}
if (-not $killed) { Write-Host "SOAS: nothing to stop (no matching PID or port owner)." }

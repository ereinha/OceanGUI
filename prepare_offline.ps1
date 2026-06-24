# Build an OFFLINE install bundle (run on a machine WITH internet).
# Downloads all dependency wheels into vendor\wheels so the app can later be
# installed on an air-gapped computer from a flash drive.
#
# Examples:
#   .\prepare_offline.ps1
#   .\prepare_offline.ps1 --target windows64 --python-version 3.11
#
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition

$Python = $null
foreach ($cmd in @("py", "python")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { $Python = $cmd; break }
}
if (-not $Python) {
    Write-Error "Python not found. Install Python 3.8+ from python.org and re-run."
    exit 1
}

Write-Host "==> Downloading dependency wheels into vendor\wheels ..."
& $Python (Join-Path $RepoRoot "assets\prepare_offline.py") @args

Write-Host ""
Write-Host "==> Bundle ready. Copy the entire repository folder (including"
Write-Host "    vendor\wheels) onto the flash drive, then run install.bat on"
Write-Host "    the offline machine."

# Install script for the Ocean Spectrometer GUI (Windows / PowerShell).
# Creates a virtual environment, installs dependencies, generates the icon,
# and creates a desktop shortcut.
#
# Works ONLINE (installs from PyPI) or OFFLINE: if vendor\wheels contains a
# pre-downloaded bundle (see prepare_offline.ps1), dependencies are installed
# from it with no network access - ideal for air-gapped machines / flash-drive
# installs.
#
#   Right-click -> "Run with PowerShell", or:
#   powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $RepoRoot
$VenvDir = Join-Path $RepoRoot ".venv"
$WheelsDir = Join-Path $RepoRoot "vendor\wheels"

Write-Host "==> Ocean Spectrometer GUI installer"
Write-Host "    Repository: $RepoRoot"

# Find a Python launcher.
$Python = $null
foreach ($cmd in @("py", "python")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { $Python = $cmd; break }
}
if (-not $Python) {
    Write-Error "Python not found. Install Python 3.8+ from python.org and re-run."
    exit 1
}

Write-Host "==> Creating virtual environment (.venv)"
& $Python -m venv $VenvDir

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

# Detect an offline wheel bundle.
$Offline = (Test-Path $WheelsDir) -and ((Get-ChildItem -Path $WheelsDir -Filter *.whl -ErrorAction SilentlyContinue).Count -gt 0)

if ($Offline) {
    Write-Host "==> Offline bundle found in vendor\wheels - installing without internet"
    try { & $VenvPython -m pip install --no-index --find-links $WheelsDir --upgrade pip wheel | Out-Null }
    catch { Write-Host "    (pip/wheel not in bundle - using the version shipped with venv)" }
    Write-Host "==> Installing dependencies (offline)"
    & $VenvPython -m pip install --no-index --find-links $WheelsDir -r (Join-Path $RepoRoot "requirements.txt")
} else {
    Write-Host "==> Upgrading pip"
    & $VenvPython -m pip install --upgrade pip wheel | Out-Null
    Write-Host "==> Installing dependencies (from PyPI)"
    & $VenvPython -m pip install -r (Join-Path $RepoRoot "requirements.txt")
}

Write-Host "==> Ensuring save directory exists"
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "saved_data") | Out-Null

Write-Host "==> Generating application icon"
try { & $VenvPython (Join-Path $RepoRoot "assets\make_icon.py") } catch { Write-Host "    (icon generation skipped)" }

Write-Host "==> Creating desktop shortcut"
try { & $VenvPython (Join-Path $RepoRoot "assets\make_shortcut.py") } catch { Write-Host "    (shortcut creation skipped)" }

Write-Host ""
Write-Host "==> Done!"
Write-Host "    Launch with:  .\run.bat"
Write-Host "    Or from the 'Ocean Spectrometer GUI' desktop shortcut."

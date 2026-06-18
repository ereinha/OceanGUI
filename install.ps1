# Install script for the Ocean Spectrometer GUI (Windows / PowerShell).
# Creates a virtual environment, installs dependencies, generates the icon,
# and creates a desktop shortcut.
#
#   Right-click -> "Run with PowerShell", or:
#   powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $RepoRoot
$VenvDir = Join-Path $RepoRoot ".venv"

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

Write-Host "==> Upgrading pip"
& $VenvPython -m pip install --upgrade pip wheel | Out-Null

Write-Host "==> Installing dependencies"
& $VenvPython -m pip install -r (Join-Path $RepoRoot "requirements.txt")

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

# Build a SELF-CONTAINED app (Windows) that needs no Python on the target
# machine. Run on an ONLINE Windows machine; copy the resulting
# dist\OceanSpectrometerGUI folder to the air-gapped PC.
#
#   powershell -ExecutionPolicy Bypass -File build_standalone.ps1
#   powershell -ExecutionPolicy Bypass -File build_standalone.ps1 --onefile
#
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $RepoRoot
$BuildVenv = Join-Path $RepoRoot ".buildvenv"
$WheelsDir = Join-Path $RepoRoot "vendor\wheels"

$Python = $null
foreach ($cmd in @("py", "python")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { $Python = $cmd; break }
}
if (-not $Python) {
    Write-Error "Python not found. Install Python 3.8+ from python.org and re-run."
    exit 1
}

Write-Host "==> Creating build environment (.buildvenv)"
& $Python -m venv $BuildVenv
$VenvPython = Join-Path $BuildVenv "Scripts\python.exe"

$Offline = (Test-Path $WheelsDir) -and ((Get-ChildItem -Path $WheelsDir -Filter *.whl -ErrorAction SilentlyContinue).Count -gt 0)
if ($Offline) {
    Write-Host "==> Installing build deps from vendor\wheels (offline)"
    & $VenvPython -m pip install --no-index --find-links $WheelsDir -r requirements.txt -r build-requirements.txt
} else {
    Write-Host "==> Installing build deps (from PyPI)"
    & $VenvPython -m pip install --upgrade pip wheel | Out-Null
    & $VenvPython -m pip install -r requirements.txt -r build-requirements.txt
}

Write-Host "==> Building self-contained app"
& $VenvPython (Join-Path $RepoRoot "assets\build_standalone.py") @args

#!/usr/bin/env bash
#
# Install script for the Ocean Spectrometer GUI (Linux / macOS).
# Creates a virtual environment, installs dependencies, generates the icon,
# configures udev rules for seabreeze, and creates a desktop shortcut.
#
# Works ONLINE (installs from PyPI) or OFFLINE: if vendor/wheels/ contains a
# pre-downloaded bundle (see prepare_offline.sh), dependencies are installed
# from it with no network access - ideal for air-gapped machines / flash-drive
# installs.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-python3}"
VENV_DIR="$REPO_ROOT/.venv"
WHEELS_DIR="$REPO_ROOT/vendor/wheels"

echo "==> Ocean Spectrometer GUI installer"
echo "    Repository: $REPO_ROOT"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "ERROR: '$PYTHON' not found. Install Python 3.8+ and re-run." >&2
    exit 1
fi

echo "==> Creating virtual environment (.venv)"
"$PYTHON" -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Detect an offline wheel bundle.
OFFLINE=0
if ls "$WHEELS_DIR"/*.whl >/dev/null 2>&1; then
    OFFLINE=1
fi

if [ "$OFFLINE" -eq 1 ]; then
    echo "==> Offline bundle found in vendor/wheels - installing without internet"
    python -m pip install --no-index --find-links "$WHEELS_DIR" --upgrade pip wheel \
        || echo "    (pip/wheel not in bundle - using the version shipped with venv)"
    echo "==> Installing dependencies (offline)"
    python -m pip install --no-index --find-links "$WHEELS_DIR" -r "$REPO_ROOT/requirements.txt"
else
    echo "==> Upgrading pip"
    python -m pip install --upgrade pip wheel >/dev/null
    echo "==> Installing dependencies (from PyPI)"
    python -m pip install -r "$REPO_ROOT/requirements.txt"
fi

echo "==> Ensuring save directory exists"
mkdir -p "$REPO_ROOT/saved_data"

echo "==> Generating application icon"
python "$REPO_ROOT/assets/make_icon.py" || echo "    (icon generation skipped)"

# seabreeze on Linux needs udev rules to access the USB device.
if command -v seabreeze_os_setup >/dev/null 2>&1; then
    echo "==> Configuring seabreeze udev rules (may prompt for sudo)"
    seabreeze_os_setup || echo "    (seabreeze_os_setup skipped/failed - run manually if using hardware)"
fi

echo "==> Creating desktop shortcut"
python "$REPO_ROOT/assets/make_shortcut.py" || echo "    (shortcut creation skipped)"

echo ""
echo "==> Done!"
echo "    Launch with:  ./run.sh"
echo "    Or from the desktop shortcut: 'Ocean Spectrometer GUI'"

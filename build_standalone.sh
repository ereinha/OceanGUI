#!/usr/bin/env bash
#
# Build a SELF-CONTAINED app (Linux / macOS) that needs no Python on the
# target machine. Run this on an ONLINE machine of the SAME OS as the target;
# copy the resulting dist/OceanSpectrometerGUI folder to the air-gapped PC.
#
#   ./build_standalone.sh             # one-folder build (recommended)
#   ./build_standalone.sh --onefile   # single executable file
#
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-python3}"
BUILD_VENV="$REPO_ROOT/.buildvenv"
WHEELS_DIR="$REPO_ROOT/vendor/wheels"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "ERROR: '$PYTHON' not found. Install Python 3.8+ and re-run." >&2
    exit 1
fi

echo "==> Creating build environment (.buildvenv)"
"$PYTHON" -m venv "$BUILD_VENV"
# shellcheck disable=SC1091
source "$BUILD_VENV/bin/activate"

# Use the offline wheel bundle if present, otherwise PyPI.
if ls "$WHEELS_DIR"/*.whl >/dev/null 2>&1; then
    echo "==> Installing build deps from vendor/wheels (offline)"
    python -m pip install --no-index --find-links "$WHEELS_DIR" \
        -r requirements.txt -r build-requirements.txt
else
    echo "==> Installing build deps (from PyPI)"
    python -m pip install --upgrade pip wheel >/dev/null
    python -m pip install -r requirements.txt -r build-requirements.txt
fi

echo "==> Building self-contained app"
python "$REPO_ROOT/assets/build_standalone.py" "$@"

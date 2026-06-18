#!/usr/bin/env bash
# Launch the Ocean Spectrometer GUI (Linux / macOS).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

if [ ! -d "$REPO_ROOT/.venv" ]; then
    echo "Virtual environment not found. Run ./install.sh first." >&2
    exit 1
fi
# shellcheck disable=SC1091
source "$REPO_ROOT/.venv/bin/activate"
exec python -m ocean_gui.main

#!/usr/bin/env bash
#
# Build an OFFLINE install bundle (run on a machine WITH internet).
# Downloads all dependency wheels into vendor/wheels/ so the app can later be
# installed on an air-gapped computer from a flash drive.
#
# Examples:
#   ./prepare_offline.sh                                  # for THIS machine
#   ./prepare_offline.sh --target windows64 --python-version 3.11
#   ./prepare_offline.sh --target linux64   --python-version 3.11
#
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "ERROR: '$PYTHON' not found. Install Python 3.8+ and re-run." >&2
    exit 1
fi

echo "==> Downloading dependency wheels into vendor/wheels ..."
"$PYTHON" -m pip --version >/dev/null 2>&1 || {
    echo "ERROR: pip is not available for $PYTHON." >&2; exit 1; }
"$PYTHON" "$REPO_ROOT/assets/prepare_offline.py" "$@"

echo ""
echo "==> Bundle ready. Copy the entire '$(basename "$REPO_ROOT")' folder"
echo "    (including vendor/wheels) onto the flash drive, then run install.sh"
echo "    / install.bat on the offline machine."

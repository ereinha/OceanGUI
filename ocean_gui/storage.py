import csv
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np


def _base_dir() -> Path:
    """Folder that ``saved_data`` lives next to.

    For a normal source checkout this is the repository root. For a frozen
    standalone build (PyInstaller) it is the folder containing the executable,
    so output is written beside the app (writable on a flash drive) rather
    than into the read-only bundle.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


REPO_ROOT = _base_dir()
DEFAULT_SAVE_DIR = REPO_ROOT / "saved_data"


def sanitize_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name.strip("._") or "run"


def run_directory(name: str, save_dir: Path = DEFAULT_SAVE_DIR) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(save_dir) / f"{sanitize_name(name)}_{stamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_csv(
    path: Path,
    single_time_ms: float,
    wavelengths: np.ndarray,
    all_intensities: np.ndarray,
    average: np.ndarray,
    std: np.ndarray,
    metadata: dict = None,
) -> Path:
    """Write the spectra to CSV.

    ``metadata`` is an optional dict of extra ``# key,value`` header lines
    (e.g. measurement mode, corrections, smoothing, dark/reference state).
    """
    n_integrations = all_intensities.shape[0]
    with open(path, "w", newline="") as fh:
        fh.write(f"# single_integration_time_ms,{single_time_ms}\n")
        fh.write(f"# n_integrations,{n_integrations}\n")
        for key, value in (metadata or {}).items():
            fh.write(f"# {key},{value}\n")
        writer = csv.writer(fh)
        header = ["wavelength_nm"]
        header += [f"integration_{i + 1}" for i in range(n_integrations)]
        header += ["average", "std"]
        writer.writerow(header)
        for j in range(wavelengths.size):
            row = [f"{wavelengths[j]:.4f}"]
            row += [f"{all_intensities[i, j]:.4f}" for i in range(n_integrations)]
            row += [f"{average[j]:.4f}", f"{std[j]:.4f}"]
            writer.writerow(row)
    return path

"""Create a desktop shortcut for the GUI on Linux or Windows.

Run after the virtual environment has been created.  It uses the venv's
Python interpreter so the shortcut launches the app with all dependencies
available.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ICON_PNG = REPO_ROOT / "assets" / "icon.png"
ICON_ICO = REPO_ROOT / "assets" / "icon.ico"
APP_NAME = "Ocean Spectrometer GUI"


def _venv_python() -> Path:
    if os.name == "nt":
        py = REPO_ROOT / ".venv" / "Scripts" / "pythonw.exe"
        if not py.exists():
            py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        py = REPO_ROOT / ".venv" / "bin" / "python"
    return py if py.exists() else Path(sys.executable)


def _desktop_dir() -> Path:
    home = Path.home()
    for candidate in (home / "Desktop", home / "Bureau", home / "Schreibtisch"):
        if candidate.exists():
            return candidate
    return home / "Desktop"


def create_linux_shortcut() -> Path:
    python = _venv_python()
    entry = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        f"Name={APP_NAME}\n"
        "Comment=Interface with Ocean spectrometers via seabreeze\n"
        f"Exec={python} -m ocean_gui.main\n"
        f"Path={REPO_ROOT}\n"
        f"Icon={ICON_PNG}\n"
        "Terminal=false\n"
        "Categories=Science;Education;\n"
    )

    targets = []
    desktop = _desktop_dir()
    desktop.mkdir(parents=True, exist_ok=True)
    desktop_file = desktop / "ocean-spectrometer-gui.desktop"
    desktop_file.write_text(entry)
    os.chmod(desktop_file, 0o755)
    targets.append(desktop_file)

    # Also register in the applications menu when possible.
    apps_dir = Path.home() / ".local" / "share" / "applications"
    try:
        apps_dir.mkdir(parents=True, exist_ok=True)
        menu_file = apps_dir / "ocean-spectrometer-gui.desktop"
        menu_file.write_text(entry)
        os.chmod(menu_file, 0o755)
        targets.append(menu_file)
    except Exception:
        pass

    print(f"Created Linux shortcut(s): {', '.join(str(t) for t in targets)}")
    return desktop_file


def create_windows_shortcut() -> Path:
    # Build the .lnk via the Windows Script Host COM object.
    import subprocess

    python = _venv_python()
    desktop = _desktop_dir()
    desktop.mkdir(parents=True, exist_ok=True)
    lnk = desktop / f"{APP_NAME}.lnk"
    icon = ICON_ICO if ICON_ICO.exists() else ICON_PNG

    ps = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{lnk}')
$s.TargetPath = '{python}'
$s.Arguments = '-m ocean_gui.main'
$s.WorkingDirectory = '{REPO_ROOT}'
$s.IconLocation = '{icon}'
$s.Description = 'Interface with Ocean spectrometers via seabreeze'
$s.Save()
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        check=True,
    )
    print(f"Created Windows shortcut: {lnk}")
    return lnk


def main() -> int:
    try:
        if os.name == "nt":
            create_windows_shortcut()
        else:
            create_linux_shortcut()
    except Exception as exc:
        print(f"Warning: could not create desktop shortcut: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

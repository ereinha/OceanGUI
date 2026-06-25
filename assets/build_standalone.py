import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "OceanSpectrometerGUI"
ENTRY = REPO_ROOT / "standalone_entry.py"


def _icon_path() -> Path | None:
    """Return the platform-appropriate icon, or None if unavailable."""
    if sys.platform.startswith("win"):
        ico = REPO_ROOT / "assets" / "icon.ico"
        return ico if ico.exists() else None
    if sys.platform == "darwin":
        icns = REPO_ROOT / "assets" / "icon.icns"
        return icns if icns.exists() else None
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--onefile", action="store_true",
                    help="produce a single executable file instead of a folder")
    args = ap.parse_args()

    try:
        import PyInstaller
    except Exception:
        print("PyInstaller is not installed. Install it with:\n"
              "    python -m pip install pyinstaller", file=sys.stderr)
        return 1

    try:
        subprocess.run([sys.executable, str(REPO_ROOT / "assets" / "make_icon.py")],
                       check=False)
    except Exception:
        pass

    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--name", APP_NAME,
        "--windowed",
        "--paths", str(REPO_ROOT),
        "--collect-all", "seabreeze",
        "--hidden-import", "PyQt5.QtNetwork",
        "--distpath", str(REPO_ROOT / "dist"),
        "--workpath", str(REPO_ROOT / "build"),
        "--specpath", str(REPO_ROOT / "build"),
    ]
    if args.onefile:
        cmd.append("--onefile")
    icon = _icon_path()
    if icon is not None:
        cmd += ["--icon", str(icon)]
    cmd.append(str(ENTRY))

    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"\nERROR: PyInstaller build failed ({exc.returncode}).", file=sys.stderr)
        return exc.returncode

    out = REPO_ROOT / "dist" / (APP_NAME if not args.onefile else "")
    print(f"\nBuild complete. Distributable in: {REPO_ROOT / 'dist'}")
    print("Copy that folder onto the flash drive and run the "
          f"'{APP_NAME}' executable on the offline machine - no Python needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = REPO_ROOT / "vendor" / "wheels"
REQUIREMENTS = REPO_ROOT / "requirements.txt"

# Convenience presets -> the platform tags pip should accept. Several tags are
# listed per target because projects publish wheels under different manylinux /
# macOS tags; pip picks the best match available for each package.
TARGET_PLATFORMS = {
    "windows64": ["win_amd64"],
    "linux64": [
        "manylinux2014_x86_64",
        "manylinux_2_17_x86_64",
        "manylinux_2_28_x86_64",
        "manylinux1_x86_64",
    ],
    "macos-intel": ["macosx_10_9_x86_64", "macosx_11_0_x86_64"],
    "macos-arm": ["macosx_11_0_arm64", "macosx_12_0_arm64"],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=sorted(TARGET_PLATFORMS),
                    help="cross-platform preset (default: current machine)")
    ap.add_argument("--platform", action="append", metavar="TAG",
                    help="explicit pip platform tag (repeatable); advanced")
    ap.add_argument("--python-version", metavar="X.Y",
                    help="target Python version, e.g. 3.11 (required with --target)")
    ap.add_argument("--dest", default=str(DEFAULT_DEST),
                    help="output directory (default: vendor/wheels)")
    args = ap.parse_args()

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)

    platforms = list(args.platform or [])
    if args.target:
        platforms += TARGET_PLATFORMS[args.target]

    cmd = [sys.executable, "-m", "pip", "download",
           "-r", str(REQUIREMENTS), "-d", str(dest)]

    if platforms:
        # Cross-platform download: wheels only (no sdists, which would need a
        # compiler on the offline box), and an explicit interpreter.
        if not args.python_version:
            ap.error("--python-version is required when using --target/--platform")
        cmd += ["--only-binary=:all:", "--python-version", args.python_version,
                "--implementation", "cp"]
        for tag in platforms:
            cmd += ["--platform", tag]

    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"\nERROR: pip download failed ({exc.returncode}).", file=sys.stderr)
        if platforms:
            print("Cross-platform downloads need binary wheels for every "
                  "dependency; try running this on the target OS instead.",
                  file=sys.stderr)
        return exc.returncode

    files = sorted(p.name for p in dest.iterdir() if p.is_file() and p.name != "MANIFEST.txt")
    (dest / "MANIFEST.txt").write_text("\n".join(files) + "\n")
    print(f"\nDownloaded {len(files)} file(s) into {dest}")
    print("Now copy the whole repository folder onto the flash drive and run "
          "the installer on the offline machine.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

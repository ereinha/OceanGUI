# vendor/ — offline install bundle

`vendor/wheels/` holds pre-downloaded Python wheels so the application can be
installed on a computer **with no internet connection** (e.g. copied from a
flash drive).

## How it works

1. **On a machine with internet**, from the repo root:

   ```bash
   ./prepare_offline.sh            # Linux/macOS, for THIS machine
   # or
   powershell -ExecutionPolicy Bypass -File prepare_offline.ps1   # Windows
   ```

   This fills `vendor/wheels/` with every dependency wheel (numpy, matplotlib,
   PyQt5, seabreeze, Pillow and their transitive deps).

2. **Copy the entire repository folder** (including `vendor/wheels/`) onto the
   flash drive.

3. **On the offline machine**, run the normal installer:

   ```bash
   ./install.sh        # or install.bat on Windows
   ```

   It auto-detects `vendor/wheels/` and installs with `pip --no-index`, so no
   network access is needed.

## Matching the target platform

Wheels are specific to OS, CPU architecture and Python version. The simplest
reliable approach is to run `prepare_offline` on a machine that matches the
offline target (same OS/arch and a close Python version).

To build a bundle for a *different* platform, pass a preset and the target
Python version:

```bash
python assets/prepare_offline.py --target windows64   --python-version 3.11
python assets/prepare_offline.py --target linux64     --python-version 3.11
python assets/prepare_offline.py --target macos-arm   --python-version 3.11
```

> Note: the offline machine still needs **Python itself** installed. Put the
> matching Python installer on the flash drive too if the target may not have
> it. Cross-platform wheel downloads only work when every dependency publishes
> a binary wheel for that platform; otherwise build the bundle on the target OS.

# Ocean Spectrometer GUI

A cross-platform (Windows + Linux) desktop GUI for acquiring spectra from
**Ocean Optics / Ocean Insight** spectrometers using the
[python-seabreeze](https://github.com/ap--/python-seabreeze) backend.

If no spectrometer (or backend) is present, the app automatically runs in
**simulation mode** so every feature can be tried offline.

---

## Features

- **Live device panel**: a perpetual connection indicator (green = connected,
  red = disconnected), a drop-down of available devices, and **Connect**
  (also used to change device), **Reconnect**, and **Refresh** buttons. The
  status auto-refreshes every 2 s.
- **Side-by-side plots**: the current integration (left) and the running
  average integration (right).
- **Paper-quality figures**: descriptive axis labels with units and *no* plot
  title, inward tick marks on all four sides, data drawn edge-to-edge so ticks
  reach the borders, and **300 DPI** output with a publication-friendly
  font-to-figure ratio.
- **Placeholder axes**: example dummy axes are shown until real data arrives.
- **Two run modes** (mutually exclusive):
  - *Number of integrations* — run an exact count, or
  - *Total integration time* — run for a total exposure (count = total ÷ single).
- **Single integration time** and **down time between integrations** settings.
- **Uncertainty toggles**: 1σ / 2σ **bars** and 1σ / 2σ **bands** on the average.
- **Required run name** before a run can start.
- **Automatic outputs** on completion (into `saved_data/<name>_<timestamp>/`):
  - `*_data.csv` — single integration time, wavelengths and intensities.
  - `*_total.png` — picture of the total/average integration.
  - `*_average.png` — average integration, no bars/bands.
  - `*_average_overlay.png` — average in **red** over each individual
    integration in **grey**.
- **Save total figure (with bars/bands)** button — saves the average plot with
  the currently-enabled uncertainty overlays.
- **Interrupt** button — stops an in-progress run after an *"Are you sure?"*
  confirmation; integrations collected so far are still saved.
- **In-app Help menu** (also `F1`).
- **Desktop shortcut** with a generated icon (white background, black border,
  red spectrum line), created by the installer.

---

## Installation

### Linux / macOS

```bash
git clone <this-repo> OceanGUI
cd OceanGUI
./install.sh
```

### Windows

Double-click `install.bat`, **or** from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

The installer will:

1. create a `.venv` virtual environment in the repo,
2. install all dependencies from `requirements.txt`,
3. generate the application icon,
4. (Linux) configure seabreeze udev rules via `seabreeze_os_setup`,
5. create a **desktop shortcut**.

### Offline / flash-drive install (no internet on the target machine)

To install on an **air-gapped computer**, pre-download the dependencies on a
machine that *has* internet, then carry everything on a flash drive:

1. **On an online machine** (ideally the same OS/architecture as the target):

   ```bash
   ./prepare_offline.sh          # Linux/macOS
   # or:  powershell -ExecutionPolicy Bypass -File prepare_offline.ps1   (Windows)
   ```

   This downloads every wheel into `vendor/wheels/`. To build a bundle for a
   different platform, e.g.:

   ```bash
   python assets/prepare_offline.py --target windows64 --python-version 3.11
   ```

2. **Copy the whole `OceanGUI` folder** (including `vendor/wheels/`) onto the
   flash drive and over to the offline machine.

3. **On the offline machine**, run the normal installer:

   ```bash
   ./install.sh        # or install.bat on Windows
   ```

   It auto-detects `vendor/wheels/` and installs with `pip --no-index`, so **no
   network access is used**. (The target machine still needs Python itself
   installed — put the Python installer on the drive too if needed.)

See [vendor/README.md](vendor/README.md) for details.

---

## Running

- **Desktop shortcut**: *Ocean Spectrometer GUI*
- **Linux / macOS**: `./run.sh`
- **Windows**: `run.bat`
- **Directly**: `python -m ocean_gui.main` (with the venv active)

---

## Usage

1. Pick a device from the **Available devices** drop-down and press
   **Connect** (or just **Start** — it connects to the selection automatically).
   The indicator turns green when connected. Use **Reconnect** after a
   replug, or **Refresh** to re-scan the bus.
2. Set the **single integration time**, **down time**, and pick a **run mode**.
3. Enter a **run name** (required — Start stays disabled until you do).
4. Press **Start**. Plots update live; toggle 1σ/2σ bars and bands anytime.
   Press **Interrupt** to stop early (with confirmation) — partial data is kept.
5. On completion the CSV and figures are saved automatically. Use
   **Save total figure (with bars/bands)** for a copy with your chosen overlays.

All output is stored inside the repository under `saved_data/`.

---

## Hardware notes (seabreeze)

- On **Linux**, USB access requires udev rules. The installer runs
  `seabreeze_os_setup`; if you skipped it, run that command once manually and
  replug the device.
- On **Windows**, you may need the device driver from Ocean Insight / a
  WinUSB/libusb driver (e.g. via Zadig) for some models.
- See the
  [seabreeze quickstart](https://github.com/ap--/python-seabreeze/blob/main/docs/source/quickstart.rst).

---

## Project layout

```
OceanGUI/
├── ocean_gui/
│   ├── main.py          # entry point
│   ├── gui.py           # PyQt5 main window
│   ├── acquisition.py   # settings model + background acquisition thread
│   ├── spectrometer.py  # seabreeze wrapper + simulation fallback
│   ├── plotting.py      # shared matplotlib rendering
│   └── storage.py       # CSV / figure saving
├── assets/
│   ├── make_icon.py       # generates the app icon
│   ├── make_shortcut.py   # creates the desktop shortcut (Linux/Windows)
│   └── prepare_offline.py # downloads wheels for an offline bundle
├── vendor/wheels/       # offline dependency bundle (built on demand)
├── saved_data/          # acquisition output (inside the repo)
├── install.sh / run.sh / prepare_offline.sh          # Linux / macOS
├── install.ps1 / install.bat / run.bat / prepare_offline.ps1   # Windows
└── requirements.txt
```

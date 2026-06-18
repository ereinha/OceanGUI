# Ocean Spectrometer GUI

A cross-platform (Windows + Linux) desktop GUI for acquiring spectra from
**Ocean Optics / Ocean Insight** spectrometers using the
[python-seabreeze](https://github.com/ap--/python-seabreeze) backend.

If no spectrometer (or backend) is present, the app automatically runs in
**simulation mode** so every feature can be tried offline.

---

## Features

- **Side-by-side plots**: the current integration (left) and the running
  average integration (right).
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

---

## Running

- **Desktop shortcut**: *Ocean Spectrometer GUI*
- **Linux / macOS**: `./run.sh`
- **Windows**: `run.bat`
- **Directly**: `python -m ocean_gui.main` (with the venv active)

---

## Usage

1. Press **Connect** (or just **Start** — it connects automatically).
2. Set the **single integration time**, **down time**, and pick a **run mode**.
3. Enter a **run name** (required — Start stays disabled until you do).
4. Press **Start**. Plots update live; toggle 1σ/2σ bars and bands anytime.
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
│   ├── make_icon.py     # generates the app icon
│   └── make_shortcut.py # creates the desktop shortcut (Linux/Windows)
├── saved_data/          # acquisition output (inside the repo)
├── install.sh / run.sh           # Linux / macOS
├── install.ps1 / install.bat / run.bat   # Windows
└── requirements.txt
```

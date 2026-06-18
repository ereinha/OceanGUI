import sys
from pathlib import Path
from typing import Optional

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtGui, QtWidgets

from . import plotting, storage
from .acquisition import AcquisitionSettings, AcquisitionWorker, RunMode
from .spectrometer import SpectrometerInterface, backend_status

HELP_TEXT = """\
<h2>Ocean Spectrometer GUI - Help</h2>

<h3>1. Connect</h3>
<p>Press <b>Connect</b> to open the first available Ocean spectrometer via the
seabreeze backend. If no device or backend is found, the app runs in
<b>simulation mode</b> so you can still try every feature.</p>

<h3>2. Settings</h3>
<ul>
<li><b>Single integration time (ms)</b> - exposure time of one spectrum.</li>
<li><b>Down time (ms)</b> - pause inserted between integrations.</li>
<li><b>Run mode</b> - choose <i>one</i>:
  <ul>
  <li><b>Number of integrations</b> - run an exact count, or</li>
  <li><b>Total integration time</b> - run for a total exposure; the count is
      total / single time.</li>
  </ul>
  You cannot use both at once.</li>
</ul>

<h3>3. Filename</h3>
<p>A <b>run name is required</b> before <b>Start</b> is enabled. Output is
written to <code>saved_data/&lt;name&gt;_&lt;timestamp&gt;/</code> inside the
repository.</p>

<h3>4. Plots</h3>
<p>Left shows the <b>current</b> integration; right shows the running
<b>average</b>. Example dummy axes are shown until data arrives. Use the
checkboxes to toggle <b>1σ / 2σ uncertainty bars and bands</b> on the average.</p>

<h3>5. Saved files</h3>
<p>When a run finishes these are written automatically:</p>
<ul>
<li><code>*_data.csv</code> - integration time, wavelengths and intensities.</li>
<li><code>*_total.png</code> - picture of the total/average integration.</li>
<li><code>*_average.png</code> - average integration, no bars/bands.</li>
<li><code>*_average_overlay.png</code> - average in red over each individual
    integration in grey.</li>
</ul>
<p>The <b>Save total figure (with bars/bands)</b> button writes the average plot
with whatever uncertainty toggles are currently enabled.</p>
"""


class SpectrometerGUI(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Ocean Spectrometer GUI")
        self.resize(1180, 720)

        self.spec: Optional[SpectrometerInterface] = None
        self.worker: Optional[AcquisitionWorker] = None
        self.run_dir: Optional[Path] = None

        self._wavelengths: Optional[np.ndarray] = None
        self._all_intensities: Optional[np.ndarray] = None
        self._average: Optional[np.ndarray] = None
        self._std: Optional[np.ndarray] = None

        self._build_ui()
        self._update_status(f"Backend: {backend_status()}")
        self._refresh_start_enabled()

    def _build_ui(self) -> None:
        self._build_menu()

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        layout.addWidget(self._build_controls(), 0)
        layout.addWidget(self._build_plots(), 1)

        self.status = self.statusBar()

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        help_menu = menubar.addMenu("&Help")
        help_action = QtWidgets.QAction("Help / How to use", self)
        help_action.setShortcut("F1")
        help_action.triggered.connect(self._show_help)
        help_menu.addAction(help_action)
        about_action = QtWidgets.QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_controls(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setFixedWidth(320)
        v = QtWidgets.QVBoxLayout(panel)

        conn_box = QtWidgets.QGroupBox("Device")
        cb = QtWidgets.QVBoxLayout(conn_box)
        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.clicked.connect(self._connect)
        self.device_label = QtWidgets.QLabel("Not connected")
        self.device_label.setWordWrap(True)
        cb.addWidget(self.connect_btn)
        cb.addWidget(self.device_label)
        v.addWidget(conn_box)

        s_box = QtWidgets.QGroupBox("Acquisition settings")
        form = QtWidgets.QFormLayout(s_box)

        self.single_time = QtWidgets.QDoubleSpinBox()
        self.single_time.setRange(0.001, 60000.0)
        self.single_time.setValue(100.0)
        self.single_time.setSuffix(" ms")
        form.addRow("Single integration time:", self.single_time)

        self.down_time = QtWidgets.QDoubleSpinBox()
        self.down_time.setRange(0.0, 600000.0)
        self.down_time.setValue(0.0)
        self.down_time.setSuffix(" ms")
        form.addRow("Down time between:", self.down_time)

        self.mode_number = QtWidgets.QRadioButton("Number of integrations")
        self.mode_total = QtWidgets.QRadioButton("Total integration time")
        self.mode_number.setChecked(True)
        self.mode_number.toggled.connect(self._update_mode_enabled)
        form.addRow(self.mode_number)

        self.n_integrations = QtWidgets.QSpinBox()
        self.n_integrations.setRange(1, 1_000_000)
        self.n_integrations.setValue(10)
        form.addRow("  count:", self.n_integrations)

        form.addRow(self.mode_total)
        self.total_time = QtWidgets.QDoubleSpinBox()
        self.total_time.setRange(0.001, 86_400_000.0)
        self.total_time.setValue(1000.0)
        self.total_time.setSuffix(" ms")
        form.addRow("  total:", self.total_time)
        v.addWidget(s_box)

        f_box = QtWidgets.QGroupBox("Run name (required)")
        fb = QtWidgets.QVBoxLayout(f_box)
        self.filename = QtWidgets.QLineEdit()
        self.filename.setPlaceholderText("e.g. sample_A")
        self.filename.textChanged.connect(self._refresh_start_enabled)
        fb.addWidget(self.filename)
        v.addWidget(f_box)

        u_box = QtWidgets.QGroupBox("Uncertainty (average plot)")
        ub = QtWidgets.QGridLayout(u_box)
        self.cb_bars1 = QtWidgets.QCheckBox("1σ bars")
        self.cb_bars2 = QtWidgets.QCheckBox("2σ bars")
        self.cb_band1 = QtWidgets.QCheckBox("1σ band")
        self.cb_band2 = QtWidgets.QCheckBox("2σ band")
        for w in (self.cb_bars1, self.cb_bars2, self.cb_band1, self.cb_band2):
            w.toggled.connect(self._redraw_average)
        self.cb_bars1.toggled.connect(lambda on: on and self.cb_bars2.setChecked(False))
        self.cb_bars2.toggled.connect(lambda on: on and self.cb_bars1.setChecked(False))
        ub.addWidget(self.cb_bars1, 0, 0)
        ub.addWidget(self.cb_bars2, 0, 1)
        ub.addWidget(self.cb_band1, 1, 0)
        ub.addWidget(self.cb_band2, 1, 1)
        v.addWidget(u_box)

        self.start_btn = QtWidgets.QPushButton("Start")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        self.save_btn = QtWidgets.QPushButton("Save total figure (with bars/bands)")
        self.save_btn.clicked.connect(self._save_total_with_uncertainty)
        self.save_btn.setEnabled(False)
        v.addWidget(self.start_btn)
        v.addWidget(self.stop_btn)
        v.addWidget(self.save_btn)

        self.progress = QtWidgets.QProgressBar()
        v.addWidget(self.progress)

        v.addStretch(1)
        return panel

    def _build_plots(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(panel)

        self.fig_current = Figure(figsize=(5, 4), tight_layout=True)
        self.ax_current = self.fig_current.add_subplot(111)
        self.canvas_current = FigureCanvas(self.fig_current)

        self.fig_avg = Figure(figsize=(5, 4), tight_layout=True)
        self.ax_avg = self.fig_avg.add_subplot(111)
        self.canvas_avg = FigureCanvas(self.fig_avg)

        h.addWidget(self.canvas_current)
        h.addWidget(self.canvas_avg)

        plotting.draw_placeholder(self.ax_current, "Current integration")
        plotting.draw_placeholder(self.ax_avg, "Average integration")
        self.canvas_current.draw()
        self.canvas_avg.draw()
        return panel

    def _update_mode_enabled(self) -> None:
        is_number = self.mode_number.isChecked()
        self.n_integrations.setEnabled(is_number)
        self.total_time.setEnabled(not is_number)

    def _refresh_start_enabled(self) -> None:
        has_name = bool(self.filename.text().strip())
        running = self.worker is not None and self.worker.isRunning()
        self.start_btn.setEnabled(has_name and not running)

    def _update_status(self, msg: str) -> None:
        self.statusBar().showMessage(msg)

    def _gather_settings(self) -> AcquisitionSettings:
        return AcquisitionSettings(
            single_time_ms=self.single_time.value(),
            down_time_ms=self.down_time.value(),
            mode=RunMode.NUMBER if self.mode_number.isChecked() else RunMode.TOTAL_TIME,
            n_integrations=self.n_integrations.value(),
            total_time_ms=self.total_time.value(),
        )

    def _connect(self) -> None:
        try:
            self.spec = SpectrometerInterface.open_first(allow_simulation=True)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Connection failed", str(exc))
            return
        mode = "SIMULATION" if self.spec.simulated else "HARDWARE"
        self.device_label.setText(
            f"[{mode}]\n{self.spec.model}\nSN: {self.spec.serial_number}"
        )
        self._update_status(f"Connected ({mode}).")

    def _start(self) -> None:
        if self.spec is None:
            self._connect()
            if self.spec is None:
                return

        settings = self._gather_settings()
        err = settings.validate()
        if err:
            QtWidgets.QMessageBox.warning(self, "Invalid settings", err)
            return

        name = self.filename.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Run name required",
                                          "Please enter a run name before starting.")
            return

        try:
            self.run_dir = storage.run_directory(name)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Cannot create folder", str(exc))
            return

        self._run_name = storage.sanitize_name(name)
        self._run_single_ms = settings.single_time_ms
        self.progress.setMaximum(settings.integrations_count())
        self.progress.setValue(0)
        plotting.draw_placeholder(self.ax_current, "Current integration")
        plotting.draw_placeholder(self.ax_avg, "Average integration")
        self.canvas_current.draw()
        self.canvas_avg.draw()

        self.worker = AcquisitionWorker(self.spec, settings)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.save_btn.setEnabled(False)
        self._update_status(f"Running -> {self.run_dir}")

    def _stop(self) -> None:
        if self.worker is not None:
            self.worker.abort()
            self._update_status("Stopping after current integration...")

    def _on_progress(self, index, total, wavelengths, intensities, avg, std) -> None:
        self._wavelengths = wavelengths
        self._average = avg
        self._std = std
        self.progress.setValue(index)
        plotting.draw_current(self.ax_current, wavelengths, intensities, index, total)
        self.canvas_current.draw()
        self._redraw_average()

    def _on_finished(self, wavelengths, all_intensities, avg, std) -> None:
        self._wavelengths = wavelengths
        self._all_intensities = all_intensities
        self._average = avg
        self._std = std
        self._redraw_average()
        self.stop_btn.setEnabled(False)
        self.save_btn.setEnabled(True)
        self._refresh_start_enabled()

        try:
            self._autosave()
            self._update_status(f"Done. {all_intensities.shape[0]} integrations saved to {self.run_dir}")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(exc))
        finally:
            self.worker = None

    def _on_failed(self, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, "Acquisition failed", message)
        self.stop_btn.setEnabled(False)
        self.worker = None
        self._refresh_start_enabled()
        self._update_status("Acquisition failed.")

    def _redraw_average(self) -> None:
        if self._wavelengths is None or self._average is None:
            return
        plotting.draw_average(
            self.ax_avg, self._wavelengths, self._average, self._std,
            bars_1sigma=self.cb_bars1.isChecked(),
            bars_2sigma=self.cb_bars2.isChecked(),
            band_1sigma=self.cb_band1.isChecked(),
            band_2sigma=self.cb_band2.isChecked(),
        )
        self.canvas_avg.draw()

    def _autosave(self) -> None:
        assert self.run_dir is not None
        base = self.run_dir / self._run_name
        wl = self._wavelengths
        alli = self._all_intensities
        avg = self._average
        std = self._std

        storage.save_csv(Path(f"{base}_data.csv"), self._run_single_ms, wl, alli, avg, std)

        fig = Figure(figsize=(6, 4.5), tight_layout=True)
        ax = fig.add_subplot(111)
        plotting.draw_average(ax, wl, avg, std, title="Total / average integration")
        fig.savefig(f"{base}_total.png", dpi=150)

        fig = Figure(figsize=(6, 4.5), tight_layout=True)
        ax = fig.add_subplot(111)
        plotting.draw_average(ax, wl, avg, std, title="Average integration")
        fig.savefig(f"{base}_average.png", dpi=150)

        fig = Figure(figsize=(6, 4.5), tight_layout=True)
        ax = fig.add_subplot(111)
        plotting.draw_overlay(ax, wl, alli, avg)
        fig.savefig(f"{base}_average_overlay.png", dpi=150)

    def _save_total_with_uncertainty(self) -> None:
        if self.run_dir is None or self._average is None:
            return
        base = self.run_dir / self._run_name
        fig = Figure(figsize=(6, 4.5), tight_layout=True)
        ax = fig.add_subplot(111)
        plotting.draw_average(
            ax, self._wavelengths, self._average, self._std,
            bars_1sigma=self.cb_bars1.isChecked(),
            bars_2sigma=self.cb_bars2.isChecked(),
            band_1sigma=self.cb_band1.isChecked(),
            band_2sigma=self.cb_band2.isChecked(),
            title="Total integration (with uncertainty)",
        )
        out = f"{base}_total_with_uncertainty.png"
        fig.savefig(out, dpi=150)
        self._update_status(f"Saved {out}")

    def _show_help(self) -> None:
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Help")
        dlg.resize(640, 560)
        lay = QtWidgets.QVBoxLayout(dlg)
        browser = QtWidgets.QTextBrowser()
        browser.setHtml(HELP_TEXT)
        lay.addWidget(browser)
        btn = QtWidgets.QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn)
        dlg.exec_()

    def _show_about(self) -> None:
        QtWidgets.QMessageBox.about(
            self, "About",
            "Ocean Spectrometer GUI\n\n"
            "Interfaces with Ocean spectrometers via the seabreeze backend.\n"
            f"{backend_status()}",
        )

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.abort()
            self.worker.wait(2000)
        if self.spec is not None:
            self.spec.close()
        event.accept()


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    icon_path = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))
    win = SpectrometerGUI()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

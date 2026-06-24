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
<p>The <b>Device</b> panel shows a live connection indicator: a
<font color="#2ca02c">green</font> dot when a device is connected and a
<font color="#cc1f1f">red</font> dot when it is not. The status refreshes
automatically.</p>
<ul>
<li><b>Available devices</b> drop-down - pick which spectrometer to use.</li>
<li><b>Connect</b> - open the selected device (also how you <i>change</i> device).</li>
<li><b>Reconnect</b> - re-open the current device after an unplug/replug.</li>
<li><b>Refresh</b> - re-scan the USB bus for connected devices.</li>
</ul>
<p>If no device or backend is found, a <b>simulation</b> entry is offered so you
can still try every feature.</p>

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

        self._connected = False

        self._build_ui()
        self._update_status(f"Backend: {backend_status()}")
        self._refresh_devices()
        self._set_connection_indicator(False, "Not connected")
        self._refresh_start_enabled()

        # Perpetual connection-status polling (skipped while a run is active).
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._poll_connection)
        self._poll_timer.start()

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

        status_row = QtWidgets.QHBoxLayout()
        self.status_dot = QtWidgets.QLabel("●")  # ●
        dot_font = self.status_dot.font()
        dot_font.setPointSize(16)
        self.status_dot.setFont(dot_font)
        self.status_dot.setFixedWidth(20)
        self.conn_text = QtWidgets.QLabel("Not connected")
        self.conn_text.setWordWrap(True)
        status_row.addWidget(self.status_dot, 0)
        status_row.addWidget(self.conn_text, 1)
        cb.addLayout(status_row)

        cb.addWidget(QtWidgets.QLabel("Available devices:"))
        self.device_combo = QtWidgets.QComboBox()
        cb.addWidget(self.device_combo)

        btn_row = QtWidgets.QHBoxLayout()
        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.setToolTip("Open the device selected above (use to change device)")
        self.connect_btn.clicked.connect(self._connect_selected)
        self.reconnect_btn = QtWidgets.QPushButton("Reconnect")
        self.reconnect_btn.setToolTip("Re-open the current device")
        self.reconnect_btn.clicked.connect(self._reconnect)
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.setToolTip("Re-scan for connected devices")
        self.refresh_btn.clicked.connect(self._refresh_devices)
        btn_row.addWidget(self.connect_btn)
        btn_row.addWidget(self.reconnect_btn)
        btn_row.addWidget(self.refresh_btn)
        cb.addLayout(btn_row)
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
        self.stop_btn = QtWidgets.QPushButton("Interrupt")
        self.stop_btn.setToolTip("Interrupt the current acquisition (asks for confirmation)")
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

        header_font = QtGui.QFont()
        header_font.setBold(True)
        header_font.setPointSize(12)

        left = QtWidgets.QVBoxLayout()
        self.current_header = QtWidgets.QLabel("Current integration")
        self.current_header.setAlignment(QtCore.Qt.AlignCenter)
        self.current_header.setFont(header_font)
        self.fig_current = Figure(figsize=(5, 4), tight_layout=True)
        self.ax_current = self.fig_current.add_subplot(111)
        self.canvas_current = FigureCanvas(self.fig_current)
        left.addWidget(self.current_header)
        left.addWidget(self.canvas_current)

        right = QtWidgets.QVBoxLayout()
        self.avg_header = QtWidgets.QLabel("Average integration")
        self.avg_header.setAlignment(QtCore.Qt.AlignCenter)
        self.avg_header.setFont(header_font)
        self.fig_avg = Figure(figsize=(5, 4), tight_layout=True)
        self.ax_avg = self.fig_avg.add_subplot(111)
        self.canvas_avg = FigureCanvas(self.fig_avg)
        right.addWidget(self.avg_header)
        right.addWidget(self.canvas_avg)

        h.addLayout(left)
        h.addLayout(right)

        plotting.draw_placeholder(self.ax_current)
        plotting.draw_placeholder(self.ax_avg)
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

    #  device mgmt
    def _set_connection_indicator(self, connected: bool, text: str) -> None:
        color = "#2ca02c" if connected else "#cc1f1f"  # green / red
        self.status_dot.setStyleSheet(f"color: {color};")
        self.conn_text.setText(text)
        self._connected = connected

    def _set_device_controls_enabled(self, enabled: bool) -> None:
        for w in (self.device_combo, self.connect_btn,
                  self.reconnect_btn, self.refresh_btn):
            w.setEnabled(enabled)

    def _selected_serial(self) -> Optional[str]:
        if self.device_combo.count() == 0:
            return None
        return self.device_combo.currentData()

    def _refresh_devices(self) -> None:
        previous = self._selected_serial()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        infos = SpectrometerInterface.list_available()
        for info in infos:
            self.device_combo.addItem(info.label, info.serial)
        if previous is not None:
            idx = self.device_combo.findData(previous)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
        self.device_combo.blockSignals(False)
        self._update_status(f"Found {len(infos)} device option(s).")

    def _open(self, serial: str) -> None:
        if self.spec is not None:
            self.spec.close()
            self.spec = None
        try:
            self.spec = SpectrometerInterface.open_serial(serial)
        except Exception as exc:
            self._set_connection_indicator(False, "Not connected")
            QtWidgets.QMessageBox.critical(self, "Connection failed", str(exc))
            return
        mode = "SIMULATION" if self.spec.simulated else "HARDWARE"
        self._set_connection_indicator(
            True, f"Connected [{mode}]\n{self.spec.model}  ·  SN {self.spec.serial_number}")
        self._update_status(f"Connected ({mode}).")
        idx = self.device_combo.findData(str(self.spec.serial_number))
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)

    def _connect_selected(self) -> None:
        serial = self._selected_serial()
        if serial is None:
            QtWidgets.QMessageBox.warning(
                self, "No device", "No device available. Press Refresh to re-scan.")
            return
        self._open(str(serial))

    def _reconnect(self) -> None:
        serial = (str(self.spec.serial_number) if self.spec is not None
                  else self._selected_serial())
        if serial is None:
            self._refresh_devices()
            self._connect_selected()
            return
        self._open(str(serial))

    def _poll_connection(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        if self.spec is None:
            if self._connected:
                self._set_connection_indicator(False, "Not connected")
            return
        if self.spec.is_alive():
            mode = "SIMULATION" if self.spec.simulated else "HARDWARE"
            self._set_connection_indicator(
                True, f"Connected [{mode}]\n{self.spec.model}  ·  SN {self.spec.serial_number}")
        else:
            self._set_connection_indicator(
                False, f"Device lost — {self.spec.model}\nPress Reconnect")

    def _start(self) -> None:
        if self.spec is None:
            self._connect_selected()
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
        self.current_header.setText("Current integration")
        self.avg_header.setText("Average integration")
        plotting.draw_placeholder(self.ax_current)
        plotting.draw_placeholder(self.ax_avg)
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
        self._set_device_controls_enabled(False)
        self._update_status(f"Running -> {self.run_dir}")

    def _stop(self) -> None:
        if self.worker is None or not self.worker.isRunning():
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Interrupt acquisition?",
            "Are you sure you want to interrupt the current acquisition?\n\n"
            "Integrations collected so far will still be saved.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        self.worker.abort()
        self._update_status("Interrupting after current integration...")

    def _on_progress(self, index, total, wavelengths, intensities, avg, std) -> None:
        self._wavelengths = wavelengths
        self._average = avg
        self._std = std
        self.progress.setValue(index)
        self.current_header.setText(f"Current integration  ({index}/{total})")
        plotting.draw_current(self.ax_current, wavelengths, intensities)
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
        self._set_device_controls_enabled(True)
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
        self._set_device_controls_enabled(True)
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

    @staticmethod
    def _save_paper_figure(draw, out_path: str) -> None:
        """Render a paper-quality figure (300 DPI) via the given draw callback."""
        fig = Figure(figsize=plotting.PAPER_FIGSIZE, tight_layout=True)
        ax = fig.add_subplot(111)
        draw(ax)
        fig.savefig(out_path, dpi=plotting.PAPER_DPI)

    def _autosave(self) -> None:
        assert self.run_dir is not None
        base = self.run_dir / self._run_name
        wl = self._wavelengths
        alli = self._all_intensities
        avg = self._average
        std = self._std

        storage.save_csv(Path(f"{base}_data.csv"), self._run_single_ms, wl, alli, avg, std)

        # Picture of the total/average integration (no bars/bands).
        self._save_paper_figure(
            lambda ax: plotting.draw_average(ax, wl, avg, std), f"{base}_total.png")
        # Average integration (no bars/bands).
        self._save_paper_figure(
            lambda ax: plotting.draw_average(ax, wl, avg, std), f"{base}_average.png")
        # Average in red over each individual integration in grey.
        self._save_paper_figure(
            lambda ax: plotting.draw_overlay(ax, wl, alli, avg), f"{base}_average_overlay.png")

    def _save_total_with_uncertainty(self) -> None:
        if self.run_dir is None or self._average is None:
            return
        base = self.run_dir / self._run_name
        out = f"{base}_total_with_uncertainty.png"
        self._save_paper_figure(
            lambda ax: plotting.draw_average(
                ax, self._wavelengths, self._average, self._std,
                bars_1sigma=self.cb_bars1.isChecked(),
                bars_2sigma=self.cb_bars2.isChecked(),
                band_1sigma=self.cb_band1.isChecked(),
                band_2sigma=self.cb_band2.isChecked(),
            ),
            out,
        )
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

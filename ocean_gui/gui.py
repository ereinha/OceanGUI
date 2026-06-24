import sys
from pathlib import Path
from typing import Optional

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtGui, QtWidgets

from . import plotting, storage
from .acquisition import (AcquisitionSettings, AcquisitionWorker, CaptureWorker,
                          RunMode)
from .processing import (MODE_LABELS, MODE_YLABELS, MeasurementMode, Processor,
                         requires_calibration, requires_dark, requires_excitation,
                         requires_reference)
from .spectrometer import SpectrometerError, SpectrometerInterface, backend_status

HELP_TEXT = """\
<h2>Ocean Spectrometer GUI - Help</h2>

<p>The left panel is split into three tabs - <b>Acquire</b> (device + timing +
run name), <b>Processing</b> (measurement mode, dark/reference, parameters,
corrections) and <b>Display</b> (uncertainty overlays). The <b>Start</b> /
<b>Interrupt</b> / <b>Save</b> controls stay pinned below the tabs at all times.</p>

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

<h3>4. Measurement modes</h3>
<p>Pick a mode from the <b>Measurement mode</b> drop-down (S = sample,
D = dark, R = reference):</p>
<ul>
<li><b>Scope</b> - raw counts (no processing).</li>
<li><b>Scope minus dark</b> - raw counts with the stored dark subtracted.
    <i>Needs a dark.</i></li>
<li><b>Absorbance</b> - A = -log10((S-D)/(R-D)). <i>Needs a dark and a
    reference.</i></li>
<li><b>Transmittance (%)</b> / <b>Reflectance (%)</b> - 100·(S-D)/(R-D).
    <i>Need a dark and a reference</i> (a reflectance standard for %R).</li>
<li><b>Irradiance (absolute)</b> - spectral irradiance in µW/cm²/nm. <i>Needs a
    dark and a radiometric calibration file</i> (two columns:
    wavelength_nm, µJ per count). Set the <b>Collection area</b> under
    <i>Mode parameters</i>; the integration time is taken from the run.</li>
<li><b>Raman shift</b> - dark-subtracted intensity plotted against Raman shift
    (cm⁻¹). <i>Needs a dark and an</i> <b>Excitation</b> <i>wavelength</i> (your
    laser, e.g. 532/633/785 nm) under <i>Mode parameters</i>.</li>
</ul>

<h3>5. Background &amp; reference</h3>
<p>Use <b>Capture dark</b> (block the light first) and <b>Capture reference</b>
to store averaged spectra. The labels show whether each is stored and at what
integration time; you'll be warned if a run uses a different integration time.
A mode won't start until everything it needs is provided.</p>

<h3>6. Mode parameters</h3>
<p><b>Excitation</b> sets the Raman laser wavelength. <b>Collection area</b> and
<b>Load calibration…</b> configure absolute irradiance. Only the parameters the
current mode needs are enabled.</p>

<h3>7. Corrections &amp; smoothing</h3>
<p><b>Electric dark</b> and <b>Nonlinearity</b> corrections use device features
that <i>not all spectrometers provide</i> - if yours doesn't, a popup explains
and the option is switched off. <b>Boxcar width</b> applies software smoothing
(0 = off).</p>

<h3>8. Plots</h3>
<p>Left shows the <b>current</b> integration; right shows the running
<b>average</b>, with axes labelled for the selected mode (the x-axis becomes
Raman shift in Raman mode). Example dummy axes are shown until data arrives.
Use the checkboxes to toggle <b>1σ / 2σ uncertainty bars and bands</b>.</p>

<h3>9. Saved files</h3>
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
        self.capture_worker: Optional[CaptureWorker] = None
        self.run_dir: Optional[Path] = None

        self.processor = Processor()
        self._dark_integ_ms: Optional[float] = None
        self._ref_integ_ms: Optional[float] = None
        self._run_xvalues: Optional[np.ndarray] = None
        self._run_xlabel = ""
        self._run_ylabel = ""
        self._run_y0 = True

        self._wavelengths: Optional[np.ndarray] = None
        self._all_intensities: Optional[np.ndarray] = None
        self._average: Optional[np.ndarray] = None
        self._std: Optional[np.ndarray] = None

        self._connected = False

        self._build_ui()
        self._update_status(f"Backend: {backend_status()}")
        self._refresh_devices()
        self._set_connection_indicator(False, "Not connected")
        self.processor.excitation_nm = self.excitation_nm.value()
        self.processor.collection_area_cm2 = self.area_cm2.value()
        self._update_mode_enabled()
        self._on_mode_changed()
        self._update_dark_ref_labels()
        self._refresh_start_enabled()

        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self._poll_connection)
        self._poll_timer.start()

    def _build_ui(self) -> None:
        self._build_menu()

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        left_col = QtWidgets.QWidget()
        left_col.setFixedWidth(350)
        left_layout = QtWidgets.QVBoxLayout(left_col)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(4)
        left_layout.addWidget(self._build_controls(), 1)
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        left_layout.addWidget(sep)
        left_layout.addWidget(self._build_action_bar(), 0)

        layout.addWidget(left_col, 0)
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
        """The left-hand settings, organised into tabs."""
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._scroll_page([self._group_device(),
                                       self._group_acquisition(),
                                       self._group_runname()]), "Acquire")
        tabs.addTab(self._scroll_page([self._group_mode(),
                                       self._group_background(),
                                       self._group_params(),
                                       self._group_corrections()]), "Processing")
        tabs.addTab(self._scroll_page([self._group_uncertainty()]), "Display")
        return tabs

    @staticmethod
    def _scroll_page(groups) -> QtWidgets.QWidget:
        """Wrap a list of group-boxes in a scrollable tab page."""
        inner = QtWidgets.QWidget()
        vb = QtWidgets.QVBoxLayout(inner)
        vb.setContentsMargins(6, 6, 6, 6)
        for group in groups:
            vb.addWidget(group)
        vb.addStretch(1)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidget(inner)
        return scroll

    def _group_device(self) -> QtWidgets.QGroupBox:
        conn_box = QtWidgets.QGroupBox("Device")
        cb = QtWidgets.QVBoxLayout(conn_box)

        status_row = QtWidgets.QHBoxLayout()
        self.status_dot = QtWidgets.QLabel("●")
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
        return conn_box

    def _group_acquisition(self) -> QtWidgets.QGroupBox:
        s_box = QtWidgets.QGroupBox("Acquisition settings")
        form = QtWidgets.QFormLayout(s_box)
        form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        form.setLabelAlignment(QtCore.Qt.AlignLeft)

        self.single_time = QtWidgets.QDoubleSpinBox()
        self.single_time.setRange(0.001, 60000.0)
        self.single_time.setValue(100.0)
        self.single_time.setSuffix(" ms")
        form.addRow("Single integration:", self.single_time)

        self.down_time = QtWidgets.QDoubleSpinBox()
        self.down_time.setRange(0.0, 600000.0)
        self.down_time.setValue(0.0)
        self.down_time.setSuffix(" ms")
        form.addRow("Down time:", self.down_time)

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
        return s_box

    def _group_runname(self) -> QtWidgets.QGroupBox:
        f_box = QtWidgets.QGroupBox("Run name (required)")
        fb = QtWidgets.QVBoxLayout(f_box)
        self.filename = QtWidgets.QLineEdit()
        self.filename.setPlaceholderText("e.g. sample_A")
        self.filename.textChanged.connect(self._refresh_start_enabled)
        fb.addWidget(self.filename)
        return f_box

    def _group_mode(self) -> QtWidgets.QGroupBox:
        m_box = QtWidgets.QGroupBox("Measurement mode")
        ml = QtWidgets.QVBoxLayout(m_box)
        self.mode_combo = QtWidgets.QComboBox()
        for mode in MeasurementMode:
            self.mode_combo.addItem(MODE_LABELS[mode], mode)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        ml.addWidget(self.mode_combo)
        self.mode_hint = QtWidgets.QLabel("")
        self.mode_hint.setWordWrap(True)
        self.mode_hint.setStyleSheet("color: #666666; font-size: 11px;")
        ml.addWidget(self.mode_hint)
        return m_box

    def _group_background(self) -> QtWidgets.QGroupBox:
        b_box = QtWidgets.QGroupBox("Background && reference")
        bl = QtWidgets.QGridLayout(b_box)
        self.capture_dark_btn = QtWidgets.QPushButton("Capture dark")
        self.capture_dark_btn.setToolTip("Store an averaged background "
                                         "(block the light first)")
        self.capture_dark_btn.clicked.connect(self._capture_dark)
        self.clear_dark_btn = QtWidgets.QPushButton("Clear")
        self.clear_dark_btn.clicked.connect(self._clear_dark)
        self.dark_label = QtWidgets.QLabel("Dark: none")
        self.dark_label.setStyleSheet("font-size: 11px;")
        self.capture_ref_btn = QtWidgets.QPushButton("Capture reference")
        self.capture_ref_btn.setToolTip("Store an averaged reference spectrum")
        self.capture_ref_btn.clicked.connect(self._capture_reference)
        self.clear_ref_btn = QtWidgets.QPushButton("Clear")
        self.clear_ref_btn.clicked.connect(self._clear_reference)
        self.ref_label = QtWidgets.QLabel("Reference: none")
        self.ref_label.setStyleSheet("font-size: 11px;")
        bl.addWidget(self.capture_dark_btn, 0, 0)
        bl.addWidget(self.clear_dark_btn, 0, 1)
        bl.addWidget(self.dark_label, 1, 0, 1, 2)
        bl.addWidget(self.capture_ref_btn, 2, 0)
        bl.addWidget(self.clear_ref_btn, 2, 1)
        bl.addWidget(self.ref_label, 3, 0, 1, 2)
        return b_box

    def _group_params(self) -> QtWidgets.QGroupBox:
        self.params_box = QtWidgets.QGroupBox("Mode parameters")
        pl = QtWidgets.QFormLayout(self.params_box)
        pl.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        pl.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        self.excitation_nm = QtWidgets.QDoubleSpinBox()
        self.excitation_nm.setRange(100.0, 2000.0)
        self.excitation_nm.setDecimals(2)
        self.excitation_nm.setValue(785.0)
        self.excitation_nm.setSuffix(" nm")
        self.excitation_nm.setToolTip("Raman excitation laser wavelength")
        self.excitation_nm.valueChanged.connect(self._on_excitation_changed)
        pl.addRow("Excitation (Raman):", self.excitation_nm)

        self.area_cm2 = QtWidgets.QDoubleSpinBox()
        self.area_cm2.setRange(0.0001, 10000.0)
        self.area_cm2.setDecimals(4)
        self.area_cm2.setValue(1.0)
        self.area_cm2.setSuffix(" cm²")
        self.area_cm2.setToolTip("Collection area for absolute irradiance")
        self.area_cm2.valueChanged.connect(self._on_area_changed)
        pl.addRow("Collection area:", self.area_cm2)

        cal_row = QtWidgets.QHBoxLayout()
        self.load_cal_btn = QtWidgets.QPushButton("Load calibration…")
        self.load_cal_btn.setToolTip("Two-column file: wavelength_nm, µJ per count")
        self.load_cal_btn.clicked.connect(self._load_calibration)
        self.clear_cal_btn = QtWidgets.QPushButton("Clear")
        self.clear_cal_btn.clicked.connect(self._clear_calibration)
        cal_row.addWidget(self.load_cal_btn)
        cal_row.addWidget(self.clear_cal_btn)
        pl.addRow("Irradiance cal.:", cal_row)
        self.cal_label = QtWidgets.QLabel("Calibration: none")
        self.cal_label.setStyleSheet("font-size: 11px;")
        self.cal_label.setWordWrap(True)
        pl.addRow(self.cal_label)
        return self.params_box

    def _group_corrections(self) -> QtWidgets.QGroupBox:
        c_box = QtWidgets.QGroupBox("Corrections && smoothing")
        cl = QtWidgets.QFormLayout(c_box)
        cl.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        cl.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        self.cb_electric_dark = QtWidgets.QCheckBox("Electric dark correction")
        self.cb_electric_dark.setToolTip("Uses the detector's dark pixels "
                                         "(not supported by all devices)")
        self.cb_electric_dark.toggled.connect(
            lambda on: self._on_correction_toggled(self.cb_electric_dark, on))
        self.cb_nonlinearity = QtWidgets.QCheckBox("Nonlinearity correction")
        self.cb_nonlinearity.setToolTip("Uses EEPROM coefficients "
                                        "(not supported by all devices)")
        self.cb_nonlinearity.toggled.connect(
            lambda on: self._on_correction_toggled(self.cb_nonlinearity, on))
        cl.addRow(self.cb_electric_dark)
        cl.addRow(self.cb_nonlinearity)
        self.boxcar_width = QtWidgets.QSpinBox()
        self.boxcar_width.setRange(0, 50)
        self.boxcar_width.setValue(0)
        self.boxcar_width.setToolTip("Boxcar smoothing half-window (0 = off)")
        self.boxcar_width.valueChanged.connect(self._on_boxcar_changed)
        cl.addRow("Boxcar width:", self.boxcar_width)
        return c_box

    def _group_uncertainty(self) -> QtWidgets.QGroupBox:
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
        ub.setRowStretch(2, 1)
        return u_box

    def _build_action_bar(self) -> QtWidgets.QWidget:
        """Run controls that stay pinned below the scrollable settings."""
        bar = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(bar)
        lay.setContentsMargins(6, 4, 6, 4)

        row = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("Start")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QtWidgets.QPushButton("Interrupt")
        self.stop_btn.setToolTip("Interrupt the current acquisition (asks for confirmation)")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        lay.addLayout(row)

        self.save_btn = QtWidgets.QPushButton("Save total figure (with bars/bands)")
        self.save_btn.clicked.connect(self._save_total_with_uncertainty)
        self.save_btn.setEnabled(False)
        lay.addWidget(self.save_btn)

        self.progress = QtWidgets.QProgressBar()
        lay.addWidget(self.progress)
        return bar

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
        self.start_btn.setEnabled(has_name and not self._busy())

    def _update_status(self, msg: str) -> None:
        self.statusBar().showMessage(msg)

    def _gather_settings(self) -> AcquisitionSettings:
        return AcquisitionSettings(
            single_time_ms=self.single_time.value(),
            down_time_ms=self.down_time.value(),
            mode=RunMode.NUMBER if self.mode_number.isChecked() else RunMode.TOTAL_TIME,
            n_integrations=self.n_integrations.value(),
            total_time_ms=self.total_time.value(),
            correct_dark_counts=self.cb_electric_dark.isChecked(),
            correct_nonlinearity=self.cb_nonlinearity.isChecked(),
        )

    def _current_mode(self) -> MeasurementMode:
        return self.mode_combo.currentData()

    def _on_mode_changed(self, *_) -> None:
        mode = self._current_mode()
        self.processor.mode = mode
        hints = []
        if requires_dark(mode):
            hints.append("a stored dark")
        if requires_reference(mode):
            hints.append("a stored reference")
        if requires_calibration(mode):
            hints.append("a calibration file")
        if requires_excitation(mode):
            hints.append("an excitation wavelength")
        self.mode_hint.setText(("This mode needs " + " and ".join(hints) + ".")
                               if hints else "Raw spectrum, nothing else needed.")
        self._apply_mode_param_enabled()
        self._redraw_current_and_average()

    def _on_boxcar_changed(self, value: int) -> None:
        self.processor.boxcar_width = int(value)

    def _on_excitation_changed(self, value: float) -> None:
        self.processor.excitation_nm = float(value)
        self._redraw_current_and_average()

    def _on_area_changed(self, value: float) -> None:
        self.processor.collection_area_cm2 = float(value)

    def _load_calibration(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load radiometric calibration",
            str(storage.DEFAULT_SAVE_DIR),
            "Calibration files (*.csv *.txt *.cal *.IrradCal);;All files (*)")
        if not path:
            return
        try:
            data = None
            for delim in (None, ","):
                try:
                    d = np.loadtxt(path, delimiter=delim, comments=("#", ";"), ndmin=2)
                except Exception:
                    continue
                if d.ndim == 2 and d.shape[1] >= 2:
                    data = d
                    break
            if data is None:
                raise ValueError("expected two numeric columns")
            wl = np.asarray(data[:, 0], dtype=float)
            coeff = np.asarray(data[:, 1], dtype=float)
            if wl.size < 2:
                raise ValueError("calibration needs at least 2 points")
            order = np.argsort(wl)
            self.processor.calibration = (wl[order], coeff[order])
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self, "Calibration load failed",
                f"Could not read '{path}':\n{exc}\n\n"
                "Expected two columns: wavelength_nm, microjoule_per_count.")
            return
        from pathlib import Path as _P
        self.cal_label.setText(f"Calibration: {_P(path).name} ({wl.size} pts)")
        self._update_status("Calibration loaded.")

    def _clear_calibration(self) -> None:
        self.processor.calibration = None
        self.cal_label.setText("Calibration: none")

    def _on_correction_toggled(self, checkbox, on: bool) -> None:
        """Verify the device supports a correction the moment it's enabled."""
        if not on or self.spec is None or self._busy():
            return
        try:
            self.spec.probe_corrections(
                correct_dark_counts=self.cb_electric_dark.isChecked(),
                correct_nonlinearity=self.cb_nonlinearity.isChecked(),
            )
        except SpectrometerError as exc:
            QtWidgets.QMessageBox.warning(self, "Correction not supported", str(exc))
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)

    def _busy(self) -> bool:
        return ((self.worker is not None and self.worker.isRunning())
                or (self.capture_worker is not None and self.capture_worker.isRunning()))

    def _capture_dark(self) -> None:
        self._start_capture("dark")

    def _capture_reference(self) -> None:
        self._start_capture("reference")

    def _start_capture(self, which: str) -> None:
        if self._busy():
            return
        if self.spec is None:
            self._connect_selected()
            if self.spec is None:
                return
        self._capture_target = which
        self.capture_worker = CaptureWorker(
            self.spec, self.single_time.value(), n_average=10,
            correct_dark_counts=self.cb_electric_dark.isChecked(),
            correct_nonlinearity=self.cb_nonlinearity.isChecked(),
        )
        self.capture_worker.captured.connect(self._on_captured)
        self.capture_worker.failed.connect(self._on_capture_failed)
        self._set_busy_controls(False)
        self._set_device_controls_enabled(False)
        self.start_btn.setEnabled(False)
        self._update_status(f"Capturing {which} (averaging 10 scans)...")
        self.capture_worker.start()

    def _finish_capture(self) -> None:
        """Restore controls after a capture, whatever the outcome."""
        self.capture_worker = None
        self._set_busy_controls(True)
        self._set_device_controls_enabled(True)
        self._refresh_start_enabled()

    def _on_captured(self, wavelengths, spectrum, integ_ms) -> None:
        if self._capture_target == "dark":
            self.processor.dark = spectrum
            self._dark_integ_ms = integ_ms
        else:
            self.processor.reference = spectrum
            self._ref_integ_ms = integ_ms
        self._finish_capture()
        self._update_dark_ref_labels()
        self._update_status(f"{self._capture_target.capitalize()} stored.")

    def _on_capture_failed(self, message: str) -> None:
        self._finish_capture()
        QtWidgets.QMessageBox.critical(self, "Capture failed", message)
        self._update_status("Capture failed.")

    def _clear_dark(self) -> None:
        self.processor.dark = None
        self._dark_integ_ms = None
        self._update_dark_ref_labels()

    def _clear_reference(self) -> None:
        self.processor.reference = None
        self._ref_integ_ms = None
        self._update_dark_ref_labels()

    def _update_dark_ref_labels(self) -> None:
        if self.processor.dark is None:
            self.dark_label.setText("Dark: none")
        else:
            self.dark_label.setText(f"Dark: stored @ {self._dark_integ_ms:g} ms")
        if self.processor.reference is None:
            self.ref_label.setText("Reference: none")
        else:
            self.ref_label.setText(f"Reference: stored @ {self._ref_integ_ms:g} ms")

    def _set_busy_controls(self, enabled: bool) -> None:
        """Enable/disable capture + mode controls while a run/capture is active."""
        for w in (self.capture_dark_btn, self.clear_dark_btn, self.capture_ref_btn,
                  self.clear_ref_btn, self.mode_combo, self.cb_electric_dark,
                  self.cb_nonlinearity, self.boxcar_width, self.excitation_nm,
                  self.area_cm2, self.load_cal_btn, self.clear_cal_btn):
            w.setEnabled(enabled)
        if enabled:
            self._apply_mode_param_enabled()

    def _apply_mode_param_enabled(self) -> None:
        mode = self.processor.mode
        self.excitation_nm.setEnabled(requires_excitation(mode))
        self.area_cm2.setEnabled(requires_calibration(mode))
        self.load_cal_btn.setEnabled(requires_calibration(mode))
        self.clear_cal_btn.setEnabled(requires_calibration(mode))

    def _set_connection_indicator(self, connected: bool, text: str) -> None:
        color = "#2ca02c" if connected else "#cc1f1f"
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
        if self._busy():
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
        if self._busy():
            return
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

        miss = self.processor.missing_requirement()
        if miss:
            QtWidgets.QMessageBox.warning(self, "Cannot start", miss)
            return

        mismatch = self._integration_mismatch(settings.single_time_ms)
        if mismatch:
            reply = QtWidgets.QMessageBox.question(
                self, "Integration time mismatch", mismatch + "\n\nProceed anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No)
            if reply != QtWidgets.QMessageBox.Yes:
                return

        if settings.correct_dark_counts or settings.correct_nonlinearity:
            try:
                self.spec.probe_corrections(settings.correct_dark_counts,
                                            settings.correct_nonlinearity)
            except SpectrometerError as exc:
                QtWidgets.QMessageBox.warning(self, "Correction not supported", str(exc))
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

        self._run_mode = self.processor.mode
        self.worker = AcquisitionWorker(self.spec, settings, self.processor)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.save_btn.setEnabled(False)
        self._set_device_controls_enabled(False)
        self._set_busy_controls(False)
        self._update_status(f"Running -> {self.run_dir}")

    def _integration_mismatch(self, run_ms: float) -> Optional[str]:
        """Message if a stored dark/reference used a different integration time."""
        issues = []
        if self.processor.dark is not None and self._dark_integ_ms is not None \
                and abs(self._dark_integ_ms - run_ms) > 1e-6:
            issues.append(f"dark was captured at {self._dark_integ_ms:g} ms")
        if self.processor.reference is not None and self._ref_integ_ms is not None \
                and abs(self._ref_integ_ms - run_ms) > 1e-6:
            issues.append(f"reference was captured at {self._ref_integ_ms:g} ms")
        if not issues:
            return None
        return (f"The run uses {run_ms:g} ms but " + " and ".join(issues) +
                ". Dark/reference subtraction is only valid at a matching "
                "integration time.")

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
        try:
            plotting.draw_current(self.ax_current, self.processor.xvalues(wavelengths),
                                  intensities, ylabel=self._ylabel(),
                                  xlabel=self.processor.xlabel(),
                                  y_from_zero=self._y_from_zero())
            self.canvas_current.draw()
            self._redraw_average()
        except Exception as exc:
            self._update_status(f"Plot update skipped: {exc}")

    def _on_finished(self, wavelengths, all_intensities, avg, std) -> None:
        self.worker = None
        self._wavelengths = wavelengths
        self._all_intensities = all_intensities
        self._average = avg
        self._std = std
        self._run_xvalues = self.processor.xvalues(wavelengths)
        self._run_xlabel = self.processor.xlabel()
        self._run_ylabel = MODE_YLABELS[self._run_mode]
        self._run_y0 = self._run_mode is MeasurementMode.SCOPE

        self.stop_btn.setEnabled(False)
        self.save_btn.setEnabled(True)
        self._set_device_controls_enabled(True)
        self._set_busy_controls(True)
        self._refresh_start_enabled()

        try:
            self._redraw_average()
        except Exception as exc:
            self._update_status(f"Plot update skipped: {exc}")
        try:
            self._autosave()
            self._update_status(
                f"Done. {all_intensities.shape[0]} integrations saved to {self.run_dir}")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Save failed", str(exc))

    def _on_failed(self, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, "Acquisition failed", message)
        self.stop_btn.setEnabled(False)
        self.worker = None
        self._set_device_controls_enabled(True)
        self._set_busy_controls(True)
        self._refresh_start_enabled()
        self._update_status("Acquisition failed.")

    def _ylabel(self) -> str:
        return MODE_YLABELS[self.processor.mode]

    def _y_from_zero(self) -> bool:
        return self.processor.mode is MeasurementMode.SCOPE

    def _xdata(self) -> np.ndarray:
        """X-axis values for the current mode (wavelength, or Raman shift)."""
        return self.processor.xvalues(self._wavelengths)

    def _redraw_average(self) -> None:
        if self._wavelengths is None or self._average is None:
            return
        plotting.draw_average(
            self.ax_avg, self._xdata(), self._average, self._std,
            bars_1sigma=self.cb_bars1.isChecked(),
            bars_2sigma=self.cb_bars2.isChecked(),
            band_1sigma=self.cb_band1.isChecked(),
            band_2sigma=self.cb_band2.isChecked(),
            ylabel=self._ylabel(), xlabel=self.processor.xlabel(),
            y_from_zero=self._y_from_zero(),
        )
        self.canvas_avg.draw()

    def _redraw_current_and_average(self) -> None:
        """Redraw both panels (e.g. after a mode/excitation change)."""
        if self._wavelengths is None:
            return
        try:
            self._redraw_average()
        except Exception as exc:
            self._update_status(f"Plot update skipped: {exc}")

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
        x = self._run_xvalues
        alli = self._all_intensities
        avg = self._average
        std = self._std
        ylabel, xlabel, y0 = self._run_ylabel, self._run_xlabel, self._run_y0

        storage.save_csv(Path(f"{base}_data.csv"), self._run_single_ms,
                         self._wavelengths, alli, avg, std, metadata=self._run_metadata())

        self._save_paper_figure(
            lambda ax: plotting.draw_average(ax, x, avg, std, ylabel=ylabel,
                                             xlabel=xlabel, y_from_zero=y0),
            f"{base}_total.png")
        self._save_paper_figure(
            lambda ax: plotting.draw_average(ax, x, avg, std, ylabel=ylabel,
                                             xlabel=xlabel, y_from_zero=y0),
            f"{base}_average.png")
        self._save_paper_figure(
            lambda ax: plotting.draw_overlay(ax, x, alli, avg, ylabel=ylabel,
                                             xlabel=xlabel, y_from_zero=y0),
            f"{base}_average_overlay.png")

    def _run_metadata(self) -> dict:
        """Header fields describing how the run was processed (for the CSV)."""
        meta = {
            "measurement_mode": MODE_LABELS[self._run_mode],
            "quantity": MODE_YLABELS[self._run_mode],
            "electric_dark_correction": self.cb_electric_dark.isChecked(),
            "nonlinearity_correction": self.cb_nonlinearity.isChecked(),
            "boxcar_width": self.boxcar_width.value(),
            "dark_stored": self.processor.dark is not None,
            "reference_stored": self.processor.reference is not None,
        }
        if self._run_mode is MeasurementMode.RAMAN:
            meta["excitation_nm"] = self.excitation_nm.value()
        if self._run_mode is MeasurementMode.IRRADIANCE:
            meta["collection_area_cm2"] = self.area_cm2.value()
            meta["calibration_loaded"] = self.processor.calibration is not None
        return meta

    def _save_total_with_uncertainty(self) -> None:
        if self.run_dir is None or self._average is None:
            return
        base = self.run_dir / self._run_name
        out = f"{base}_total_with_uncertainty.png"
        self._save_paper_figure(
            lambda ax: plotting.draw_average(
                ax, self._run_xvalues, self._average, self._std,
                bars_1sigma=self.cb_bars1.isChecked(),
                bars_2sigma=self.cb_bars2.isChecked(),
                band_1sigma=self.cb_band1.isChecked(),
                band_2sigma=self.cb_band2.isChecked(),
                ylabel=self._run_ylabel, xlabel=self._run_xlabel, y_from_zero=self._run_y0,
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
            self.worker.wait(5000)
        if self.capture_worker is not None and self.capture_worker.isRunning():
            self.capture_worker.wait(5000)
        still_busy = ((self.worker is not None and self.worker.isRunning())
                      or (self.capture_worker is not None
                          and self.capture_worker.isRunning()))
        if self.spec is not None and not still_busy:
            self.spec.close()
        event.accept()


def _install_excepthook() -> None:
    """Keep the app alive if an unexpected exception escapes a Qt slot.

    Without this, PyQt5 aborts the whole process on an unhandled exception in a
    slot. We log it and show a non-fatal dialog instead.
    """
    import traceback

    def hook(exc_type, exc, tb):
        message = "".join(traceback.format_exception(exc_type, exc, tb))
        sys.stderr.write(message)
        try:
            QtWidgets.QMessageBox.critical(
                None, "Unexpected error",
                "An unexpected error occurred but the application is still "
                "running.\n\n" + "".join(traceback.format_exception_only(exc_type, exc)))
        except Exception:
            pass

    sys.excepthook = hook


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    _install_excepthook()
    icon_path = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))
    win = SpectrometerGUI()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

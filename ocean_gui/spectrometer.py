import numpy as np

try:
    from seabreeze.spectrometers import Spectrometer, list_devices

    _SEABREEZE_AVAILABLE = True
except Exception:
    Spectrometer = None
    list_devices = None
    _SEABREEZE_AVAILABLE = False


class SpectrometerError(RuntimeError):
    """Raised when the spectrometer cannot be opened or read."""


class SimulatedSpectrometer:
    model = "Simulated"
    serial_number = "SIM-0001"

    def __init__(self, n_pixels: int = 2048) -> None:
        self._n = n_pixels
        self._wavelengths = np.linspace(340.0, 1024.0, n_pixels)
        self._integration_us = 100_000
        self._peaks = [(486.0, 4000, 6.0), (589.0, 9000, 4.0),
                       (656.0, 6000, 8.0), (820.0, 2500, 12.0)]

    def integration_time_micros(self, micros: int) -> None:
        self._integration_us = int(micros)

    def wavelengths(self) -> np.ndarray:
        return self._wavelengths.copy()

    def intensities(self) -> np.ndarray:
        scale = self._integration_us / 100_000.0
        base = 200.0 * scale + np.zeros(self._n)
        for center, amp, width in self._peaks:
            base += amp * scale * np.exp(-0.5 * ((self._wavelengths - center) / width) ** 2)
        noise = np.random.normal(0.0, np.sqrt(np.abs(base)) + 15.0 * scale)
        return np.clip(base + noise, 0.0, None)

    def close(self) -> None:
        pass


class SpectrometerInterface:
    def __init__(self, device=None, simulated: bool = False) -> None:
        self._device = device
        self.simulated = simulated

    @classmethod
    def open_first(cls, allow_simulation: bool = True) -> "SpectrometerInterface":
        if _SEABREEZE_AVAILABLE:
            try:
                devices = list_devices()
                if devices:
                    spec = Spectrometer.from_first_available()
                    return cls(spec, simulated=False)
            except Exception as exc:
                if not allow_simulation:
                    raise SpectrometerError(f"Could not open spectrometer: {exc}") from exc

        if not allow_simulation:
            raise SpectrometerError(
                "No spectrometer found and simulation disabled. "
                "Connect an Ocean device and install seabreeze."
            )
        return cls(SimulatedSpectrometer(), simulated=True)

    @property
    def model(self) -> str:
        return getattr(self._device, "model", "Unknown")

    @property
    def serial_number(self) -> str:
        return getattr(self._device, "serial_number", "Unknown")

    def set_integration_time_ms(self, milliseconds: float) -> None:
        self._device.integration_time_micros(int(round(milliseconds * 1000)))

    def wavelengths(self) -> np.ndarray:
        return np.asarray(self._device.wavelengths(), dtype=float)

    def intensities(self) -> np.ndarray:
        return np.asarray(self._device.intensities(), dtype=float)

    def close(self) -> None:
        try:
            self._device.close()
        except Exception:
            pass


def backend_status() -> str:
    if not _SEABREEZE_AVAILABLE:
        return "seabreeze not installed - simulation only"
    try:
        devices = list_devices() or []
    except Exception as exc:
        return f"seabreeze installed - device query failed ({exc})"
    if not devices:
        return "seabreeze installed - no device connected (simulation)"
    return f"seabreeze installed - {len(devices)} device(s) found"

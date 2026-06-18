import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from PyQt5 import QtCore

from .spectrometer import SpectrometerInterface


class RunMode(Enum):
    NUMBER = "number"
    TOTAL_TIME = "total_time"


@dataclass
class AcquisitionSettings:
    single_time_ms: float = 100.0
    down_time_ms: float = 0.0
    mode: RunMode = RunMode.NUMBER
    n_integrations: int = 10
    total_time_ms: float = 1000.0

    def integrations_count(self) -> int:
        if self.mode is RunMode.NUMBER:
            return max(1, int(self.n_integrations))
        return max(1, int(self.total_time_ms // max(self.single_time_ms, 1e-6)))

    def validate(self) -> Optional[str]:
        if self.single_time_ms <= 0:
            return "Single integration time must be greater than 0 ms."
        if self.down_time_ms < 0:
            return "Down time cannot be negative."
        if self.mode is RunMode.NUMBER and self.n_integrations < 1:
            return "Number of integrations must be at least 1."
        if self.mode is RunMode.TOTAL_TIME and self.total_time_ms < self.single_time_ms:
            return "Total integration time must be >= single integration time."
        return None


class AcquisitionWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int, int, object, object, object, object)
    finished_ok = QtCore.pyqtSignal(object, object, object, object)  # wl, all, avg, std
    failed = QtCore.pyqtSignal(str)

    def __init__(self, spec: SpectrometerInterface, settings: AcquisitionSettings):
        super().__init__()
        self._spec = spec
        self._settings = settings
        self._abort = False

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:
        try:
            settings = self._settings
            total = settings.integrations_count()
            self._spec.set_integration_time_ms(settings.single_time_ms)

            wavelengths = self._spec.wavelengths()
            collected = np.empty((total, wavelengths.size), dtype=float)
            count = 0

            for i in range(total):
                if self._abort:
                    break
                intensities = self._spec.intensities()
                collected[count] = intensities
                count += 1

                stack = collected[:count]
                avg = stack.mean(axis=0)
                std = stack.std(axis=0, ddof=1) if count > 1 else np.zeros_like(avg)
                self.progress.emit(count, total, wavelengths, intensities, avg, std)

                if settings.down_time_ms > 0 and i < total - 1:
                    self._sleep_ms(settings.down_time_ms)

            if count == 0:
                self.failed.emit("Acquisition aborted before any data was collected.")
                return

            stack = collected[:count]
            avg = stack.mean(axis=0)
            std = stack.std(axis=0, ddof=1) if count > 1 else np.zeros_like(avg)
            self.finished_ok.emit(wavelengths, stack, avg, std)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.failed.emit(str(exc))

    def _sleep_ms(self, ms: float) -> None:
        end = time.monotonic() + ms / 1000.0
        while time.monotonic() < end:
            if self._abort:
                return
            time.sleep(min(0.02, max(0.0, end - time.monotonic())))

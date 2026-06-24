"""Measurement modes and spectral post-processing.

These transforms mirror the standard OceanView acquisition modes. Most are
computed in software from a raw spectrum plus an optional stored **dark**
(background) and **reference** spectrum:

* **Scope**            - raw counts (no processing).
* **Scope minus dark** - raw counts with the dark/background subtracted.
* **Absorbance**       - ``A = -log10((S - D) / (R - D))``.
* **Transmittance**    - ``%T = 100 * (S - D) / (R - D)``.
* **Reflectance**      - ``%R = 100 * (S - D) / (R - D)`` (reflectance standard).
* **Irradiance**       - absolute spectral irradiance (µW/cm²/nm); needs a
                          radiometric **calibration file** and a dark.
* **Raman shift**      - dark-subtracted intensity plotted against Raman shift
                          (cm⁻¹) relative to an **excitation wavelength**.

where S = sample, D = dark, R = reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

import numpy as np

_EPS = 1e-9


class MeasurementMode(Enum):
    SCOPE = "scope"
    DARK_SUBTRACT = "dark_subtract"
    ABSORBANCE = "absorbance"
    TRANSMITTANCE = "transmittance"
    REFLECTANCE = "reflectance"
    IRRADIANCE = "irradiance"
    RAMAN = "raman"


# Human-readable names (for the GUI drop-down) and axis labels per mode.
MODE_LABELS = {
    MeasurementMode.SCOPE: "Scope (raw counts)",
    MeasurementMode.DARK_SUBTRACT: "Scope minus dark",
    MeasurementMode.ABSORBANCE: "Absorbance",
    MeasurementMode.TRANSMITTANCE: "Transmittance (%)",
    MeasurementMode.REFLECTANCE: "Reflectance (%)",
    MeasurementMode.IRRADIANCE: "Irradiance (absolute)",
    MeasurementMode.RAMAN: "Raman shift",
}

MODE_YLABELS = {
    MeasurementMode.SCOPE: "Intensity (counts)",
    MeasurementMode.DARK_SUBTRACT: "Intensity (counts, dark-subtracted)",
    MeasurementMode.ABSORBANCE: "Absorbance (AU)",
    MeasurementMode.TRANSMITTANCE: "Transmittance (%)",
    MeasurementMode.REFLECTANCE: "Reflectance (%)",
    MeasurementMode.IRRADIANCE: "Irradiance (µW/cm²/nm)",
    MeasurementMode.RAMAN: "Intensity (counts, dark-subtracted)",
}

XLABEL_WAVELENGTH = "Wavelength (nm)"
XLABEL_RAMAN = "Raman shift (cm⁻¹)"


def requires_dark(mode: MeasurementMode) -> bool:
    return mode is not MeasurementMode.SCOPE


def requires_reference(mode: MeasurementMode) -> bool:
    return mode in (MeasurementMode.ABSORBANCE,
                    MeasurementMode.TRANSMITTANCE,
                    MeasurementMode.REFLECTANCE)


def requires_calibration(mode: MeasurementMode) -> bool:
    return mode is MeasurementMode.IRRADIANCE


def requires_excitation(mode: MeasurementMode) -> bool:
    return mode is MeasurementMode.RAMAN


def raman_shift(wavelengths: np.ndarray, excitation_nm: float) -> np.ndarray:
    """Raman shift in cm⁻¹ for the given wavelengths and excitation laser."""
    return (1.0e7 / float(excitation_nm)) - (1.0e7 / np.asarray(wavelengths, dtype=float))


def boxcar_smooth(arr: np.ndarray, width: int) -> np.ndarray:
    """Boxcar (moving-average) smoothing with a half-window of ``width``.

    ``width=0`` returns the array unchanged. Edges are handled by edge-padding
    so the output keeps the same length without end artifacts.
    """
    if width <= 0:
        return np.asarray(arr, dtype=float)
    window = 2 * int(width) + 1
    kernel = np.ones(window, dtype=float) / window
    padded = np.pad(np.asarray(arr, dtype=float), width, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


@dataclass
class Processor:
    """Holds the current mode plus stored dark/reference, calibration, etc."""

    mode: MeasurementMode = MeasurementMode.SCOPE
    dark: Optional[np.ndarray] = None
    reference: Optional[np.ndarray] = None
    boxcar_width: int = 0
    # Irradiance: calibration as (wavelength_nm, microjoule_per_count) points.
    calibration: Optional[Tuple[np.ndarray, np.ndarray]] = None
    collection_area_cm2: float = 1.0
    # Raman: excitation laser wavelength in nm.
    excitation_nm: Optional[float] = None

    def ylabel(self) -> str:
        return MODE_YLABELS[self.mode]

    def xlabel(self) -> str:
        return XLABEL_RAMAN if self.mode is MeasurementMode.RAMAN else XLABEL_WAVELENGTH

    def xvalues(self, wavelengths: np.ndarray) -> np.ndarray:
        """X-axis values for plotting (wavelength, or Raman shift for Raman)."""
        if self.mode is MeasurementMode.RAMAN and self.excitation_nm:
            return raman_shift(wavelengths, self.excitation_nm)
        return np.asarray(wavelengths, dtype=float)

    def missing_requirement(self) -> Optional[str]:
        """Return an error message if the mode needs data that isn't set."""
        label = MODE_LABELS[self.mode]
        if requires_dark(self.mode) and self.dark is None:
            return f"{label} needs a stored dark/background spectrum. Capture one first."
        if requires_reference(self.mode) and self.reference is None:
            return f"{label} needs a stored reference spectrum. Capture one first."
        if requires_calibration(self.mode) and self.calibration is None:
            return f"{label} needs a radiometric calibration file. Load one first."
        if requires_excitation(self.mode) and not self.excitation_nm:
            return f"{label} needs an excitation wavelength (nm)."
        return None

    def apply(self, raw: np.ndarray, wavelengths: Optional[np.ndarray] = None,
              integration_time_s: Optional[float] = None) -> np.ndarray:
        """Transform a raw spectrum's intensities for the current mode.

        ``wavelengths`` and ``integration_time_s`` are required for irradiance
        (and ignored by the simpler modes).
        """
        s = boxcar_smooth(raw, self.boxcar_width)
        if self.mode is MeasurementMode.SCOPE:
            return s

        d = boxcar_smooth(self.dark, self.boxcar_width) if self.dark is not None \
            else np.zeros_like(s)
        if self.mode in (MeasurementMode.DARK_SUBTRACT, MeasurementMode.RAMAN):
            return s - d

        if self.mode is MeasurementMode.IRRADIANCE:
            return self._irradiance(s, d, wavelengths, integration_time_s)

        # Ratio modes (absorbance / transmittance / reflectance).
        r = boxcar_smooth(self.reference, self.boxcar_width) \
            if self.reference is not None else np.ones_like(s)
        num = s - d
        denom = r - d
        if self.mode is MeasurementMode.ABSORBANCE:
            ratio = np.clip(num, _EPS, None) / np.clip(denom, _EPS, None)
            return -np.log10(ratio)
        denom_safe = np.where(np.abs(denom) < _EPS, _EPS, denom)
        return 100.0 * num / denom_safe

    def _irradiance(self, s, d, wavelengths, integration_time_s) -> np.ndarray:
        if wavelengths is None or integration_time_s is None or self.calibration is None:
            # Not enough context (guarded by missing_requirement upstream).
            return s - d
        cal_wl, cal_coeff = self.calibration
        cal = np.interp(wavelengths, cal_wl, cal_coeff)          # µJ per count
        dlambda = np.abs(np.gradient(np.asarray(wavelengths, dtype=float)))  # nm/pixel
        dlambda = np.where(dlambda < _EPS, _EPS, dlambda)
        t = max(float(integration_time_s), _EPS)
        area = max(float(self.collection_area_cm2), _EPS)
        # (counts) * (µJ/count) / (s * nm * cm²) = µW/cm²/nm
        return (s - d) * cal / (t * dlambda * area)

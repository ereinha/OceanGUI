import numpy as np

LINE_RED = "#cc1f1f"
LINE_BLUE = "#1f3fcc"
GREY = "#9a9a9a"
BAND_1 = "#cc1f1f"
BAND_2 = "#f0a0a0"


def draw_placeholder(ax, title: str) -> None:
    x = np.linspace(0, 10, 200)
    y = np.sin(x) * np.exp(-0.1 * x)
    ax.clear()
    ax.plot(x, y, color=GREY, linestyle="--", linewidth=1.0)
    ax.set_title(title)
    ax.set_xlabel("Wavelength (nm)  [example axes]")
    ax.set_ylabel("Intensity (counts)  [example axes]")
    ax.text(0.5, 0.5, "Awaiting acquisition", transform=ax.transAxes,
            ha="center", va="center", fontsize=11, color="#666666",
            bbox=dict(boxstyle="round", fc="white", ec="#cccccc"))
    ax.grid(True, alpha=0.3)


def draw_current(ax, wavelengths, intensities, index: int, total: int) -> None:
    ax.clear()
    ax.plot(wavelengths, intensities, color=LINE_BLUE, linewidth=1.0)
    ax.set_title(f"Current integration  ({index}/{total})")
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Intensity (counts)")
    ax.grid(True, alpha=0.3)


def draw_average(
    ax,
    wavelengths,
    average,
    std=None,
    *,
    bars_1sigma: bool = False,
    bars_2sigma: bool = False,
    band_1sigma: bool = False,
    band_2sigma: bool = False,
    title: str = "Average integration",
    color: str = LINE_RED,
) -> None:
    ax.clear()
    if std is None:
        std = np.zeros_like(average)

    if band_2sigma:
        ax.fill_between(wavelengths, average - 2 * std, average + 2 * std,
                        color=BAND_2, alpha=0.5, label=r"2$\sigma$ band")
    if band_1sigma:
        ax.fill_between(wavelengths, average - std, average + std,
                        color=BAND_1, alpha=0.25, label=r"1$\sigma$ band")

    if bars_1sigma or bars_2sigma:
        n = wavelengths.size
        step = max(1, n // 60)
        idx = np.arange(0, n, step)
        k = 2 if bars_2sigma else 1
        label = r"2$\sigma$ bars" if bars_2sigma else r"1$\sigma$ bars"
        ax.errorbar(wavelengths[idx], average[idx], yerr=k * std[idx],
                    fmt="none", ecolor="#444444", elinewidth=0.8,
                    capsize=2, alpha=0.7, label=label)

    ax.plot(wavelengths, average, color=color, linewidth=1.2, label="average")
    ax.set_title(title)
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Intensity (counts)")
    ax.grid(True, alpha=0.3)
    if bars_1sigma or bars_2sigma or band_1sigma or band_2sigma:
        ax.legend(loc="upper right", fontsize=8)


def draw_overlay(ax, wavelengths, all_intensities, average) -> None:
    ax.clear()
    for row in all_intensities:
        ax.plot(wavelengths, row, color=GREY, linewidth=0.6, alpha=0.5)
    ax.plot(wavelengths, average, color=LINE_RED, linewidth=1.4)
    ax.set_title("Average (red) over individual integrations (grey)")
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Intensity (counts)")
    ax.grid(True, alpha=0.3)

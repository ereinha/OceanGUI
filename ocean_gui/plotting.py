import numpy as np

LINE_RED = "#cc1f1f"
LINE_BLUE = "#1f3fcc"
GREY = "#9a9a9a"
BAND_1 = "#cc1f1f"
BAND_2 = "#f0a0a0"

PAPER_FIGSIZE = (6.0, 4.5)   # inches
PAPER_DPI = 300
LABEL_FONTSIZE = 15
TICK_FONTSIZE = 12
LEGEND_FONTSIZE = 11

XLABEL = "Wavelength (nm)"
YLABEL = "Intensity (counts)"


def style_axes(ax, wavelengths=None, *, y_from_zero: bool = False) -> None:
    """Apply the shared paper-quality styling to an axes.

    - axis labels with units, no title;
    - inward major+minor ticks on all four sides;
    - x-limits tightened to the data so ticks reach the plot edges.
    """
    ax.set_xlabel(XLABEL, fontsize=LABEL_FONTSIZE)
    ax.set_ylabel(YLABEL, fontsize=LABEL_FONTSIZE)

    if wavelengths is not None and np.size(wavelengths) > 1:
        ax.set_xlim(float(np.min(wavelengths)), float(np.max(wavelengths)))
    ax.margins(y=0.02)
    if y_from_zero:
        ax.set_ylim(bottom=0.0)

    ax.tick_params(which="major", direction="in", top=True, right=True,
                   length=5, width=1.0, labelsize=TICK_FONTSIZE)
    ax.minorticks_on()
    ax.tick_params(which="minor", direction="in", top=True, right=True,
                   length=3, width=0.8)
    for spine in ax.spines.values():
        spine.set_linewidth(1.0)


def draw_placeholder(ax) -> None:
    """Draw example dummy axes shown before any real data exists."""
    x = np.linspace(0, 10, 200)
    y = np.sin(x) * np.exp(-0.1 * x)
    ax.clear()
    ax.plot(x, y, color=GREY, linestyle="--", linewidth=1.0)
    ax.text(0.5, 0.5, "Awaiting acquisition\n(example axes)",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=12, color="#666666",
            bbox=dict(boxstyle="round", fc="white", ec="#cccccc"))
    style_axes(ax, x)


def draw_current(ax, wavelengths, intensities) -> None:
    """Draw the most recent single integration."""
    ax.clear()
    ax.plot(wavelengths, intensities, color=LINE_BLUE, linewidth=1.0)
    style_axes(ax, wavelengths, y_from_zero=True)


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
    color: str = LINE_RED,
) -> None:
    """Draw the average spectrum with optional uncertainty bars/bands."""
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
    style_axes(ax, wavelengths)
    if bars_1sigma or bars_2sigma or band_1sigma or band_2sigma:
        ax.legend(loc="upper right", fontsize=LEGEND_FONTSIZE, framealpha=0.9)


def draw_overlay(ax, wavelengths, all_intensities, average) -> None:
    """Average in red with each individual integration in grey behind it."""
    ax.clear()
    for row in all_intensities:
        ax.plot(wavelengths, row, color=GREY, linewidth=0.6, alpha=0.5)
    ax.plot(wavelengths, average, color=LINE_RED, linewidth=1.4)
    style_axes(ax, wavelengths, y_from_zero=True)

"""Generate the application icon.

A simple cartoon plot: white background, black border, red spectrum line.
Produces ``icon.png`` (and ``icon.ico`` on systems where Pillow is present)
next to this script.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent


def make_icon(size_px: int = 256) -> Path:
    dpi = 100
    inches = size_px / dpi
    fig = plt.figure(figsize=(inches, inches), dpi=dpi)
    ax = fig.add_axes([0.08, 0.08, 0.84, 0.84])  # leave room for the border

    # Red cartoon spectrum line with a couple of peaks.
    x = np.linspace(0, 10, 500)
    y = (np.exp(-((x - 3) ** 2) / 0.3) * 0.9
         + np.exp(-((x - 6.2) ** 2) / 0.6) * 0.6
         + np.exp(-((x - 8) ** 2) / 0.2) * 0.4
         + 0.05)
    ax.plot(x, y, color="#cc1f1f", linewidth=3.0)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 1.05)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    # Black border.
    for spine in ax.spines.values():
        spine.set_edgecolor("black")
        spine.set_linewidth(4.0)

    png_path = HERE / "icon.png"
    fig.savefig(png_path, dpi=dpi, facecolor="white")
    plt.close(fig)

    # Best-effort .ico for Windows shortcuts.
    try:
        from PIL import Image  # type: ignore

        ico_path = HERE / "icon.ico"
        img = Image.open(png_path)
        img.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    except Exception:
        pass

    return png_path


if __name__ == "__main__":
    path = make_icon()
    print(f"Wrote {path}")

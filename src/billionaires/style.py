"""One visual system for every figure.

Colours are the first three slots of a palette validated for colour-vision
deficiency (all pairs separable under protanopia, deuteranopia and
tritanopia). No chart uses more than three series; anything beyond that is
folded into "Other".
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
INK_3 = "#8a8983"
GRID = "#e6e5e0"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SERIES = (BLUE, ORANGE, AQUA)


def apply() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans", "font.size": 10.5,
        "text.color": INK, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
        "axes.edgecolor": GRID, "axes.linewidth": 1.0,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.axisbelow": True, "axes.titlesize": 13, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.titlepad": 26,
        "xtick.major.size": 0, "ytick.major.size": 0,
        "legend.frameon": False, "legend.fontsize": 9.5,
        "lines.linewidth": 2.0, "lines.solid_capstyle": "round",
        "text.parse_math": False,  # so "$1B" is a dollar amount, not LaTeX
    })


def subtitle(ax, text: str) -> None:
    """Grey one-liner under the title that states the takeaway or the unit."""
    ax.text(0, 1.02, text, transform=ax.transAxes, fontsize=9.5, color=INK_2, va="bottom")


def plot_gapped(ax, years, values, color, label=None, **kw) -> None:
    """Solid line between consecutive years, dashed across gaps in the data."""
    years, values = list(years), list(values)
    for (x0, y0), (x1, y1) in zip(zip(years, values), zip(years[1:], values[1:])):
        ax.plot([x0, x1], [y0, y1], color=color, zorder=1,
                linestyle="-" if x1 - x0 == 1 else (0, (4, 3)),
                linewidth=2 if x1 - x0 == 1 else 1.5)
    ax.plot([], [], color=color, label=label)
    ax.scatter(years, values, color=color, s=kw.pop("s", 45), zorder=3,
               edgecolor=SURFACE, linewidth=1.5, **kw)


def save(fig, path: Path, note: str | None = None) -> Path:
    """Write the figure; ``note`` goes under everything else, legend included."""
    if note:
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        boxes = [ax.get_tightbbox(r) for ax in fig.axes]
        y = min(b.y0 for b in boxes) / fig.bbox.height
        x = min(b.x0 for b in boxes) / fig.bbox.width
        fig.text(x, y - 0.015, note, fontsize=7.5, color=INK_3, ha="left", va="top")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    return path

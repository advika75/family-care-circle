"""Shared matplotlib styling and a grouped-bar helper for all result figures."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

logger = logging.getLogger(__name__)

# Reference palette (light mode). Categorical slots are used in this fixed order, never cycled.
SURFACE, INK, INK_MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
NEUTRAL = "#9a9892"
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
MAX_SERIES = len(CATEGORICAL)


def style_axes(ax: plt.Axes, title: str, ylabel: str) -> None:
    """Recessive grid/axes, left-aligned bold title."""
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=11, fontweight="bold")
    ax.set_ylabel(ylabel, color=INK_MUTED)
    ax.tick_params(colors=INK_MUTED, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.axhline(0, color=GRID, linewidth=0.8)


def grouped_bars(
    ax: plt.Axes,
    categories: Sequence[str],
    series: dict[str, Sequence[float]],
    fmt: str = "{:.2f}",
    label_values: bool | None = None,
    errors: dict[str, Sequence[float]] | None = None,
) -> None:
    """Draw one bar group per category and one bar per series.

    Series beyond the 8 categorical colors are dropped with a warning (never cycled). Values are
    printed on bars only when there are at most 3 series, to avoid clutter. ``errors`` (same shape as
    ``series``) draws error bars, e.g. the std across seeds.
    """
    names = list(series)
    if len(names) > MAX_SERIES:
        logger.warning("Only the first %d series are plotted (got %d).", MAX_SERIES, len(names))
        names = names[:MAX_SERIES]
    n = max(len(names), 1)
    width = min(0.8 / n, 0.38)
    if label_values is None:
        label_values = n <= 3
    for i, name in enumerate(names):
        offsets = [x + (i - (n - 1) / 2) * width for x in range(len(categories))]
        yerr = [e if e == e else 0 for e in errors[name]] if errors and name in errors else None
        bars = ax.bar(offsets, series[name], width=width * 0.94, color=CATEGORICAL[i], edgecolor=SURFACE,
                      linewidth=1.5, label=name, yerr=yerr,
                      error_kw={"ecolor": INK_MUTED, "elinewidth": 1, "capsize": 2})
        if label_values:
            ax.bar_label(bars, labels=[fmt.format(v) if v == v else "" for v in series[name]], padding=3,
                         color=INK, fontsize=8)
    ax.set_xticks(range(len(categories)), categories)
    if n >= 2:  # legend sits between the plot and the title, so push the title up
        ncol = min(n, 5)  # matplotlib fills legends column-first; keep it to one row where possible
        rows = (n + ncol - 1) // ncol
        ax.legend(frameon=False, labelcolor=INK, fontsize=8, loc="lower left", bbox_to_anchor=(0, 1.01),
                  ncol=ncol, handlelength=1.2, columnspacing=1.0)
        ax.set_title(ax.get_title(loc="left"), loc="left", pad=8 + 16 * rows, color=INK, fontsize=11,
                     fontweight="bold")


def new_figure(ncols: int = 1, width_per_panel: float = 5.5, height: float = 4.2) -> tuple[plt.Figure, list[plt.Axes]]:
    """Create a figure with ``ncols`` side-by-side panels on the chart surface."""
    fig, axes = plt.subplots(1, ncols, figsize=(width_per_panel * ncols, height), facecolor=SURFACE, squeeze=False)
    return fig, list(axes[0])


def save_figure(fig: plt.Figure, path: Path, note: str | None = None) -> None:
    """Optionally add a muted caption, then save at 150 dpi and close."""
    if note:
        fig.suptitle(note, color=INK_MUTED, fontsize=9, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)

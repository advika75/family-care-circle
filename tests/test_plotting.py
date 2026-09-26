"""Tests for src/plotting.py."""

from __future__ import annotations

import logging

from src.plotting import MAX_SERIES, grouped_bars, new_figure, save_figure, style_axes


def test_grouped_bars_with_errors_and_legend(tmp_path):
    fig, (ax,) = new_figure(1)
    style_axes(ax, "Title", "y")
    grouped_bars(ax, ["A", "B"], {"s1": [1.0, 2.0], "s2": [1.5, float("nan")]},
                 errors={"s1": [0.1, 0.2], "s2": [float("nan"), 0.0]})
    assert len(ax.patches) == 4 and ax.get_legend() is not None
    save_figure(fig, tmp_path / "chart.png", "caption")
    assert (tmp_path / "chart.png").stat().st_size > 1000


def test_single_series_has_no_legend_and_extra_series_are_dropped(caplog):
    fig, (ax,) = new_figure(1)
    grouped_bars(ax, ["A"], {"only": [1.0]})
    assert ax.get_legend() is None
    fig, (ax,) = new_figure(1)
    with caplog.at_level(logging.WARNING):
        grouped_bars(ax, ["A"], {f"s{i}": [1.0] for i in range(MAX_SERIES + 2)})
    assert len(ax.patches) == MAX_SERIES and "Only the first" in caplog.text

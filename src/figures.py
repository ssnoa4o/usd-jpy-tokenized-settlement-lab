"""Main figures (Day 14). Turns the result CSVs into Plotly figures. Runs no simulation.

Run with: python -m src.figures [--force] [--allow-dirty] [--no-png]
          [--results-dir DIR] [--out-dir DIR]

Reads (all from the results directory):
    summary.csv, stress_test_results.csv, lstar_by_seed.csv, experiment_log.csv,
    h3_verdicts.csv (only for the git commit of the L* data).
Writes into the output directory (default results/figures/):
    f1_baseline, f2_liquidity_stress, f3_delay_failure, f4_h4b, f5_lstar, f6_exposure_liquidity, f7_proxy_delay
        (.html and .png each)
    plotly.min.js  (one shared copy of Plotly, so the HTML files open with no internet)
    figures_manifest.csv  (one row per figure; `slide_candidate` is yours to fill in and is kept on --force)

Layout of this file:
    1. Style (one fixed colour, marker and name per model)
    2. Data checks (fail loudly, never fill with zeros)
    3. Figure builders: take DataFrames, return a plotly Figure (the dashboard can reuse them)
    4. File reading, file writing, manifest and command line

Rules: figures show only numbers from the CSVs; no verdict words; titles describe what is plotted.
Exit code is 1 if a guard refuses, or if PNG export fails (the HTML files are still written).
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.experiments import DirtyTreeError, check_git_clean

# ------------------------------------------------------------------ 1. style

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
FIGURES_DIR = RESULTS_DIR / "figures"

SUMMARY_FILE = "summary.csv"
STRESS_FILE = "stress_test_results.csv"
LSTAR_FILE = "lstar_by_seed.csv"
LOG_FILE = "experiment_log.csv"
H3_FILE = "h3_verdicts.csv"
MANIFEST_FILE = "figures_manifest.csv"

SUMMARY_COLUMNS = ["experiment", "condition", "model", "metric", "n_seeds", "n_valid", "mean", "min", "max"]
LSTAR_COLUMNS = ["factor", "level", "model", "seed", "lstar"]
LOG_COLUMNS = ["experiment", "seeds", "parameters", "git_commit"]

# Model order is always A, B, C. The strings are the `model` values used in the CSVs.
MODEL_ORDER = ["sequential", "prefunded", "atomic"]
MODEL_NAMES = {"sequential": "A: Sequential", "prefunded": "B: Prefunded Tokenized", "atomic": "C: Atomic PvP"}
MODEL_SHORT = {"sequential": "A", "prefunded": "B", "atomic": "C"}
# Colour-blind-friendly palette. The same colour is used for a model in every figure.
MODEL_COLORS = {"sequential": "#D55E00", "prefunded": "#0072B2", "atomic": "#009E73"}
# Different dash and marker per model, so lines that overlap exactly are both still visible:
# A is drawn first with a big round marker, C last with a smaller diamond on top.
MODEL_LINE = {
    "sequential": {"dash": "solid", "width": 6, "symbol": "circle", "size": 20},
    "prefunded": {"dash": "dot", "width": 4, "symbol": "square", "size": 13},
    "atomic": {"dash": "dash", "width": 3, "symbol": "diamond", "size": 9},
}

SYNTHETIC_NOTE = "Synthetic data, own model — independent research prototype"
JPY_ONLY_NOTE = "JPY-only liquidity stress: only JPY balances are lowered, USD balances stay at the reference level"

FONT_SIZE = 18
PNG_WIDTH, PNG_HEIGHT, PNG_SCALE = 1600, 900, 2

# Figure ids in output order.
FIGURE_IDS = [
    "f1_baseline", "f2_liquidity_stress", "f3_delay_failure", "f4_h4b", "f5_lstar",
    "f6_exposure_liquidity", "f7_proxy_delay",
]
PLOTLY_JS_FILE = "plotly.min.js"


class FigureDataError(ValueError):
    """Raised when the CSV data a figure needs is missing or inconsistent."""


@dataclass(frozen=True)
class FigureMeta:
    """Facts printed on a figure, read from the data (never typed in by hand)."""

    seeds: str  # for example "1-30"
    note: str = ""  # extra condition text, for example "delay sweep at failure probability 0.01"
    shared_delay: float | None = None  # f3: delay (s) of the shared exp4_failure/failure_0.01 cell, checked in the log
    grid: tuple[float, ...] | None = None  # f5: the JPY multiplier grid of Exp3, read from the stress CSV


# ------------------------------------------------------------------ 2. data checks

def check_columns(table: pd.DataFrame, columns: Sequence[str], source: str) -> None:
    """Raise FigureDataError if the table lacks a column."""
    missing = [c for c in columns if c not in table.columns]
    if missing:
        raise FigureDataError(f"{source}: missing column(s) {missing}")


def pick_cells(
    table: pd.DataFrame, experiment: str, conditions: Sequence[str], metrics: Sequence[str], source: str = "summary",
) -> dict[tuple[str, str, str], pd.Series]:
    """Return {(condition, model, metric): row} for every combination. Each must exist exactly once.

    Also checks that every row used has the same n_seeds, and that n_valid is 0 (NaN by definition) or n_seeds.
    Raises FigureDataError otherwise.
    """
    check_columns(table, SUMMARY_COLUMNS, source)
    part = table[table["experiment"] == experiment]
    if part.empty:
        raise FigureDataError(f"{source}: experiment '{experiment}' not found")
    cells: dict[tuple[str, str, str], pd.Series] = {}
    for condition in conditions:
        for model in MODEL_ORDER:
            for metric in metrics:
                hit = part[(part["condition"] == condition) & (part["model"] == model) & (part["metric"] == metric)]
                where = f"{source}: experiment '{experiment}', condition '{condition}', model '{model}', metric '{metric}'"
                if len(hit) == 0:
                    raise FigureDataError(f"{where} not found")
                if len(hit) > 1:
                    raise FigureDataError(f"{where} appears {len(hit)} times (expected once)")
                cells[(condition, model, metric)] = hit.iloc[0]
    for key, row in cells.items():
        if int(row["n_valid"]) not in (0, int(row["n_seeds"])):
            raise FigureDataError(
                f"{source}: experiment '{experiment}', condition '{key[0]}', model '{key[1]}', metric '{key[2]}' "
                f"has n_valid={int(row['n_valid'])} but n_seeds={int(row['n_seeds'])} (expected 0 or n_seeds)")
    n_values = {int(row["n_seeds"]) for row in cells.values()}
    if len(n_values) != 1:
        raise FigureDataError(f"{source}: experiment '{experiment}' rows used have different n_seeds: {sorted(n_values)}")
    return cells


def n_seeds_of(cells: dict[tuple[str, str, str], pd.Series]) -> int:
    """The common n_seeds of the rows used (pick_cells has already checked they agree)."""
    return int(next(iter(cells.values()))["n_seeds"])


def merge_cells(*groups: dict[tuple[str, str, str], pd.Series]) -> int:
    """Check that several groups of cells share one n_seeds. Returns it."""
    values = {n_seeds_of(group) for group in groups}
    if len(values) != 1:
        raise FigureDataError(f"rows used in one figure have different n_seeds: {sorted(values)}")
    return values.pop()


def format_seeds(seeds: Sequence[int]) -> str:
    """'1-30' for a continuous range, otherwise a comma list."""
    ordered = sorted(set(int(s) for s in seeds))
    if not ordered:
        raise FigureDataError("no seeds found")
    if ordered == list(range(ordered[0], ordered[-1] + 1)):
        return f"{ordered[0]}-{ordered[-1]}" if len(ordered) > 1 else str(ordered[0])
    return ",".join(str(s) for s in ordered)


def parse_parameters(text: str) -> dict[str, str]:
    """Parse the `parameters` text of the experiment log ('a=1;b=2') into a dict."""
    pairs = (part.split("=", 1) for part in str(text).split(";") if "=" in part)
    return {key.strip(): value.strip() for key, value in pairs}


# ------------------------------------------------------------------ 3. figure builders

def title_block(title: str, lines: Sequence[str]) -> dict[str, object]:
    """Plotly title with a subtitle made of several lines."""
    return {"text": title, "subtitle": {"text": "<br>".join(lines), "font": {"size": 15}},
            "x": 0.01, "xanchor": "left", "y": 0.97, "yanchor": "top", "font": {"size": 26}}  # fmt: skip


def style_layout(fig: go.Figure, title: str, lines: Sequence[str], top_margin: int = 190) -> None:
    """Common layout: fonts, title, subtitle, legend below the plot."""
    fig.update_layout(
        template="plotly_white", font={"size": FONT_SIZE}, width=PNG_WIDTH, height=PNG_HEIGHT,
        title=title_block(title, lines),
        legend={"orientation": "h", "x": 0.5, "xanchor": "center", "y": -0.16, "yanchor": "top",
                "font": {"size": 20}, "itemsizing": "constant", "title": {"text": ""}},
        margin={"l": 100, "r": 40, "t": top_margin, "b": 150},
    )  # fmt: skip
    fig.update_annotations(font={"size": 20})


def subtitle_lines(n_seeds: int, seeds: str, condition_text: str, reading: str, extra: Sequence[str] = ()) -> list[str]:
    """Subtitle lines: seeds, condition, how to read the spread, optional notes, synthetic-data note."""
    first = f"n = {n_seeds} seeds (seeds {seeds}) · {condition_text}"
    return [first, reading, *extra, SYNTHETIC_NOTE]


def line_trace(
    model: str, x: Sequence[object], cells: dict[tuple[str, str, str], pd.Series],
    conditions: Sequence[str], metric: str, show_legend: bool,
) -> go.Scatter:
    """One line for one model: mean as the point, min-max across seeds as error bars."""
    rows = [cells[(c, model, metric)] for c in conditions]
    mean = [float(r["mean"]) for r in rows]
    style = MODEL_LINE[model]
    color = MODEL_COLORS[model]
    return go.Scatter(
        x=list(x), y=mean, mode="lines+markers", cliponaxis=False, name=MODEL_NAMES[model], legendgroup=model, showlegend=show_legend,
        line={"color": color, "dash": style["dash"], "width": style["width"]},
        marker={"color": color, "symbol": style["symbol"], "size": style["size"], "line": {"color": "white", "width": 1}},
        error_y={"type": "data", "symmetric": False, "color": color, "thickness": 2, "width": 7,
                 "array": [float(r["max"]) - float(r["mean"]) for r in rows],
                 "arrayminus": [float(r["mean"]) - float(r["min"]) for r in rows]},
    )  # fmt: skip


def line_x_axis_style() -> dict[str, object]:
    """Keep x tick labels clear of markers that sit on the y = 0 line."""
    return {"ticklabelstandoff": 16}


def padded_range(values: Sequence[float]) -> list[float]:
    """Axis range a little wider than the data, so end markers are not cut in half."""
    low, high = min(values), max(values)
    pad = 0.05 * (high - low)
    return [low - pad, high + pad]


def condition_value(condition: str) -> float:
    """The number at the end of a condition name, e.g. 'jpy_0.0625' gives 0.0625."""
    try:
        return float(condition.rsplit("_", 1)[1])
    except (IndexError, ValueError) as error:
        raise FigureDataError(f"condition '{condition}' does not end with a number") from error


def short_number(value: float) -> str:
    """Compact text for a big number, in the same style as the axis ticks: 2.57e10 gives '25.7B'. NaN gives 'n/a'."""
    if math.isnan(value):
        return "n/a"
    if abs(value) >= 1e9:
        return f"{value / 1e9:.3g}B"
    if abs(value) >= 1e6:
        return f"{value / 1e6:.3g}M"
    return f"{value:.3g}"


F1_EXPERIMENT = "exp1_baseline"
F1_CONDITION = "baseline"
F1_PANELS = [
    ("principal_exposure_usd_seconds", "Principal exposure<br>(duration-weighted)", "USD·s"),
    ("gross_prefunding_usd", "Gross prefunding", "USD"),
    ("peak_liquidity_proxy_usd", "Peak liquidity proxy", "USD"),
]


def build_f1(summary: pd.DataFrame, meta: FigureMeta) -> go.Figure:
    """F1: Exp1 baseline. Three panels (one per metric), one bar per model, mean with min-max whiskers."""
    metrics = [m for m, _, _ in F1_PANELS]
    cells = pick_cells(summary, F1_EXPERIMENT, [F1_CONDITION], metrics)
    n_seeds = n_seeds_of(cells)
    fig = make_subplots(rows=1, cols=3, subplot_titles=[p[1] for p in F1_PANELS], horizontal_spacing=0.11)
    for col, (metric, _, unit) in enumerate(F1_PANELS, start=1):
        labels = []
        for model in MODEL_ORDER:
            row = cells[(F1_CONDITION, model, metric)]
            mean, low, high = float(row["mean"]), float(row["min"]), float(row["max"])
            # NaN stays NaN (no bar). A bar of height 0 would claim "zero", which is not true for Model A.
            error = {"type": "data", "symmetric": False, "array": [high - mean], "arrayminus": [mean - low],
                     "color": "#333333", "thickness": 2, "width": 8}  # fmt: skip
            fig.add_trace(go.Bar(
                x=[MODEL_SHORT[model]], y=[mean], name=MODEL_NAMES[model], legendgroup=model,
                showlegend=(col == 1), marker={"color": MODEL_COLORS[model]}, error_y=error, width=0.6,
            ), row=1, col=col)  # fmt: skip
            labels.append(f"<b>{MODEL_SHORT[model]}</b><br>{short_number(mean)}")
        fig.update_xaxes(tickvals=list(map(MODEL_SHORT.get, MODEL_ORDER)), ticktext=labels, row=1, col=col)
        fig.update_yaxes(title_text=unit, rangemode="tozero", exponentformat="B", row=1, col=col)
    lines = subtitle_lines(n_seeds, meta.seeds, f"condition: {F1_CONDITION}",
                           "Bars show the mean over seeds; whiskers show the min-max range across seeds. "
                           "Labels under bars: mean (n/a = not defined for the model)", meta.note and [meta.note] or [])  # fmt: skip
    style_layout(fig, "Principal exposure, gross prefunding and peak liquidity proxy by model, baseline", lines)
    fig.update_xaxes(tickfont={"size": 16})
    return fig


CATEGORICAL_NOTE = "The x axis is categorical and evenly spaced, although the multipliers are not evenly spaced."
F2_EXPERIMENT = "exp3_liquidity"
F2_CONDITIONS = ["jpy_1", "jpy_0.09375", "jpy_0.0625", "jpy_0.03125", "jpy_0.0125"]
F2_PANELS = [
    ("success_rate", "Success rate (settled only)"),
    ("partial_rate", "Partial rate"),
    ("failure_rate", "Failure rate"),
]


def build_f2(stress: pd.DataFrame, meta: FigureMeta) -> go.Figure:
    """F2: Exp3 JPY liquidity stress. Success, partial and failure rate by JPY multiplier, one line per model."""
    metrics = [m for m, _ in F2_PANELS]
    cells = pick_cells(stress, F2_EXPERIMENT, F2_CONDITIONS, metrics, source="stress_test_results")
    n_seeds = n_seeds_of(cells)
    x = [f"{condition_value(c):g}" for c in F2_CONDITIONS]
    fig = make_subplots(rows=1, cols=3, subplot_titles=[p[1] for p in F2_PANELS], horizontal_spacing=0.08)
    for col, (metric, _) in enumerate(F2_PANELS, start=1):
        for model in MODEL_ORDER:
            fig.add_trace(line_trace(model, x, cells, F2_CONDITIONS, metric, show_legend=(col == 1)), row=1, col=col)
        fig.update_yaxes(title_text="Share of transactions" if col == 1 else None, rangemode="tozero", row=1, col=col)
        fig.update_xaxes(title_text="JPY liquidity multiplier", type="category", row=1, col=col, **line_x_axis_style())
    fig.update_yaxes(range=[0, 1.05], row=1, col=1)
    lines = subtitle_lines(n_seeds, meta.seeds, f"conditions: {', '.join(F2_CONDITIONS)} (1 = reference, lower = more stress)",
                           "Points show the mean over seeds; error bars show the min-max range across seeds. "
                           "Partial is never counted as success. Lines that overlap are drawn with different markers.",
                           [JPY_ONLY_NOTE, CATEGORICAL_NOTE])  # fmt: skip
    style_layout(fig, "Success, partial and failure rate by JPY liquidity multiplier", lines, top_margin=235)
    return fig


F3_FAILURE_EXPERIMENT, F3_FAILURE_CONDITIONS = "exp4_failure", ["failure_0", "failure_0.01", "failure_0.05"]
F3_DELAY_EXPERIMENT, F3_DELAY_CONDITIONS = "exp4_delay", ["delay_0", "delay_300"]
F3_SHARED_CONDITION = "failure_0.01"  # delay 60 s at failure 1%: the same cell serves both sweeps (experiments.py)
F3_ROWS = [
    ("principal_exposure_usd", "Exposure, amount<br>(USD)"),
    ("principal_exposure_usd_seconds", "Exposure, duration-<br>weighted (USD·s)"),
    ("success_rate", "Success rate<br>(share of tx)"),
]


def build_f3(stress: pd.DataFrame, meta: FigureMeta) -> go.Figure:
    """F3: Exp4 failure probability (left) and delay (right). Rows: exposure in USD, in USD·s, success rate."""
    metrics = [m for m, _ in F3_ROWS]
    failure = pick_cells(stress, F3_FAILURE_EXPERIMENT, F3_FAILURE_CONDITIONS, metrics, source="stress_test_results")
    delay = pick_cells(stress, F3_DELAY_EXPERIMENT, F3_DELAY_CONDITIONS, metrics, source="stress_test_results")
    n_seeds = merge_cells(failure, delay)
    if meta.shared_delay is None:
        raise FigureDataError("f3 needs FigureMeta.shared_delay (the delay of the shared failure_0.01 cell, from the log)")
    # The delay sweep has the 60 s point from the shared failure_0.01 cell between the 0 s and 300 s cells.
    delay_cells = {**delay, **{key: row for key, row in failure.items() if key[0] == F3_SHARED_CONDITION}}
    delay_conditions = [F3_DELAY_CONDITIONS[0], F3_SHARED_CONDITION, *F3_DELAY_CONDITIONS[1:]]
    delay_x = [condition_value(F3_DELAY_CONDITIONS[0]), float(meta.shared_delay), condition_value(F3_DELAY_CONDITIONS[1])]
    sweeps = [
        (1, failure, F3_FAILURE_CONDITIONS, [condition_value(c) for c in F3_FAILURE_CONDITIONS],
         "Technical failure probability (per transaction)", "Failure probability sweep"),
        (2, delay_cells, delay_conditions, delay_x, "Settlement delay (seconds)", "Delay sweep"),
    ]
    fig = make_subplots(rows=3, cols=2, shared_yaxes="rows", horizontal_spacing=0.05, vertical_spacing=0.09,
                        column_titles=[s[5] for s in sweeps])  # fmt: skip
    for col, cells, conditions, x, x_title, _ in sweeps:
        for row, (metric, _) in enumerate(F3_ROWS, start=1):
            for model in MODEL_ORDER:
                fig.add_trace(line_trace(model, x, cells, conditions, metric, show_legend=(row == 1 and col == 1)),
                              row=row, col=col)  # fmt: skip
            fig.update_xaxes(tickvals=x, range=padded_range(x), title_text=x_title if row == 3 else None,
                             exponentformat="none", row=row, col=col, **line_x_axis_style())  # fmt: skip
    for row, (metric, label) in enumerate(F3_ROWS, start=1):
        fig.update_yaxes(title_text=label, title_font={"size": 16}, rangemode="tozero", exponentformat="B",
                         row=row, col=1)  # fmt: skip
    fig.update_yaxes(range=[0, 1.05], row=3, col=1)
    lines = subtitle_lines(n_seeds, meta.seeds, "conditions: " + ", ".join(F3_FAILURE_CONDITIONS + F3_DELAY_CONDITIONS),
                           "Points show the mean over seeds; error bars show the min-max range across seeds. "
                           "Partial is never counted as success. Lines that overlap are drawn with different markers.",
                           [meta.note] if meta.note else [])  # fmt: skip
    style_layout(fig, "Principal exposure and success rate by failure probability and settlement delay", lines, top_margin=210)
    fig.update_layout(legend={"y": -0.12}, margin={"b": 130})
    return fig


F4_EXPERIMENT = "exp4_h4b"
F4_CONDITIONS = ["h4b_delay_0", "h4b_delay_60", "h4b_delay_300"]
F4_METRIC = "principal_exposure_usd"  # the H4b primary metric (hypotheses.md): amount-based Principal Exposure


def build_f4(stress: pd.DataFrame, meta: FigureMeta) -> go.Figure:
    """F4: Exp4 H4b cell. Amount-based principal exposure (USD) by delay, one line per model."""
    cells = pick_cells(stress, F4_EXPERIMENT, F4_CONDITIONS, [F4_METRIC], source="stress_test_results")
    n_seeds = n_seeds_of(cells)
    x = [condition_value(c) for c in F4_CONDITIONS]
    fig = go.Figure()
    for model in MODEL_ORDER:
        fig.add_trace(line_trace(model, x, cells, F4_CONDITIONS, F4_METRIC, show_legend=True))
    fig.update_xaxes(title_text="Settlement delay (seconds)", tickvals=x, range=padded_range(x), **line_x_axis_style())
    fig.update_yaxes(title_text="Principal exposure, amount (USD)", rangemode="tozero", exponentformat="B")
    lines = subtitle_lines(n_seeds, meta.seeds, f"conditions: {', '.join(F4_CONDITIONS)}",
                           "Points show the mean over seeds; error bars show the min-max range across seeds. "
                           "Amount-based exposure ignores delay by definition.",
                           [JPY_ONLY_NOTE] + ([meta.note] if meta.note else []))  # fmt: skip
    style_layout(fig, "Principal exposure by settlement delay under JPY liquidity stress, per model", lines, top_margin=210)
    return fig


F6_METRIC = "principal_exposure_usd"  # the H1b metric (verdicts.py h1b_rows): amount-based Principal Exposure


def build_f6(stress: pd.DataFrame, meta: FigureMeta) -> go.Figure:
    """F6: Exp3 JPY liquidity stress. Amount-based principal exposure (USD) by JPY multiplier, one line per model."""
    cells = pick_cells(stress, F2_EXPERIMENT, F2_CONDITIONS, [F6_METRIC], source="stress_test_results")
    n_seeds = n_seeds_of(cells)
    x = [f"{condition_value(c):g}" for c in F2_CONDITIONS]
    fig = go.Figure()
    for model in MODEL_ORDER:
        fig.add_trace(line_trace(model, x, cells, F2_CONDITIONS, F6_METRIC, show_legend=True))
    fig.update_xaxes(title_text="JPY liquidity multiplier", type="category", **line_x_axis_style())
    fig.update_yaxes(title_text="Principal exposure, amount (USD)", rangemode="tozero", exponentformat="B")
    lines = subtitle_lines(n_seeds, meta.seeds, f"conditions: {', '.join(F2_CONDITIONS)} (1 = reference, lower = more stress)",
                           "Points show the mean over seeds; error bars show the min-max range across seeds. "
                           "Lines that overlap are drawn with different markers.",
                           [JPY_ONLY_NOTE, CATEGORICAL_NOTE])  # fmt: skip
    style_layout(fig, "Principal exposure (amount) by JPY liquidity multiplier, per model", lines, top_margin=235)
    return fig


F7_METRIC = "peak_liquidity_proxy_usd"
REFERENCE_MULTIPLIER = 1.0  # JPY liquidity multiplier of the reference (ample) level
H2_NOTE = ("Ranges are across seeds. The H2 rule compares models within the same seed (B minus A); "
           "the per-seed gap is recorded in results/verdicts.csv.")


def build_f7(stress: pd.DataFrame, meta: FigureMeta) -> go.Figure:
    """F7: Exp4 delay sweep at ample liquidity. Peak Liquidity Proxy (USD) by delay, one line per model."""
    delay = pick_cells(stress, F3_DELAY_EXPERIMENT, F3_DELAY_CONDITIONS, [F7_METRIC], source="stress_test_results")
    shared = pick_cells(stress, F3_FAILURE_EXPERIMENT, [F3_SHARED_CONDITION], [F7_METRIC], source="stress_test_results")
    n_seeds = merge_cells(delay, shared)
    if meta.shared_delay is None:
        raise FigureDataError("f7 needs FigureMeta.shared_delay (the delay of the shared failure_0.01 cell, from the log)")
    cells = {**delay, **shared}
    conditions = [F3_DELAY_CONDITIONS[0], F3_SHARED_CONDITION, *F3_DELAY_CONDITIONS[1:]]
    x = [condition_value(F3_DELAY_CONDITIONS[0]), float(meta.shared_delay), condition_value(F3_DELAY_CONDITIONS[1])]
    fig = go.Figure()
    for model in MODEL_ORDER:
        fig.add_trace(line_trace(model, x, cells, conditions, F7_METRIC, show_legend=True))
    fig.update_xaxes(title_text="Settlement delay (seconds)", tickvals=x, range=padded_range(x), **line_x_axis_style())
    fig.update_yaxes(title_text="Peak liquidity proxy (USD)", rangemode="tozero", exponentformat="B")
    lines = subtitle_lines(n_seeds, meta.seeds, "conditions: " + ", ".join(F3_DELAY_CONDITIONS + [F3_SHARED_CONDITION]),
                           "Points show the mean over seeds; error bars show the min-max range across seeds. "
                           "Lines that overlap are drawn with different markers.",
                           [H2_NOTE] + ([meta.note] if meta.note else []))  # fmt: skip
    style_layout(fig, "Peak liquidity proxy by settlement delay, ample liquidity, per model", lines, top_margin=210)
    return fig


def level_sort_key(level: str) -> tuple[int, float, str]:
    """Numbers first in numeric order, then text."""
    try:
        return (0, float(level), level)
    except ValueError:
        return (1, 0.0, level)


FACTOR_ORDER = ["baseline", "volume", "banks", "arrival"]


def facet_label(factor: str, level: str) -> str:
    """Panel title for one factor level."""
    return level if factor == level else f"{factor} = {level}"


def build_f5(lstar: pd.DataFrame, meta: FigureMeta | None = None) -> go.Figure:
    """F5: how many seeds ended at each L* value, per factor level and model (grouped bars with counts)."""
    check_columns(lstar, LSTAR_COLUMNS, "lstar_by_seed")
    if lstar.empty:
        raise FigureDataError("lstar_by_seed: no rows")
    table = lstar.copy()
    table["level"] = table["level"].astype(str)
    missing_models = [m for m in MODEL_ORDER if m not in set(table["model"])]
    if missing_models:
        raise FigureDataError(f"lstar_by_seed: model(s) {missing_models} not found")
    if table["lstar"].isna().any():
        raise FigureDataError("lstar_by_seed: lstar has empty values (L* not reached); the figure does not handle these")
    facets = sorted({(f, lv) for f, lv in zip(table["factor"], table["level"], strict=True)},
                    key=lambda p: (FACTOR_ORDER.index(p[0]) if p[0] in FACTOR_ORDER else len(FACTOR_ORDER), level_sort_key(p[1])))  # fmt: skip
    seed_counts = {(f, lv, m): table[(table["factor"] == f) & (table["level"] == lv) & (table["model"] == m)]["seed"].nunique()
                   for f, lv in facets for m in MODEL_ORDER}  # fmt: skip
    if len(set(seed_counts.values())) != 1 or 0 in seed_counts.values():
        raise FigureDataError(f"lstar_by_seed: seeds per factor level and model differ: {sorted(set(seed_counts.values()))}")
    n_seeds = next(iter(seed_counts.values()))
    values = sorted({float(v) for v in table["lstar"]}, reverse=True)  # 1 first, lowest liquidity last
    x = [f"{v:g}" for v in values]
    unused_note: list[str] = []
    if meta is not None and meta.grid:
        outside = [v for v in values if not any(math.isclose(v, g) for g in meta.grid)]
        if outside:
            raise FigureDataError(f"lstar_by_seed: L* value(s) {outside} are not on the Exp3 grid {sorted(meta.grid, reverse=True)}")
        unused = [g for g in sorted(meta.grid, reverse=True) if not any(math.isclose(g, v) for v in values)]
        if unused:
            unused_note = ["Grid value(s) with no seed, not shown: " + ", ".join(f"{g:g}" for g in unused)]
    n_rows, n_cols = 2, 3
    if len(facets) > n_rows * n_cols:
        raise FigureDataError(f"lstar_by_seed: {len(facets)} factor levels, the layout holds {n_rows * n_cols}")
    fig = make_subplots(rows=n_rows, cols=n_cols, shared_yaxes=True, vertical_spacing=0.17, horizontal_spacing=0.04,
                        subplot_titles=[facet_label(f, lv) for f, lv in facets])  # fmt: skip
    for index, (factor, level) in enumerate(facets):
        row, col = index // n_cols + 1, index % n_cols + 1
        cell = table[(table["factor"] == factor) & (table["level"] == level)]
        for model in MODEL_ORDER:
            counts = cell[cell["model"] == model]["lstar"].astype(float).value_counts()
            y = [int(counts.get(v, 0)) for v in values]
            fig.add_trace(go.Bar(
                x=x, y=y, name=MODEL_NAMES[model], legendgroup=model, showlegend=(index == 0),
                marker={"color": MODEL_COLORS[model]}, text=[str(n) if n else "" for n in y], textposition="outside",
                textfont={"size": 14}, cliponaxis=False,
            ), row=row, col=col)  # fmt: skip
        fig.update_xaxes(type="category", categoryorder="array", categoryarray=x, tickfont={"size": 15},
                         title_text="L* (JPY multiplier)" if row == n_rows else None, row=row, col=col)  # fmt: skip
        fig.update_yaxes(range=[0, n_seeds + 3], title_text="Number of seeds" if col == 1 else None, row=row, col=col)
    seeds = meta.seeds if meta is not None else format_seeds(table["seed"].tolist())
    lines = subtitle_lines(
        n_seeds, seeds, "conditions: factor levels shown in the panel titles, each on the JPY multiplier grid",
        "Bars count seeds per L* value. L* = lowest JPY multiplier at which the success rate stays at 95% or more "
        "(1 = reference level). Partial is not success.", [JPY_ONLY_NOTE, *unused_note])  # fmt: skip
    style_layout(fig, "Distribution of L* across seeds by factor level and model", lines, top_margin=235)
    fig.update_layout(barmode="group", bargap=0.2, bargroupgap=0.04, legend={"y": -0.1}, margin={"b": 130})
    return fig


# ------------------------------------------------------------------ 4. reading, writing, manifest, command line

def read_csv_checked(path: Path) -> pd.DataFrame:
    """Read a CSV, with a clear error if the file is missing."""
    if not path.exists():
        raise FigureDataError(f"Required file not found: {path}")
    return pd.read_csv(path)


def log_facts(log: pd.DataFrame, experiments: Sequence[str]) -> tuple[list[int], list[str]]:
    """Seeds (as integers) and git commits that the log records for the given experiments."""
    check_columns(log, LOG_COLUMNS, LOG_FILE)
    part = log[log["experiment"].isin(experiments)]
    if part.empty:
        raise FigureDataError(f"{LOG_FILE}: no rows for experiment(s) {list(experiments)}")
    try:
        seeds = sorted({int(s) for s in part["seeds"]})
    except ValueError as error:
        raise FigureDataError(f"{LOG_FILE}: a seeds value is not a single integer for {list(experiments)}") from error
    commits = list(dict.fromkeys(str(c) for c in part["git_commit"]))
    return seeds, commits


def check_seed_count(seeds: Sequence[int], n_seeds: int, experiments: Sequence[str]) -> None:
    """The log's seeds and the CSV's n_seeds must agree."""
    if len(seeds) != n_seeds:
        raise FigureDataError(f"{LOG_FILE} lists {len(seeds)} seeds for {list(experiments)} but the result CSV says n_seeds={n_seeds}")


def one_parameter(log: pd.DataFrame, experiment: str, key: str) -> str:
    """The value of a parameter that must be the same in every log row of the experiment."""
    values = {parse_parameters(p).get(key) for p in log[log["experiment"] == experiment]["parameters"]}
    if len(values) != 1 or None in values:
        raise FigureDataError(f"{LOG_FILE}: parameter '{key}' is missing or not unique for experiment '{experiment}'")
    return values.pop()


@dataclass
class FigureSpec:
    """How to make one figure: which files, experiments, conditions and metrics it uses."""

    figure_id: str
    sources: list[str]
    experiments: list[str]
    conditions: list[str]
    metrics: list[str]
    build: Callable[[pd.DataFrame, FigureMeta], go.Figure]
    table: str  # which CSV holds the data: "summary", "stress" or "lstar"


SPECS = [
    FigureSpec("f1_baseline", [SUMMARY_FILE, LOG_FILE], [F1_EXPERIMENT], [F1_CONDITION],
               [m for m, _, _ in F1_PANELS], build_f1, "summary"),
    FigureSpec("f2_liquidity_stress", [STRESS_FILE, LOG_FILE], [F2_EXPERIMENT], F2_CONDITIONS,
               [m for m, _ in F2_PANELS], build_f2, "stress"),
    FigureSpec("f3_delay_failure", [STRESS_FILE, LOG_FILE], [F3_FAILURE_EXPERIMENT, F3_DELAY_EXPERIMENT],
               F3_FAILURE_CONDITIONS + F3_DELAY_CONDITIONS, [m for m, _ in F3_ROWS], build_f3, "stress"),
    FigureSpec("f4_h4b", [STRESS_FILE, LOG_FILE], [F4_EXPERIMENT], F4_CONDITIONS, [F4_METRIC], build_f4, "stress"),
    FigureSpec("f5_lstar", [LSTAR_FILE, H3_FILE, STRESS_FILE, LOG_FILE], ["exp2_x_exp3"], ["see lstar_by_seed.csv factor/level"],
               ["lstar"], lambda table, meta: build_f5(table, meta), "lstar"),
    FigureSpec("f6_exposure_liquidity", [STRESS_FILE, LOG_FILE], [F2_EXPERIMENT], F2_CONDITIONS, [F6_METRIC],
               build_f6, "stress"),
    FigureSpec("f7_proxy_delay", [STRESS_FILE, LOG_FILE], [F3_DELAY_EXPERIMENT, F3_FAILURE_EXPERIMENT],
               F3_DELAY_CONDITIONS + [F3_SHARED_CONDITION], [F7_METRIC], build_f7, "stress"),
]  # fmt: skip


def condition_parameters(log: pd.DataFrame, experiment: str, condition: str) -> dict[str, str]:
    """The log parameters of one condition. All log rows of that condition must agree."""
    texts = {p for p in log[log["experiment"] == experiment]["parameters"] if parse_parameters(p).get("condition") == condition}
    if len(texts) != 1:
        raise FigureDataError(f"{LOG_FILE}: expected one parameter set for {experiment}/{condition}, found {len(texts)}")
    return parse_parameters(texts.pop())


def shared_cell_delay(log: pd.DataFrame) -> float:
    """Delay (s) of the exp4_failure/failure_0.01 cell, after checking that it can serve as the 60 s delay point.

    Its failure probability must equal the one fixed in the delay sweep, and every other parameter must match
    the delay-sweep cells (only the delay differs). Raises FigureDataError otherwise.
    """
    shared = condition_parameters(log, F3_FAILURE_EXPERIMENT, F3_SHARED_CONDITION)
    for key in ("delay_seconds", "failure_probability"):
        if key not in shared:
            raise FigureDataError(f"{LOG_FILE}: {F3_FAILURE_EXPERIMENT}/{F3_SHARED_CONDITION} has no '{key}'")
    fixed = float(one_parameter(log, F3_DELAY_EXPERIMENT, "failure_probability"))
    if not math.isclose(float(shared["failure_probability"]), fixed):
        raise FigureDataError(
            f"{LOG_FILE}: {F3_FAILURE_EXPERIMENT}/{F3_SHARED_CONDITION} has failure_probability "
            f"{shared['failure_probability']} but the delay sweep uses {fixed:g}; it cannot be the shared cell")
    for condition in F3_DELAY_CONDITIONS:
        other = condition_parameters(log, F3_DELAY_EXPERIMENT, condition)
        ignore = {"condition", "delay_seconds"}
        if {k: v for k, v in shared.items() if k not in ignore} != {k: v for k, v in other.items() if k not in ignore}:
            raise FigureDataError(f"{LOG_FILE}: {F3_FAILURE_EXPERIMENT}/{F3_SHARED_CONDITION} differs from "
                                  f"{F3_DELAY_EXPERIMENT}/{condition} in more than the delay; it cannot be the shared cell")
    delay_values = {float(condition_parameters(log, F3_DELAY_EXPERIMENT, c)["delay_seconds"]) for c in F3_DELAY_CONDITIONS}
    delay = float(shared["delay_seconds"])
    if delay in delay_values or not min(delay_values) < delay < max(delay_values):
        raise FigureDataError(f"{LOG_FILE}: shared cell delay {delay:g} s does not lie between the delay-sweep cells {sorted(delay_values)}")
    return delay


def check_ample_delay_cells(log: pd.DataFrame) -> str:
    """The delay cells and the shared cell must be at the reference JPY multiplier. Returns its text."""
    cells = [(F3_DELAY_EXPERIMENT, c) for c in F3_DELAY_CONDITIONS] + [(F3_FAILURE_EXPERIMENT, F3_SHARED_CONDITION)]
    for experiment, condition in cells:
        parameters = condition_parameters(log, experiment, condition)
        value = parameters.get("jpy_multiplier")
        if value is None or not math.isclose(float(value), REFERENCE_MULTIPLIER):
            raise FigureDataError(f"{LOG_FILE}: {experiment}/{condition} has jpy_multiplier {value}, "
                                  f"expected the reference level {REFERENCE_MULTIPLIER:g} (ample liquidity)")
    return f"{REFERENCE_MULTIPLIER:g}"


def figure_note(spec: FigureSpec, log: pd.DataFrame) -> str:
    """Extra condition text taken from the log (delay or failure probability held fixed)."""
    if spec.figure_id == "f3_delay_failure":
        delay = one_parameter(log, F3_FAILURE_EXPERIMENT, "delay_seconds")
        failure = one_parameter(log, F3_DELAY_EXPERIMENT, "failure_probability")
        return (f"Failure sweep at delay {delay} s; delay sweep at failure probability {failure}. The "
                f"{shared_cell_delay(log):g} s point of the delay sweep is the shared {F3_SHARED_CONDITION} cell. "
                "Success-rate axis starts at 0.")
    if spec.figure_id == "f7_proxy_delay":
        failure = one_parameter(log, F3_DELAY_EXPERIMENT, "failure_probability")
        multiplier = check_ample_delay_cells(log)
        return (f"Ample liquidity (JPY multiplier {multiplier}, reference level); failure probability {failure}. "
                f"The {shared_cell_delay(log):g} s point is the shared {F3_SHARED_CONDITION} cell.")
    if spec.figure_id == "f4_h4b":
        return f"JPY liquidity multiplier {one_parameter(log, F4_EXPERIMENT, 'jpy_multiplier')}"
    return ""


def build_all(results_dir: Path) -> dict[str, tuple[go.Figure, dict[str, object]]]:
    """Read the CSVs and build every figure. Returns {figure_id: (figure, manifest facts)}."""
    tables = {
        "summary": read_csv_checked(results_dir / SUMMARY_FILE),
        "stress": read_csv_checked(results_dir / STRESS_FILE),
        "lstar": read_csv_checked(results_dir / LSTAR_FILE),
    }
    log = read_csv_checked(results_dir / LOG_FILE)
    h3 = read_csv_checked(results_dir / H3_FILE)
    check_columns(h3, ["git_commit"], H3_FILE)
    built: dict[str, tuple[go.Figure, dict[str, object]]] = {}
    for spec in SPECS:
        table = tables[spec.table]
        commits: list[str]
        if spec.table == "lstar":
            seeds = sorted(int(s) for s in table["seed"].unique())
            commits = list(dict.fromkeys(str(c) for c in h3["git_commit"]))
            n_seeds = len(seeds)
            _, log_commits = log_facts(log, spec.experiments)
            commits = list(dict.fromkeys(commits + log_commits))
        else:
            seeds, commits = log_facts(log, spec.experiments)
        shared = shared_cell_delay(log) if spec.figure_id in ("f3_delay_failure", "f7_proxy_delay") else None
        grid = None
        if spec.figure_id == "f5_lstar":
            conditions = tables["stress"][tables["stress"]["experiment"] == F2_EXPERIMENT]["condition"].unique()
            grid = tuple(sorted(condition_value(c) for c in conditions))
        meta = FigureMeta(seeds=format_seeds(seeds), note=figure_note(spec, log), shared_delay=shared, grid=grid)
        fig = spec.build(table, meta)
        if spec.table != "lstar":
            n_seeds = int(table[table["experiment"].isin(spec.experiments)]["n_seeds"].iloc[0])
            check_seed_count(seeds, n_seeds, spec.experiments)
        built[spec.figure_id] = (fig, {
            "spec": spec, "n_seeds": n_seeds, "seeds": meta.seeds, "commits": commits,
        })  # fmt: skip
    return built


def output_names(figure_id: str) -> tuple[str, str]:
    """HTML and PNG file names of a figure."""
    return f"{figure_id}.html", f"{figure_id}.png"


def manifest_rows(
    built: dict[str, tuple[go.Figure, dict[str, object]]], results_dir: Path, png_written: set[str],
    code_commit: str, generated_utc: str, slide_candidates: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """One manifest row per figure. `slide_candidates` carries over values the user typed earlier."""
    slide_candidates = slide_candidates or {}
    rows = []
    for figure_id, (_, facts) in built.items():
        spec: FigureSpec = facts["spec"]  # type: ignore[assignment]
        html_name, png_name = output_names(figure_id)
        rows.append({
            "figure_id": figure_id, "html_file": html_name, "png_file": png_name if figure_id in png_written else "",
            "source_csvs": ";".join(f"{results_dir.name}/{name}" for name in spec.sources),
            "experiments": ";".join(spec.experiments), "conditions": ";".join(spec.conditions),
            "metrics": ";".join(spec.metrics), "n_seeds": str(facts["n_seeds"]), "seeds": str(facts["seeds"]),
            "data_git_commits": ";".join(facts["commits"]),  # type: ignore[arg-type]
            "figure_code_commit": code_commit, "generated_utc": generated_utc, "slide_candidate": slide_candidates.get(figure_id, ""),
        })  # fmt: skip
    return rows


MANIFEST_COLUMNS = ["figure_id", "html_file", "png_file", "source_csvs", "experiments", "conditions", "metrics",
                    "n_seeds", "seeds", "data_git_commits", "figure_code_commit", "generated_utc", "slide_candidate"]  # fmt: skip


def read_slide_candidates(path: Path) -> dict[str, str]:
    """The `slide_candidate` values of an existing manifest, by figure id (empty dict if there is none)."""
    if not path.exists():
        return {}
    old = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "figure_id" not in old.columns or "slide_candidate" not in old.columns:
        return {}
    return {row["figure_id"]: row["slide_candidate"] for _, row in old.iterrows() if row["slide_candidate"] != ""}


def write_png(fig: go.Figure, path: Path) -> None:
    """Export one PNG (16:9, 1600x900 at scale 2). Needs kaleido and a Chrome/Chromium."""
    fig.write_image(str(path), width=PNG_WIDTH, height=PNG_HEIGHT, scale=PNG_SCALE)


PNG_HELP = (
    "PNG export failed. The HTML files were written. Kaleido needs Google Chrome or Chromium. "
    "Install Chrome, or run `plotly_get_chrome` inside the .venv (it downloads a private copy), then rerun with --force."
)


def main(
    results_dir: Path = RESULTS_DIR, out_dir: Path | None = None, force: bool = False,
    allow_dirty: bool = False, write_png_files: bool = True,
) -> dict[str, object]:
    """Build all figures and write HTML, PNG and the manifest.

    Raises FileExistsError (an output exists, no force), DirtyTreeError, FigureDataError (bad CSV data).
    Nothing is written if any of these is raised. With force, old PNGs that this run did not write are removed,
    and `slide_candidate` values in an existing manifest are carried over. Returns n_figures, png_failed (list), git_commit.
    PNG export problems do not raise: they are listed in `png_failed` after the HTML files are written.
    """
    out_dir = out_dir or results_dir / "figures"
    names = [n for fid in FIGURE_IDS for n in output_names(fid)] + [PLOTLY_JS_FILE, MANIFEST_FILE]
    existing = [out_dir / n for n in names if (out_dir / n).exists()]
    if existing and not force:
        listed = ", ".join(str(p) for p in existing)
        raise FileExistsError(f"Output already exists: {listed}. Use --force to overwrite.")
    commit = check_git_clean(allow_dirty)
    built = build_all(results_dir)  # any data error stops here, before anything is written
    slide_candidates = read_slide_candidates(out_dir / MANIFEST_FILE)
    out_dir.mkdir(parents=True, exist_ok=True)
    for figure_id, (fig, _) in built.items():
        fig.write_html(str(out_dir / output_names(figure_id)[0]), include_plotlyjs="directory")  # one shared plotly.min.js next to the HTML files
    png_written: set[str] = set()
    png_failed: list[str] = []
    if write_png_files:
        for index, (figure_id, (fig, _)) in enumerate(built.items()):
            try:
                write_png(fig, out_dir / output_names(figure_id)[1])
                png_written.add(figure_id)
            except Exception as error:  # noqa: BLE001 - kaleido raises several kinds of errors
                png_failed = list(built)[index:]
                print(f"PNG export failed for {figure_id}: {type(error).__name__}: {error}")
                break
    for figure_id in FIGURE_IDS:  # a PNG from an earlier run must not sit beside new HTML
        stale = out_dir / output_names(figure_id)[1]
        if figure_id not in png_written and stale.exists():
            stale.unlink()
            print(f"Removed stale PNG (not written in this run): {stale}")
    rows = manifest_rows(built, results_dir, png_written, commit, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         slide_candidates)
    pd.DataFrame(rows, columns=MANIFEST_COLUMNS).to_csv(out_dir / MANIFEST_FILE, index=False)
    print(f"Wrote {len(built)} HTML files, {len(png_written)} PNG files and {MANIFEST_FILE} to {out_dir}")
    print(f"Figure code commit: {commit}")
    return {"n_figures": len(built), "png_failed": png_failed, "git_commit": commit}


def cli(argv: Sequence[str] | None = None) -> int:
    """Command line entry point. Returns the exit code (0 = ok, 1 = refused or PNG export failed)."""
    parser = argparse.ArgumentParser(description="Make the main figures from the result CSVs.")
    parser.add_argument("--force", action="store_true", help="overwrite existing figure files")
    parser.add_argument("--allow-dirty", action="store_true", help="allow uncommitted changes (test runs only)")
    parser.add_argument("--no-png", action="store_true", help="write only HTML and the manifest")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR, help="folder with the result CSVs")
    parser.add_argument("--out-dir", type=Path, default=None, help="folder for the figures (default: RESULTS_DIR/figures)")
    args = parser.parse_args(argv)
    try:
        result = main(args.results_dir, args.out_dir, args.force, args.allow_dirty, write_png_files=not args.no_png)
    except (FileExistsError, FigureDataError, DirtyTreeError) as error:
        print(f"ERROR: {error}")
        return 1
    if result["png_failed"]:
        print(f"ERROR: {PNG_HELP}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())

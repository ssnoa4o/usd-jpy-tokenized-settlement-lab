"""Live dashboard engine (Day 15). Pure functions: no streamlit, nothing is written to disk.

`run_live` runs the real engine (transactions -> simulator -> metrics, through
`experiments.run_one`) for a few seeds. The same transactions of one seed feed every
selected model. A live run is exploratory: it is not an experiment of the study and
produces no hypothesis verdict. Recorded verdicts are only READ from results/*.csv.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src import experiments, transactions
from src.experiments import (
    ARRIVAL, CALIBRATION_FILE, COUNT, DELAY_SECONDS, FX_RATE, N_BANKS, RESULTS_DIR,
    ExpCondition,
)
from src.figures import MODEL_COLORS, MODEL_NAMES, MODEL_ORDER, MODEL_SHORT, SYNTHETIC_NOTE
from src.simulator import Model

LIVE_EXPERIMENT = "live_dashboard"
MAX_SEEDS = 30
VERDICTS_FILE = "verdicts.csv"
H3_VERDICTS_FILE = "h3_verdicts.csv"

# Metrics shown in the summary table: (metric, label with unit).
METRIC_LABELS = (
    ("success_rate", "Success rate"),
    ("partial_rate", "Partial rate"),
    ("failure_rate", "Failure rate"),
    ("principal_exposure_usd", "Principal exposure (USD)"),
    ("principal_exposure_usd_seconds", "Principal exposure x time (USD-seconds)"),
    ("gross_prefunding_usd", "Gross prefunding / validated amount (USD)"),
    ("liquidity_utilization", "Liquidity utilization"),
    ("peak_liquidity_proxy_usd", "Peak liquidity proxy (USD)"),
    ("average_settlement_time_seconds", "Average settlement time (s)"),
)
SUMMARY_COLUMNS = ["model", "metric", "n_seeds", "n_valid", "mean", "min", "max"]

GENERAL_VERDICT_NOTE = (
    "Verdicts are read from results/verdicts.csv and results/h3_verdicts.csv (30 seeds, synthetic "
    "data, simplified own models). They were computed by code committed before the main runs and "
    "are not recomputed here. 'supported' / 'not supported' / 'inconclusive' refer to decision "
    "rules fixed before the main runs, not to statistical tests."
)

MODEL_RULES_NOTE = (
    "For the arrival comparison, L* is identical in every seed for A and C; this may follow from "
    "the model rules (unverified reading)."
)
H3_CAVEAT = (
    "Verdict on this grid only: the JPY grid is coarse between multipliers 1 and 0.09375. "
    "Range rule on 30 seeds, not a statistical test."
)
VERDICT_NOTES = {
    "H1a": "Descriptive only; no decision rule and no verdict.",
    "H1b": (
        "The direction is largely design-driven: Model B reserves both legs at arrival, so it cannot "
        "have a second-leg insufficient_funds partial. Not independent evidence about B. "
        "JPY-only liquidity stress."
    ),
    "H2": (
        "The direction can be anticipated from the reservation rule (B holds the JPY leg from "
        "arrival). Peak Liquidity is a proxy and ignores netting and credit."
    ),
    "H4a": (
        "Success Rate of A equals that of C in all 150 (level, seed) pairs of the liquidity stress "
        "experiment (Exp3). This may follow from the model rules rather than from the stress "
        "(unverified reading). JPY-only liquidity stress."
    ),
    "H4b": "Mixed signs across seeds at the highest stress; the rule gives no verdict in either direction.",
    "H3": H3_CAVEAT,
}
VERDICT_HYPOTHESES = ("H1a", "H1b", "H2", "H4a", "H4b")
BANKS_NOTE = (
    "Liquidity is set per bank, so adding banks also adds total liquidity; the banks factor is not "
    "a pure participant-number effect."
)
H3_MODEL_RULES_MODELS = ("sequential", "atomic")

LIVE_NOTES = [
    "Live exploratory run: not one of the recorded experiments. Nothing is saved and no hypothesis "
    "verdict is computed from it.",
    "Model C (Atomic PvP) has partial = 0 and principal exposure = 0 by design (validate both legs, "
    "then one commit). This is a property of the model, not evidence.",
    "Gross prefunding is not peak liquidity. For Model C the 'gross prefunding' value is the amount "
    "that passed validation (counted even if the commit then fails), not funds locked in advance.",
    "Peak liquidity is a proxy; it ignores netting and credit.",
    "Synthetic data and simplified own models; independent research prototype.",
]

# Count columns shown in the status / reason table: (column, label).
REASON_COLUMNS = (
    ("n_settled", "settled"), ("n_partial", "partial"), ("n_failed", "failed"),
    ("n_insufficient_funds", "insufficient_funds (all)"),
    ("n_technical_failure", "technical_failure (all)"),
    ("n_timeout", "timeout (all)"),
    ("n_partial_insufficient_funds", "partial: insufficient_funds"),
    ("n_partial_technical_failure", "partial: technical_failure"),
    ("n_partial_timeout", "partial: timeout"),
    ("n_failed_insufficient_funds", "failed: insufficient_funds"),
    ("n_failed_technical_failure", "failed: technical_failure"),
    ("n_failed_timeout", "failed: timeout"),
)  # fmt: skip


# ------------------------------------------------------------------ inputs


@dataclass(frozen=True)
class LiveInputs:
    """Everything a live run needs. Defaults are the Exp1 baseline."""

    initial_usd: float
    initial_jpy: float
    fx_rate: float = FX_RATE
    count: int = COUNT
    n_banks: int = N_BANKS
    arrival: str = ARRIVAL
    models: tuple[str, ...] = ("sequential", "prefunded", "atomic")
    failure_probability: float = 0.01
    delay_seconds: float = DELAY_SECONDS
    first_seed: int = 1
    n_seeds: int = 5

    def __post_init__(self) -> None:
        """Check only what the engine does not check itself."""
        valid = {model.value for model in Model}
        if not self.models:
            raise ValueError("Select at least one settlement model.")
        if any(model not in valid for model in self.models):
            raise ValueError(f"Unknown model in {self.models!r}. Valid models: {sorted(valid)}.")
        if len(set(self.models)) != len(self.models):
            raise ValueError("Each model can be selected only once.")
        if isinstance(self.n_seeds, bool) or not isinstance(self.n_seeds, int) or self.n_seeds < 1:
            raise ValueError("Number of seeds must be an integer >= 1.")
        if self.n_seeds > MAX_SEEDS:
            raise ValueError(f"Number of seeds must be at most {MAX_SEEDS}.")
        if isinstance(self.first_seed, bool) or not isinstance(self.first_seed, int) or self.first_seed < 0:
            raise ValueError("First seed must be an integer >= 0.")

    @property
    def seeds(self) -> range:
        """The seeds of this run."""
        return range(self.first_seed, self.first_seed + self.n_seeds)


def reference_balances(results_dir: Path = RESULTS_DIR) -> tuple[int, int]:
    """Reference (USD, JPY) per bank, read from calibration.csv."""
    return experiments.read_reference(results_dir / CALIBRATION_FILE)


def default_inputs(results_dir: Path = RESULTS_DIR) -> LiveInputs:
    """Exp1 baseline inputs; the balances come from the calibration file."""
    usd, jpy = reference_balances(results_dir)
    return LiveInputs(initial_usd=float(usd), initial_jpy=float(jpy))


# ------------------------------------------------------------------ run


def run_live(inputs: LiveInputs) -> pd.DataFrame:
    """Run the real engine; one row per (seed, model). Writes nothing to disk.

    Transactions are generated once per seed and shared by all selected models.
    """
    condition = ExpCondition(
        name="live", failure_probability=inputs.failure_probability,
        experiment=LIVE_EXPERIMENT, delay_seconds=inputs.delay_seconds, ample=False,
    )  # fmt: skip
    selected = [name for name in MODEL_ORDER if name in inputs.models]
    rows: list[dict[str, object]] = []
    for seed in inputs.seeds:
        data = transactions.generate_transactions(
            count=inputs.count, fx_rate=inputs.fx_rate, seed=seed,
            n_banks=inputs.n_banks, arrival=inputs.arrival,
        )  # fmt: skip
        for name in selected:
            row = experiments.run_one(
                data, Model(name), condition, seed, inputs.initial_usd, inputs.initial_jpy,
                inputs.count, inputs.n_banks, inputs.delay_seconds, inputs.arrival,
            )  # fmt: skip
            row["fx_rate"] = inputs.fx_rate
            rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ tables


def summarize_live(runs: pd.DataFrame) -> pd.DataFrame:
    """Long table per (model, metric): n_seeds, n_valid, mean, min, max. NaN stays NaN."""
    rows: list[dict[str, object]] = []
    for name in MODEL_ORDER:
        group = runs[runs["model"] == name]
        if group.empty:
            continue
        for metric, _ in METRIC_LABELS:
            column = group[metric].astype(float)
            rows.append({
                "model": name, "metric": metric, "n_seeds": len(column),
                "n_valid": int(column.notna().sum()), "mean": column.mean(),
                "min": column.min(), "max": column.max(),
            })  # fmt: skip
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def range_text(low: float, high: float) -> str:
    """'min - max' as text, or 'n/a' if there is no valid value."""
    if math.isnan(low) or math.isnan(high):
        return "n/a"
    return f"{low:,.4g} - {high:,.4g}"


def summary_table(summary: pd.DataFrame) -> pd.DataFrame:
    """Wide table: one row per metric, one column per model (value = mean over seeds)."""
    models = [name for name in MODEL_ORDER if name in set(summary["model"])]
    rows = []
    for metric, label in METRIC_LABELS:
        row: dict[str, object] = {"Metric": label}
        for name in models:
            cell = summary[(summary["model"] == name) & (summary["metric"] == metric)].iloc[0]
            row[MODEL_NAMES[name]] = cell["mean"]
        rows.append(row)
    return pd.DataFrame(rows)


def range_table(summary: pd.DataFrame) -> pd.DataFrame:
    """Same shape as summary_table, but each cell is the min - max text over seeds."""
    models = [name for name in MODEL_ORDER if name in set(summary["model"])]
    rows = []
    for metric, label in METRIC_LABELS:
        row: dict[str, object] = {"Metric": label}
        for name in models:
            cell = summary[(summary["model"] == name) & (summary["metric"] == metric)].iloc[0]
            row[MODEL_NAMES[name]] = range_text(cell["min"], cell["max"])
        rows.append(row)
    return pd.DataFrame(rows)


# How each metric is written on screen. Display only: the tables keep the exact numbers.
METRIC_FORMATS = {
    "success_rate": "{:.1%}",
    "partial_rate": "{:.1%}",
    "failure_rate": "{:.1%}",
    "principal_exposure_usd": "{:,.0f}",
    "principal_exposure_usd_seconds": "{:,.0f}",
    "gross_prefunding_usd": "{:,.0f}",
    "liquidity_utilization": "{:.1%}",
    "peak_liquidity_proxy_usd": "{:,.0f}",
    "average_settlement_time_seconds": "{:,.1f}",
}
NOT_AVAILABLE = "n/a"

# Metrics of the comparison at the top of the live tab: (metric, column heading).
HEADLINE_METRICS = (
    ("success_rate", "Success rate"),
    ("partial_rate", "Partial rate"),
    ("failure_rate", "Failure rate"),
    ("principal_exposure_usd", "Principal exposure (USD)"),
    ("peak_liquidity_proxy_usd", "Peak liquidity proxy (USD)"),
)


def format_value(metric: str, value: float) -> str:
    """One metric value as display text. NaN becomes 'n/a' (never 0)."""
    if value is None or math.isnan(value):
        return NOT_AVAILABLE
    pattern = METRIC_FORMATS[metric]
    text = pattern.format(value)
    # Rounding must not hide a real difference: a small non-zero value is not shown as zero,
    # and a share just below 100% is not shown as 100%.
    if value > 0 and text == pattern.format(0):
        return "<" + pattern.format(_smallest_step(pattern))
    if pattern.endswith("%}") and value < 1 and text == pattern.format(1):
        return ">" + pattern.format(1 - _smallest_step(pattern))
    return text


def _smallest_step(pattern: str) -> float:
    """The smallest value a display pattern can show: 0.001 for '{:.1%}', 1 for '{:,.0f}', 0.1 for '{:,.1f}'."""
    digits = int(pattern.split(".")[1][0])
    return 10.0 ** -(digits + 2) if pattern.endswith("%}") else 10.0 ** -digits


def headline_rows(summary: pd.DataFrame) -> list[dict[str, object]]:
    """One dict per model for the comparison at the top: mean values as numbers and as text."""
    rows: list[dict[str, object]] = []
    for name in MODEL_ORDER:
        if name not in set(summary["model"]):
            continue
        values = {metric: _value(summary, name, metric, "mean") for metric, _ in HEADLINE_METRICS}
        rows.append({
            "model": name, "name": MODEL_NAMES[name], "color": MODEL_COLORS[name], "values": values,
            "text": {metric: format_value(metric, value) for metric, value in values.items()},
        })  # fmt: skip
    return rows


def reason_table(runs: pd.DataFrame) -> pd.DataFrame:
    """Counts by status and failure reason, summed over seeds. One row per model."""
    rows = []
    for name in MODEL_ORDER:
        group = runs[runs["model"] == name]
        if group.empty:
            continue
        row: dict[str, object] = {"Model": MODEL_NAMES[name]}
        for column, label in REASON_COLUMNS:
            row[label] = int(group[column].sum())
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ figure


def _value(summary: pd.DataFrame, model: str, metric: str, column: str) -> float:
    """One number from the summary table."""
    cell = summary[(summary["model"] == model) & (summary["metric"] == metric)]
    return float(cell.iloc[0][column])


def _none_if_nan(value: float) -> float | None:
    """Plotly draws no bar for None (a NaN must never become a 0 bar)."""
    return None if math.isnan(value) else value


def _whisker(summary: pd.DataFrame, model: str, metric: str) -> tuple[float | None, float | None]:
    """Distances from the mean down to min and up to max (None if not available)."""
    mean = _value(summary, model, metric, "mean")
    low = _value(summary, model, metric, "min")
    high = _value(summary, model, metric, "max")
    if math.isnan(mean) or math.isnan(low) or math.isnan(high):
        return None, None
    return mean - low, high - mean


def build_live_figure(summary: pd.DataFrame) -> go.Figure:
    """1 x 3 panels: outcome rates, principal exposure (USD), peak liquidity proxy (USD)."""
    models = [name for name in MODEL_ORDER if name in set(summary["model"])]
    n_seeds = int(summary["n_seeds"].max()) if len(summary) else 0
    fig = make_subplots(
        rows=1, cols=3, horizontal_spacing=0.09,
        subplot_titles=("Settlement outcome rates", "Principal exposure (USD)", "Peak liquidity proxy (USD)"),
    )  # fmt: skip
    outcomes = (("success_rate", "Success"), ("partial_rate", "Partial"), ("failure_rate", "Failure"))
    for name in models:
        means = [_none_if_nan(_value(summary, name, metric, "mean")) for metric, _ in outcomes]
        fig.add_trace(go.Bar(
            x=[label for _, label in outcomes], y=means, name=MODEL_NAMES[name],
            marker_color=MODEL_COLORS[name], legendgroup=name,
        ), row=1, col=1)  # fmt: skip
    for col, metric in ((2, "principal_exposure_usd"), (3, "peak_liquidity_proxy_usd")):
        for name in models:
            below, above = _whisker(summary, name, metric)
            error = None if below is None else {"type": "data", "symmetric": False,
                                                "array": [above], "arrayminus": [below]}  # fmt: skip
            fig.add_trace(go.Bar(
                x=[MODEL_SHORT[name]], y=[_none_if_nan(_value(summary, name, metric, "mean"))],
                marker_color=MODEL_COLORS[name], name=MODEL_NAMES[name], legendgroup=name,
                showlegend=False, error_y=error,
            ), row=1, col=col)  # fmt: skip
    fig.update_yaxes(range=[0, 1], tickformat=".0%", row=1, col=1)
    fig.update_xaxes(tickangle=0)
    fig.update_layout(
        title=f"Live exploratory run ({n_seeds} seeds). {SYNTHETIC_NOTE}",
        barmode="group", height=480, template="plotly_white",
        legend={"orientation": "h", "y": -0.2},
    )  # fmt: skip
    return fig


# ------------------------------------------------------------------ recorded verdicts


def read_checked(path: Path, columns: list[str]) -> pd.DataFrame:
    """Read a CSV; ValueError if it is missing or lacks a needed column."""
    if not path.exists():
        raise ValueError(f"Verdict file not found: {path}")
    table = pd.read_csv(path)
    missing = [column for column in columns if column not in table.columns]
    if missing:
        raise ValueError(f"{path.name} has no column(s) {missing}")
    return table


def h3_caveat(factor: str, model: str) -> str:
    """Caveat text of one H3 row."""
    if factor == "arrival" and model in H3_MODEL_RULES_MODELS:
        return f"{VERDICT_NOTES['H3']} {MODEL_RULES_NOTE}"
    if factor == "banks":
        return f"{VERDICT_NOTES['H3']} {BANKS_NOTE}"
    return VERDICT_NOTES["H3"]


def load_verdict_tables(results_dir: Path = RESULTS_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recorded verdicts (read only, never recomputed): (H1a-H4b table, H3 table)."""
    main = read_checked(results_dir / VERDICTS_FILE, ["hypothesis", "role", "verdict", "note"])
    overall = main[main["role"] == "overall"]
    rows = []
    for hypothesis in VERDICT_HYPOTHESES:
        found = overall[overall["hypothesis"] == hypothesis]
        if found.empty:
            raise ValueError(f"{VERDICTS_FILE} has no 'overall' row for {hypothesis}")
        row = found.iloc[0]
        verdict = row["verdict"]
        if pd.isna(verdict) or str(verdict) == "":
            verdict = "descriptive only, no verdict"
        rows.append({"hypothesis": hypothesis, "verdict": str(verdict),
                     "note": "" if pd.isna(row["note"]) else str(row["note"]),
                     "caveat": VERDICT_NOTES[hypothesis]})  # fmt: skip
    columns = ["factor", "model", "low_level", "high_level", "verdict", "n_seeds_equal", "note"]
    h3 = read_checked(results_dir / H3_VERDICTS_FILE, ["role", *columns])
    decides = h3[h3["role"] == "decides"][columns].reset_index(drop=True)
    decides["caveat"] = [h3_caveat(str(f), str(m)) for f, m in zip(decides["factor"], decides["model"])]
    return pd.DataFrame(rows), decides

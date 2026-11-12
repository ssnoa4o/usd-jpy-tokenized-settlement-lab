"""Experiments. Day 11: Exp1 Baseline; Day 12: Exp3 + Exp4 stress (methodology sec. 4-8).

Run with: python -m src.experiments baseline [--force] [--allow-dirty]

Exp1 runs Models A, B and C on the same synthetic transactions (one data set per seed,
shared by the three models) for seeds 1-30 and two conditions:
- `baseline`:    failure probability 0.01
- `sanity_0pct`: failure probability 0.0 (a correctness check, not evidence)
Both use 500 transactions, 2 banks, sequential arrival, delay 60 s, cutoff 3600 s.
The reference balances come from results/calibration.csv (the run is refused if the
calibration did not succeed). 2 conditions x 3 models x 30 seeds = 180 runs.

Output files (in the results directory):
- run_metrics.csv     one row per run: experiment, condition, model, seed, parameters,
                      every calculate_metrics column, git_commit, run_utc. NaN is empty.
- baseline_results.csv  LONG format, one row per (condition, model, metric):
                      columns condition, model, metric, n_seeds, n_valid, mean, min, max.
                      n_seeds = number of seeds (runs); n_valid = how many of them have a
                      non-NaN value. mean / min / max use only the n_valid values.
- summary.csv         the same table with a leading `experiment` column (Day 12 appends).
- experiment_log.csv  APPEND-ONLY: one row per run. Existing rows are never rewritten,
                      also with --force (only run_metrics / baseline_results / summary
                      are overwritten then). Columns:
                      run_utc,experiment,model,seeds,parameters,git_commit,status,note

Aggregation: mean / min / max over seeds ignore NaN values; a metric that is NaN in
every seed stays NaN (e.g. Model A gross prefunding, n_valid = 0). It is never turned
into 0.

Safety rules:
- The run is refused (exit code 1) if git_version() ends with "-dirty", unless
  allow_dirty=True / --allow-dirty is given. The real run must be from a clean commit.
- Existing run_metrics.csv, baseline_results.csv or summary.csv is never overwritten
  without force.

Self-checks (design guarantees, so correctness tests and NOT evidence) raise
RuntimeError. The ample check is different and is never hidden by a self-check: if any
run has insufficient_funds > 0, that run gets status `ample_violated`, a warning is
printed and the run continues (main returns ample_violated=True). The reference is NOT
raised automatically (methodology sec. 6). In sanity_0pct only a partial caused by
technical_failure is a self-check error (it cannot happen at 0%); partials caused by
insufficient funds go through the ample path. The atomic model must have no partial, no
principal exposure and principal_exposure_usd_seconds == 0.

Day 13: `python -m src.experiments sensitivity [--force] [--allow-dirty]` runs Exp2 x Exp3
(6 factor cells x the JPY grid), see the "sensitivity" section below.

Day 12: `python -m src.experiments stress [--force] [--allow-dirty]` runs Exp3 (JPY
liquidity grid) and Exp4 (failure and delay levels, plus the H4b cells), see the
"stress" section below. The grid and the H4b level are read from results/calibration.csv.
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from src import metrics, simulator, transactions
from src.calibration import git_version, seeds_label
from src.simulator import Currency, Model, SimulationParams, to_minor

EXPERIMENT = "exp1_baseline"
MAIN_SEEDS = range(1, 31)
MODELS = (Model.SEQUENTIAL, Model.PREFUNDED, Model.ATOMIC)
COUNT = 500
N_BANKS = 2
ARRIVAL = "sequential"
DELAY_SECONDS = 60
CUTOFF_SECONDS = 3600
FX_RATE = 150.0  # generator default

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
CALIBRATION_FILE = "calibration.csv"
RUN_METRICS_FILE = "run_metrics.csv"
BASELINE_FILE = "baseline_results.csv"
SUMMARY_FILE = "summary.csv"
LOG_FILE = "experiment_log.csv"
LOG_COLUMNS = ["run_utc", "experiment", "model", "seeds", "parameters", "git_commit", "status", "note"]

# Metrics that go into baseline_results.csv / summary.csv.
SUMMARY_METRICS = (
    "success_rate", "partial_rate", "failure_rate",
    "principal_exposure_usd", "principal_exposure_usd_seconds",
    "gross_prefunding_usd", "liquidity_utilization", "peak_liquidity_proxy_usd",
    "average_settlement_time_seconds",
    "n_partial", "n_failed", "n_insufficient_funds", "n_technical_failure",
)  # fmt: skip
AGGREGATE_COLUMNS = ["condition", "model", "metric", "n_seeds", "n_valid", "mean", "min", "max"]
STATUS_OK = "ok"
STATUS_AMPLE_VIOLATED = "ample_violated"


class DirtyTreeError(RuntimeError):
    """Raised when the git working tree has uncommitted changes."""


@dataclass(frozen=True)
class ExpCondition:
    """One experiment cell.

    Exp1 conditions keep the defaults (delay 60 s, JPY multiplier 1, ample). Stress cells
    set `experiment`, `delay_seconds`, `jpy_multiplier` and `ample` (False = shortages of
    JPY are expected in this cell, so insufficient_funds is not an ample violation).
    """

    name: str
    failure_probability: float
    experiment: str = EXPERIMENT
    delay_seconds: float = DELAY_SECONDS
    jpy_multiplier: float = 1.0
    ample: bool = True


CONDITIONS = (ExpCondition("baseline", 0.01), ExpCondition("sanity_0pct", 0.0))


# ------------------------------------------------------------------ calibration

def read_reference(calibration_path: Path) -> tuple[int, int]:
    """Return (reference_usd, reference_jpy) from calibration.csv.

    ValueError if the file is missing, status is not "ok" or ample was not reached.
    """
    if not calibration_path.exists():
        raise ValueError(f"Calibration file not found: {calibration_path}. Run the calibration first.")
    row = pd.read_csv(calibration_path).iloc[0]
    if str(row["status"]) != "ok":
        raise ValueError(f"Calibration status is {row['status']!r}, not 'ok'. No main run may start.")
    if str(row["ample_reached"]) != "True":
        raise ValueError("Calibration did not reach the ample reference. No main run may start.")
    return int(row["reference_usd"]), int(row["reference_jpy"])


# ------------------------------------------------------------------ one run

def check_run(
    model: Model, condition: ExpCondition, row: dict[str, float],
    ledger: simulator.Ledger, params: SimulationParams,
) -> None:
    """Self-checks on one run. Raises RuntimeError on a violation (correctness tests only)."""
    label = f"{condition.name}/{model.value}/seed {params.seed}"
    if model == Model.ATOMIC and (
        row["n_partial"] != 0
        or row["principal_exposure_usd"] != 0
        or row["principal_exposure_usd_seconds"] != 0
    ):
        raise RuntimeError(f"{label}: atomic model has partial or principal exposure")
    rate_sum = row["success_rate"] + row["partial_rate"] + row["failure_rate"]
    if not math.isclose(rate_sum, 1.0):
        raise RuntimeError(f"{label}: rates sum to {rate_sum}, not 1")
    expected = {
        Currency.USD: params.n_banks * to_minor(params.initial_usd),
        Currency.JPY: params.n_banks * to_minor(params.initial_jpy),
    }
    for currency, amount in expected.items():
        if ledger.total(currency) != amount:
            raise RuntimeError(f"{label}: total {currency.value} over all banks changed")
    # Partials from insufficient funds are an ample violation (handled by run_status).
    if condition.failure_probability == 0 and row["n_partial_technical_failure"] != 0:
        raise RuntimeError(f"{label}: technical-failure partial with failure probability 0")


def run_one(
    data: pd.DataFrame, model: Model, condition: ExpCondition, seed: int,
    initial_usd: int, initial_jpy: int, count: int, n_banks: int, delay_seconds: float,
    arrival: str = ARRIVAL,
) -> dict[str, object]:
    """Run one model once, check it, and return one run_metrics row (without git / time).

    `arrival` only labels the row: the arrival pattern is already inside `data`.
    """
    params = SimulationParams(
        seed=seed, initial_usd=initial_usd, initial_jpy=initial_jpy,
        delay_seconds=delay_seconds, failure_probability=condition.failure_probability,
        cutoff_seconds=CUTOFF_SECONDS, n_banks=n_banks,
    )  # fmt: skip
    results, ledger = simulator.run_model(data, model, params)
    values = metrics.calculate_metrics(results, data, params, ledger)
    check_run(model, condition, values, ledger, params)
    return {
        "experiment": condition.experiment, "condition": condition.name, "model": model.value,
        "seed": seed, "count": count, "n_banks": n_banks, "arrival": arrival,
        "delay_seconds": delay_seconds, "failure_probability": condition.failure_probability,
        "initial_usd": initial_usd, "initial_jpy": initial_jpy,
        **values,
    }  # fmt: skip


def run_status(row: dict[str, object], ample: bool = True) -> str:
    """`ample_violated` if an ample cell has insufficient funds, else `ok`.

    In a non-ample (stress) cell shortages are expected, so the status is always `ok`.
    """
    if ample and row["n_insufficient_funds"] > 0:
        return STATUS_AMPLE_VIOLATED
    return STATUS_OK


def run_all(
    initial_usd: int, initial_jpy: int,
    seeds: Sequence[int] = MAIN_SEEDS, count: int = COUNT, n_banks: int = N_BANKS,
    delay_seconds: float = DELAY_SECONDS, conditions: Sequence[ExpCondition] = CONDITIONS,
) -> pd.DataFrame:
    """Run every (condition, seed, model). Transactions are generated once per seed.

    Returns the run_metrics table plus `status`, `git_commit` and `run_utc` columns.
    """
    commit = git_version()
    rows: list[dict[str, object]] = []
    for seed in seeds:
        data = transactions.generate_transactions(
            count=count, fx_rate=FX_RATE, seed=seed, n_banks=n_banks, arrival=ARRIVAL
        )
        for condition in conditions:
            for model in MODELS:
                row = run_one(data, model, condition, seed, initial_usd, initial_jpy,
                              count, n_banks, delay_seconds)  # fmt: skip
                row["status"] = run_status(row)
                row["git_commit"] = commit
                row["run_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ outputs

def aggregate(runs: pd.DataFrame) -> pd.DataFrame:
    """Long table: n_seeds, n_valid (non-NaN), mean, min, max per (condition, model, metric). NaN stays NaN."""
    rows: list[dict[str, object]] = []
    for (condition, model), group in runs.groupby(["condition", "model"], sort=False):
        for metric in SUMMARY_METRICS:
            column = group[metric].astype(float)
            rows.append({
                "condition": condition, "model": model, "metric": metric,
                "n_seeds": len(column), "n_valid": int(column.notna().sum()), "mean": column.mean(),
                "min": column.min(), "max": column.max(),
            })  # fmt: skip
    return pd.DataFrame(rows, columns=AGGREGATE_COLUMNS)


def parameters_text(row: pd.Series) -> str:
    """Parameters of one run as 'key=value;key=value'."""
    keys = ["condition", "count", "n_banks", "arrival", "delay_seconds", "failure_probability",
            "initial_usd", "initial_jpy", "cutoff_seconds"]  # fmt: skip
    if "jpy_multiplier" in row.index:  # stress rows only; Exp1 text stays unchanged
        keys.append("jpy_multiplier")
    return ";".join(f"{key}={row[key]}" for key in keys)


def log_rows(runs: pd.DataFrame) -> list[list[str]]:
    """One experiment_log row per run (columns as in LOG_COLUMNS)."""
    rows = []
    for _, run in runs.iterrows():
        note = ""
        if run["status"] == STATUS_AMPLE_VIOLATED:
            note = f"insufficient_funds={int(run['n_insufficient_funds'])}; ample reference violated"
        rows.append([
            run["run_utc"], run["experiment"], run["model"], str(run["seed"]),
            parameters_text(run), run["git_commit"], run["status"], note,
        ])  # fmt: skip
    return rows


def append_log(log_path: Path, rows: list[list[str]]) -> None:
    """Append rows to the log. Create the file with the header if it does not exist."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not log_path.exists() or log_path.stat().st_size == 0
    needs_newline = False
    if not new_file:
        with open(log_path, "rb") as handle:
            handle.seek(-1, 2)
            needs_newline = handle.read(1) not in (b"\n", b"\r")
    with open(log_path, "a", newline="", encoding="utf-8") as handle:
        if needs_newline:
            handle.write("\n")
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(LOG_COLUMNS)
        writer.writerows(rows)


def write_outputs(runs: pd.DataFrame, results_dir: Path) -> None:
    """Write run_metrics, baseline_results and summary (overwrite) and append the log."""
    results_dir.mkdir(parents=True, exist_ok=True)
    table = aggregate(runs)
    runs.drop(columns=["status"]).to_csv(results_dir / RUN_METRICS_FILE, index=False, na_rep="")
    table.to_csv(results_dir / BASELINE_FILE, index=False, na_rep="")
    table.insert(0, "experiment", EXPERIMENT)
    table.to_csv(results_dir / SUMMARY_FILE, index=False, na_rep="")
    append_log(results_dir / LOG_FILE, log_rows(runs))


# ------------------------------------------------------------------ main

def check_git_clean(allow_dirty: bool) -> str:
    """Return the git version. Raise DirtyTreeError if dirty and not allowed; warn if allowed."""
    commit = git_version()
    if commit.endswith("-dirty"):
        if not allow_dirty:
            raise DirtyTreeError(
                f"Git working tree has uncommitted changes ({commit}). Commit first, "
                "or use --allow-dirty for a test run."
            )
        print("WARNING: git working tree has uncommitted changes. The real run must be from a clean commit.")
    return commit


def main(
    results_dir: Path = RESULTS_DIR, calibration_path: Path | None = None, force: bool = False,
    seeds: Sequence[int] = MAIN_SEEDS, count: int = COUNT, allow_dirty: bool = False,
) -> dict[str, object]:
    """Run Exp1 Baseline and write the files.

    Raises ValueError (bad calibration), FileExistsError (output exists, no force) or
    DirtyTreeError (uncommitted changes, no allow_dirty).
    Returns a small dict: n_runs, ample_violated, git_commit.
    """
    calibration_path = calibration_path or results_dir / CALIBRATION_FILE
    existing = [results_dir / n for n in (RUN_METRICS_FILE, BASELINE_FILE, SUMMARY_FILE) if (results_dir / n).exists()]
    if existing and not force:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"Output already exists: {names}. Use --force to overwrite.")
    usd, jpy = read_reference(calibration_path)
    commit = check_git_clean(allow_dirty)
    runs = run_all(usd, jpy, seeds=seeds, count=count)
    violated = runs[runs["status"] == STATUS_AMPLE_VIOLATED]
    if len(violated) > 0:
        print(f"WARNING: ample reference violated in {len(violated)} run(s) (insufficient_funds > 0).")
        print("Do not change the reference silently: follow methodology sec. 6.")
    write_outputs(runs, results_dir)
    print(f"Exp1 baseline: {len(runs)} runs, seeds {seeds_label(list(seeds))}, commit {commit}")
    print(f"Ample violated: {len(violated) > 0}")
    print(f"Wrote {results_dir / RUN_METRICS_FILE}, {results_dir / BASELINE_FILE}, "
          f"{results_dir / SUMMARY_FILE}; appended {len(runs)} rows to {results_dir / LOG_FILE}")  # fmt: skip
    return {"n_runs": len(runs), "ample_violated": len(violated) > 0, "git_commit": commit}


# ------------------------------------------------------------------ stress (Exp3 + Exp4)

STRESS_RUN_METRICS_FILE = "stress_run_metrics.csv"
STRESS_RESULTS_FILE = "stress_test_results.csv"
EXP3 = "exp3_liquidity"
EXP4_FAILURE = "exp4_failure"
EXP4_DELAY = "exp4_delay"
EXP4_H4B = "exp4_h4b"
STRESS_FAILURE_PROBABILITY = 0.01  # failure level of Exp3, Exp4 delay and H4b cells
EXP4_FAILURE_LEVELS = (0.0, 0.01, 0.05)
EXP4_DELAY_LEVELS = (0, 300)  # 60 s at 1% is the cell failure_0.01 of exp4_failure (shared)
H4B_DELAY_LEVELS = (0, 60, 300)
SHARED_CELL_NOTE = (
    "The Exp4 delay level 60 s (failure 1%, ample) is the cell exp4_failure/failure_0.01. "
    "It is not run a second time; verdict code reads it from there."
)


@dataclass(frozen=True)
class StressLevels:
    """Liquidity levels read from calibration.csv: lower JPY multipliers and the H4b level."""

    lower_multipliers: tuple[float, ...]
    h4b_multiplier: float | None  # None if H4b is not testable
    h4b_skip_reason: str  # empty if H4b cells are run


def read_stress_levels(calibration_path: Path) -> StressLevels:
    """Read the JPY grid and the H4b level from calibration.csv (never hard-coded).

    ValueError if the calibration did not succeed (see read_reference) or a column is missing.
    """
    read_reference(calibration_path)  # same checks as Exp1: file exists, status ok, ample reached
    row = pd.read_csv(calibration_path).iloc[0]
    for column in ("lower_multipliers", "h4b_multiplier", "h4b_testable"):
        if column not in row.index:
            raise ValueError(f"Calibration file has no column {column!r}.")
    lower = tuple(float(text) for text in str(row["lower_multipliers"]).split())
    if not lower:
        raise ValueError("Calibration file has no lower multipliers.")
    if str(row["h4b_testable"]) != "True" or pd.isna(row["h4b_multiplier"]):
        return StressLevels(lower, None, f"h4b_testable is {str(row['h4b_testable'])!r} in the calibration")
    return StressLevels(lower, float(row["h4b_multiplier"]), "")


def level_text(value: float) -> str:
    """Short stable text for a number in a condition name: 1.0 -> '1', 0.09375 -> '0.09375'."""
    return f"{value:g}"


def stress_conditions(levels: StressLevels) -> list[ExpCondition]:
    """All stress cells (13 when H4b is testable), in a fixed order.

    Exp3: JPY multiplier 1 (ample) and the lower multipliers, failure 1%, delay 60 s.
    Exp4 failure: failure 0 / 1 / 5%, delay 60 s, ample.
    Exp4 delay: delay 0 and 300 s at failure 1%, ample (60 s is shared, see SHARED_CELL_NOTE).
    Exp4 H4b: delay 0 / 60 / 300 s at failure 1%, JPY multiplier = H4b level, not ample.
    """
    cells = [
        ExpCondition(f"jpy_{level_text(m)}", STRESS_FAILURE_PROBABILITY, EXP3, DELAY_SECONDS, m, m == 1.0)
        for m in (1.0, *levels.lower_multipliers)
    ]
    cells += [ExpCondition(f"failure_{level_text(p)}", p, EXP4_FAILURE) for p in EXP4_FAILURE_LEVELS]
    cells += [ExpCondition(f"delay_{level_text(d)}", STRESS_FAILURE_PROBABILITY, EXP4_DELAY, d)
              for d in EXP4_DELAY_LEVELS]  # fmt: skip
    if levels.h4b_multiplier is not None:
        cells += [
            ExpCondition(f"h4b_delay_{level_text(d)}", STRESS_FAILURE_PROBABILITY, EXP4_H4B, d,
                         levels.h4b_multiplier, False)
            for d in H4B_DELAY_LEVELS
        ]
    return cells


def initial_jpy_for(reference_jpy: int, multiplier: float) -> int:
    """Initial JPY of a cell: reference x multiplier, rounded to a whole yen (major units)."""
    return round(reference_jpy * multiplier)


def run_stress_all(
    initial_usd: int, reference_jpy: int, conditions: Sequence[ExpCondition],
    seeds: Sequence[int] = MAIN_SEEDS, count: int = COUNT, n_banks: int = N_BANKS,
) -> pd.DataFrame:
    """Run every (seed, cell, model). Transactions are generated once per seed and reused.

    Returns run rows plus `jpy_multiplier`, `ample_cell`, `status`, `git_commit`, `run_utc`.
    Self-checks over all runs (check_stress) run at the end.
    """
    commit = git_version()
    rows: list[dict[str, object]] = []
    for seed in seeds:
        data = transactions.generate_transactions(
            count=count, fx_rate=FX_RATE, seed=seed, n_banks=n_banks, arrival=ARRIVAL
        )
        for condition in conditions:
            jpy = initial_jpy_for(reference_jpy, condition.jpy_multiplier)
            for model in MODELS:
                row = run_one(data, model, condition, seed, initial_usd, jpy,
                              count, n_banks, condition.delay_seconds)  # fmt: skip
                row["jpy_multiplier"] = condition.jpy_multiplier
                row["ample_cell"] = condition.ample
                row["status"] = run_status(row, condition.ample)
                row["git_commit"] = commit
                row["run_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                rows.append(row)
    runs = pd.DataFrame(rows)
    check_stress(runs)
    # Put the two stress columns right after initial_jpy.
    columns = [c for c in runs.columns if c not in ("jpy_multiplier", "ample_cell")]
    position = columns.index("initial_jpy") + 1
    return runs[columns[:position] + ["jpy_multiplier", "ample_cell"] + columns[position:]]


def check_stress(runs: pd.DataFrame) -> None:
    """Cross-run self-checks (design guarantees = correctness tests, NOT evidence). RuntimeError.

    A seed / model with insufficient_funds > 0 is skipped by the checks that need "no
    insufficient funds" (the shortage is reported through the ample path, not hidden here).
    1. Ample cell, per seed: if A and B both have no insufficient_funds, their
       principal_exposure_usd is equal (methodology sec. 7).
    2. exp4_failure, per seed and model A / B with no insufficient_funds in the three
       cells: exposure does not fall 0% -> 1% -> 5% (nested failure draws).
    3. exp4_failure, over seeds (aggregate): the MEAN exposure at 5% is higher than at 0%.
       The sec. 7 test says "with 500 transactions it is higher at 5% than at 0%". Read per
       seed it could in principle fail by chance (no hit in a seed); the mean over the
       eligible seeds cannot, so the aggregate reading is used. Skipped if no seed is eligible.
    Exposure values are sums of cents (math.fsum, order independent), so exact equality is used.
    The 0% cell having no technical-failure partial is already checked in check_run.
    """
    ample = runs[runs["ample_cell"]]
    for (_, condition, seed), group in ample.groupby(["experiment", "condition", "seed"], sort=False):
        a = group[group["model"] == Model.SEQUENTIAL.value].iloc[0]
        b = group[group["model"] == Model.PREFUNDED.value].iloc[0]
        if a["n_insufficient_funds"] == 0 and b["n_insufficient_funds"] == 0 and (
            a["principal_exposure_usd"] != b["principal_exposure_usd"]
        ):
            raise RuntimeError(f"{condition}/seed {seed}: A and B exposure differ without insufficient funds")
    cells = runs[runs["experiment"] == EXP4_FAILURE]
    if cells.empty:
        return
    for model in (Model.SEQUENTIAL, Model.PREFUNDED):
        eligible_exposure = []  # per eligible seed: exposure at each failure level, in level order
        for seed, group in cells[cells["model"] == model.value].groupby("seed", sort=False):
            group = group.sort_values("failure_probability")
            if (group["n_insufficient_funds"] > 0).any():
                continue  # shortage in this seed: skip (reported through the ample status)
            exposure = group["principal_exposure_usd"].tolist()
            if any(later < earlier for earlier, later in zip(exposure, exposure[1:])):
                raise RuntimeError(f"{model.value}/seed {seed}: exposure falls as failure probability rises")
            eligible_exposure.append(exposure)
        if eligible_exposure:
            low = math.fsum(e[0] for e in eligible_exposure) / len(eligible_exposure)
            high = math.fsum(e[-1] for e in eligible_exposure) / len(eligible_exposure)
            if not high > low:
                raise RuntimeError(f"{model.value}: mean exposure at the highest failure level is not above the lowest")


def aggregate_stress(runs: pd.DataFrame) -> pd.DataFrame:
    """Long table with a leading `experiment` column; one block per experiment."""
    blocks = []
    for experiment, group in runs.groupby("experiment", sort=False):
        table = aggregate(group)
        table.insert(0, "experiment", experiment)
        blocks.append(table)
    return pd.concat(blocks, ignore_index=True)


def write_stress_outputs(runs: pd.DataFrame, results_dir: Path) -> None:
    """Write stress_run_metrics, stress_test_results, rebuild summary.csv, append the log.

    summary.csv = the Exp1 table (baseline_results.csv, experiment exp1_baseline) + the stress table.
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    table = aggregate_stress(runs)
    baseline = pd.read_csv(results_dir / BASELINE_FILE)
    baseline.insert(0, "experiment", EXPERIMENT)
    runs.drop(columns=["status"]).to_csv(results_dir / STRESS_RUN_METRICS_FILE, index=False, na_rep="")
    table.to_csv(results_dir / STRESS_RESULTS_FILE, index=False, na_rep="")
    pd.concat([baseline, table], ignore_index=True).to_csv(results_dir / SUMMARY_FILE, index=False, na_rep="")
    append_log(results_dir / LOG_FILE, log_rows(runs))


def main_stress(
    results_dir: Path = RESULTS_DIR, calibration_path: Path | None = None, force: bool = False,
    seeds: Sequence[int] = MAIN_SEEDS, count: int = COUNT, allow_dirty: bool = False,
) -> dict[str, object]:
    """Run Exp3 + Exp4 stress cells and write the files.

    Raises ValueError (bad calibration or no baseline_results.csv), FileExistsError (stress
    output exists, no force) or DirtyTreeError. Returns n_runs, n_cells, ample_violated,
    h4b_skipped, git_commit.
    """
    calibration_path = calibration_path or results_dir / CALIBRATION_FILE
    existing = [results_dir / n for n in (STRESS_RUN_METRICS_FILE, STRESS_RESULTS_FILE) if (results_dir / n).exists()]
    if existing and not force:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"Output already exists: {names}. Use --force to overwrite.")
    usd, jpy = read_reference(calibration_path)
    levels = read_stress_levels(calibration_path)
    if not (results_dir / BASELINE_FILE).exists():
        raise ValueError(f"{results_dir / BASELINE_FILE} not found. Run Exp1 (baseline) first: summary.csv needs it.")
    commit = check_git_clean(allow_dirty)
    conditions = stress_conditions(levels)
    if levels.h4b_multiplier is None:
        print(f"WARNING: H4b cells skipped: {levels.h4b_skip_reason}. H4b is untestable.")
    started = time.perf_counter()
    runs = run_stress_all(usd, jpy, conditions, seeds=seeds, count=count)
    elapsed = time.perf_counter() - started
    violated = runs[runs["status"] == STATUS_AMPLE_VIOLATED]
    if len(violated) > 0:
        print(f"WARNING: ample reference violated in {len(violated)} run(s) (insufficient_funds > 0 in an ample cell).")
        print("Do not change the reference silently: follow methodology sec. 6.")
    write_stress_outputs(runs, results_dir)
    print(f"Stress (Exp3 + Exp4): {len(runs)} runs, {len(conditions)} cells, seeds {seeds_label(list(seeds))}, "
          f"commit {commit}, {elapsed:.1f} s")  # fmt: skip
    print(f"Ample violated: {len(violated) > 0}")
    for condition in conditions:
        cell = runs[(runs["experiment"] == condition.experiment) & (runs["condition"] == condition.name)]
        rates = {m: cell[cell["model"] == m.value]["success_rate"].mean() for m in MODELS}
        print(f"  {condition.experiment}/{condition.name}: mean success rate "
              f"A={rates[Model.SEQUENTIAL]:.4f} B={rates[Model.PREFUNDED]:.4f} C={rates[Model.ATOMIC]:.4f}")  # fmt: skip
    print(f"Wrote {results_dir / STRESS_RUN_METRICS_FILE}, {results_dir / STRESS_RESULTS_FILE}, "
          f"{results_dir / SUMMARY_FILE}; appended {len(runs)} rows to {results_dir / LOG_FILE}")  # fmt: skip
    return {"n_runs": len(runs), "n_cells": len(conditions), "ample_violated": len(violated) > 0,
            "h4b_skipped": levels.h4b_multiplier is None, "git_commit": commit}  # fmt: skip


# ------------------------------------------------------------------ sensitivity (Exp2 x Exp3, Day 13)

SENSITIVITY_RUN_METRICS_FILE = "sensitivity_run_metrics.csv"
SENSITIVITY_RESULTS_FILE = "sensitivity_results.csv"
EXP2X3 = "exp2_x_exp3"
# Columns that may differ between a sensitivity row and the Exp3 row it repeats.
CROSS_CHECK_SKIP = ("git_commit", "run_utc", "experiment", "condition", "factor", "factor_level", "status")


@dataclass(frozen=True)
class SensitivityCell:
    """One Exp2 factor cell: one factor changed, the others at baseline."""

    name: str
    factor: str  # volume / banks / arrival / baseline
    factor_level: str
    count: int = COUNT
    n_banks: int = N_BANKS
    arrival: str = ARRIVAL


def sensitivity_cells() -> list[SensitivityCell]:
    """The 6 Exp2 cells (methodology sec. 6, Day 13 decision 6), in a fixed order."""
    return [
        SensitivityCell("baseline", "baseline", "baseline"),
        SensitivityCell("volume_100", "volume", "100", count=100),
        SensitivityCell("volume_1000", "volume", "1000", count=1000),
        SensitivityCell("banks_5", "banks", "5", n_banks=5),
        SensitivityCell("banks_10", "banks", "10", n_banks=10),
        SensitivityCell("arrival_burst", "arrival", "burst", arrival="burst"),
    ]


def sensitivity_multipliers(levels: StressLevels) -> list[float]:
    """JPY grid: multiplier 1 first, then the lower multipliers from calibration.csv."""
    return [1.0, *levels.lower_multipliers]


def run_sensitivity_all(
    initial_usd: int, reference_jpy: int, cells: Sequence[SensitivityCell], multipliers: Sequence[float],
    seeds: Sequence[int] = MAIN_SEEDS,
) -> pd.DataFrame:
    """Run every (seed, cell, grid level, model). Transactions: once per (seed, cell).

    The data of one (seed, cell) is shared by all grid levels and all three models.
    Only grid level 1 is an ample cell. check_stress (check 1) runs over the ample cells.
    """
    commit = git_version()
    rows: list[dict[str, object]] = []
    for seed in seeds:
        for cell in cells:
            data = transactions.generate_transactions(
                count=cell.count, fx_rate=FX_RATE, seed=seed, n_banks=cell.n_banks, arrival=cell.arrival
            )
            for multiplier in multipliers:
                condition = ExpCondition(f"{cell.name}/jpy_{level_text(multiplier)}", STRESS_FAILURE_PROBABILITY,
                                         EXP2X3, DELAY_SECONDS, multiplier, multiplier == 1.0)  # fmt: skip
                jpy = initial_jpy_for(reference_jpy, multiplier)
                for model in MODELS:
                    row = run_one(data, model, condition, seed, initial_usd, jpy, cell.count,
                                  cell.n_banks, DELAY_SECONDS, cell.arrival)  # fmt: skip
                    row["factor"] = cell.factor
                    row["factor_level"] = cell.factor_level
                    row["jpy_multiplier"] = multiplier
                    row["ample_cell"] = condition.ample
                    row["status"] = run_status(row, condition.ample)
                    row["git_commit"] = commit
                    row["run_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                    rows.append(row)
    runs = pd.DataFrame(rows)
    check_stress(runs)
    extra = ("factor", "factor_level", "jpy_multiplier", "ample_cell")
    columns = [c for c in runs.columns if c not in extra]
    after_condition = columns.index("condition") + 1
    after_jpy = columns.index("initial_jpy") + 1
    ordered = (columns[:after_condition] + ["factor", "factor_level"] + columns[after_condition:after_jpy]
               + ["jpy_multiplier", "ample_cell"] + columns[after_jpy:])  # fmt: skip
    return runs[ordered]


def same_value(first: object, second: object) -> bool:
    """True if two table values are equal (two missing values count as equal)."""
    if pd.isna(first) and pd.isna(second):
        return True
    return bool(first == second)


def cross_check_baseline(sensitivity: pd.DataFrame, stress: pd.DataFrame) -> str:
    """Check that the `baseline` cell repeats the Exp3 rows, seed by seed and model by model.

    Compares every column both tables share except CROSS_CHECK_SKIP. Only seeds present in
    both tables are compared. The baseline seeds must be a subset of the Exp3 seeds.
    Returns "OK (...)", or "skipped (...)" with a printed WARNING if the stress table has no
    Exp3 rows at all. Raises RuntimeError with the first mismatch, on partial or no seed
    overlap, on an empty baseline cell, or when no column can be compared.
    """
    base = sensitivity[sensitivity["factor"] == "baseline"]
    exp3 = stress[stress["experiment"] == EXP3]
    if exp3.empty:
        print("WARNING: baseline cross-check skipped: the stress table has no Exp3 rows.")
        return "skipped (no Exp3 rows)"
    if base.empty:
        raise RuntimeError("cross-check: the sensitivity table has no baseline cell rows")
    missing = sorted(set(base["seed"]) - set(exp3["seed"]))
    if missing:
        raise RuntimeError(f"cross-check: baseline seeds {missing} are not in the Exp3 rows "
                           "(partial or no overlap); run the stress experiment with the same seeds")  # fmt: skip
    seeds = sorted(set(base["seed"]))
    columns = [c for c in base.columns if c in exp3.columns and c not in CROSS_CHECK_SKIP]
    if not columns:
        raise RuntimeError("cross-check: no common columns to compare")
    key = ["seed", "model", "jpy_multiplier"]

    def index(table: pd.DataFrame) -> dict[tuple, dict]:
        part = table[table["seed"].isin(seeds)]
        return {(r["seed"], r["model"], r["jpy_multiplier"]): r for r in part.to_dict("records")}

    mine, theirs = index(base), index(exp3)
    for k in sorted(mine, key=str):
        if k not in theirs:
            raise RuntimeError(f"cross-check: {dict(zip(key, k))} is in the sensitivity baseline but not in Exp3")
        for column in columns:
            if not same_value(mine[k][column], theirs[k][column]):
                raise RuntimeError(f"cross-check mismatch at {dict(zip(key, k))}, column {column}: "
                                   f"sensitivity {mine[k][column]!r} vs Exp3 {theirs[k][column]!r}")  # fmt: skip
    for k in sorted(set(theirs) - set(mine), key=str):
        raise RuntimeError(f"cross-check: {dict(zip(key, k))} is in Exp3 but not in the sensitivity baseline")
    return f"OK ({len(mine)} rows, {len(seeds)} seeds, {len(columns)} columns)"


def write_sensitivity_outputs(runs: pd.DataFrame, results_dir: Path) -> None:
    """Write sensitivity_run_metrics, sensitivity_results, rebuild summary.csv, append the log.

    summary.csv = Exp1 table (baseline_results.csv) + stress table (stress_test_results.csv)
    + the sensitivity table.
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    table = aggregate_stress(runs)
    baseline = pd.read_csv(results_dir / BASELINE_FILE)
    baseline.insert(0, "experiment", EXPERIMENT)
    stress = pd.read_csv(results_dir / STRESS_RESULTS_FILE)
    runs.drop(columns=["status"]).to_csv(results_dir / SENSITIVITY_RUN_METRICS_FILE, index=False, na_rep="")
    table.to_csv(results_dir / SENSITIVITY_RESULTS_FILE, index=False, na_rep="")
    pd.concat([baseline, stress, table], ignore_index=True).to_csv(results_dir / SUMMARY_FILE, index=False, na_rep="")
    append_log(results_dir / LOG_FILE, log_rows(runs))


def main_sensitivity(
    results_dir: Path = RESULTS_DIR, calibration_path: Path | None = None, force: bool = False,
    seeds: Sequence[int] = MAIN_SEEDS, allow_dirty: bool = False,
    cells: Sequence[SensitivityCell] | None = None,
) -> dict[str, object]:
    """Run Exp2 x Exp3 and write the files. `cells` is only changed by tests (small counts).

    Raises FileExistsError (output exists, no force), ValueError (bad calibration, or
    baseline_results.csv / stress_test_results.csv missing), DirtyTreeError, or RuntimeError
    (self-check or baseline cross-check failed; nothing is written then).
    Returns n_runs, n_cells, ample_violated, cross_check, git_commit.
    Known limitation (same as stress): experiment_log.csv is append-only, so a --force rerun
    adds a second set of rows for the same runs. With --force, an existing lstar_by_seed.csv /
    h3_verdicts.csv becomes stale: a warning is printed to regenerate them.
    """
    calibration_path = calibration_path or results_dir / CALIBRATION_FILE
    outputs = (SENSITIVITY_RUN_METRICS_FILE, SENSITIVITY_RESULTS_FILE)
    existing = [results_dir / n for n in outputs if (results_dir / n).exists()]
    if existing and not force:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"Output already exists: {names}. Use --force to overwrite.")
    usd, jpy = read_reference(calibration_path)
    levels = read_stress_levels(calibration_path)
    for name in (BASELINE_FILE, STRESS_RESULTS_FILE):
        if not (results_dir / name).exists():
            raise ValueError(f"{results_dir / name} not found. Run Exp1 (baseline) and stress first: summary.csv needs it.")
    commit = check_git_clean(allow_dirty)
    cells = list(cells) if cells is not None else sensitivity_cells()
    started = time.perf_counter()
    runs = run_sensitivity_all(usd, jpy, cells, sensitivity_multipliers(levels), seeds=seeds)
    elapsed = time.perf_counter() - started
    stress_runs = results_dir / STRESS_RUN_METRICS_FILE
    if stress_runs.exists():
        cross_check = cross_check_baseline(runs, pd.read_csv(stress_runs))
    else:
        cross_check = f"skipped ({STRESS_RUN_METRICS_FILE} not found)"
        print(f"WARNING: baseline cross-check skipped: {STRESS_RUN_METRICS_FILE} not found.")
    violated = runs[runs["status"] == STATUS_AMPLE_VIOLATED]
    if len(violated) > 0:
        print(f"WARNING: ample reference violated in {len(violated)} run(s) (insufficient_funds > 0 at grid level 1).")
        print("Do not change the reference silently: follow methodology sec. 6.")
    write_sensitivity_outputs(runs, results_dir)
    stale = [n for n in ("lstar_by_seed.csv", "h3_verdicts.csv") if (results_dir / n).exists()]
    if stale:
        print(f"WARNING: {', '.join(stale)} now stale (based on older sensitivity runs). "
              "Regenerate with `python -m src.verdicts h3 --force`.")  # fmt: skip
    print(f"Sensitivity (Exp2 x Exp3): {len(runs)} runs, {len(cells)} cells, seeds {seeds_label(list(seeds))}, "
          f"commit {commit}, {elapsed:.1f} s")  # fmt: skip
    print(f"Ample violated: {len(violated) > 0}")
    print(f"Baseline cross-check vs Exp3: {cross_check}")
    print(f"Wrote {results_dir / SENSITIVITY_RUN_METRICS_FILE}, {results_dir / SENSITIVITY_RESULTS_FILE}, "
          f"{results_dir / SUMMARY_FILE}; appended {len(runs)} rows to {results_dir / LOG_FILE}")  # fmt: skip
    return {"n_runs": len(runs), "n_cells": len(cells), "ample_violated": len(violated) > 0,
            "cross_check": cross_check, "git_commit": commit}  # fmt: skip


def cli(argv: Sequence[str] | None = None) -> int:
    """Command line entry point. Returns the exit code (0 = ok, 1 = refused)."""
    parser = argparse.ArgumentParser(description="Run an experiment.")
    parser.add_argument("experiment", choices=["baseline", "stress", "sensitivity"], help="which experiment to run")
    parser.add_argument("--force", action="store_true", help="overwrite existing results")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="allow a run with uncommitted changes (test runs only)")
    args = parser.parse_args(argv)
    try:
        runners = {"baseline": main, "stress": main_stress, "sensitivity": main_sensitivity}
        run = runners[args.experiment]
        run(force=args.force, allow_dirty=args.allow_dirty)
    except (FileExistsError, ValueError, DirtyTreeError) as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())

"""Experiments. Day 11: Exp1 Baseline (methodology sec. 4-8).

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
"""

from __future__ import annotations

import argparse
import csv
import math
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
    """One Exp1 condition: a name and its failure probability."""

    name: str
    failure_probability: float


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
) -> dict[str, object]:
    """Run one model once, check it, and return one run_metrics row (without git / time)."""
    params = SimulationParams(
        seed=seed, initial_usd=initial_usd, initial_jpy=initial_jpy,
        delay_seconds=delay_seconds, failure_probability=condition.failure_probability,
        cutoff_seconds=CUTOFF_SECONDS, n_banks=n_banks,
    )  # fmt: skip
    results, ledger = simulator.run_model(data, model, params)
    values = metrics.calculate_metrics(results, data, params, ledger)
    check_run(model, condition, values, ledger, params)
    return {
        "experiment": EXPERIMENT, "condition": condition.name, "model": model.value,
        "seed": seed, "count": count, "n_banks": n_banks, "arrival": ARRIVAL,
        "delay_seconds": delay_seconds, "failure_probability": condition.failure_probability,
        "initial_usd": initial_usd, "initial_jpy": initial_jpy,
        **values,
    }  # fmt: skip


def run_status(row: dict[str, object]) -> str:
    """`ample_violated` if any transaction failed for insufficient funds, else `ok`."""
    return STATUS_AMPLE_VIOLATED if row["n_insufficient_funds"] > 0 else STATUS_OK


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
    commit = git_version()
    if commit.endswith("-dirty"):
        if not allow_dirty:
            raise DirtyTreeError(
                f"Git working tree has uncommitted changes ({commit}). Commit first, "
                "or use --allow-dirty for a test run."
            )
        print("WARNING: git working tree has uncommitted changes. The real run must be from a clean commit.")
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


def cli(argv: Sequence[str] | None = None) -> int:
    """Command line entry point. Returns the exit code (0 = ok, 1 = refused)."""
    parser = argparse.ArgumentParser(description="Run an experiment.")
    parser.add_argument("experiment", choices=["baseline"], help="which experiment to run")
    parser.add_argument("--force", action="store_true", help="overwrite existing results")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="allow a run with uncommitted changes (test runs only)")
    args = parser.parse_args(argv)
    try:
        main(force=args.force, allow_dirty=args.allow_dirty)
    except (FileExistsError, ValueError, DirtyTreeError) as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())

"""Liquidity calibration (methodology sec. 6), run once before the main experiments.

Only `insufficient_funds` counts are read. No other metric is computed or stored.
Decision functions are pure (they take count tables); the runner generates the data
and can be replaced by a fake in tests.

Attempt 2 (this code). Attempt 1 scaled USD and JPY together in the grid and H4b stages and
failed: with 2 banks and failure probability 0, no Model A second-leg shortage occurred
(explanation and tests in research/findings.md sec. 2; results/calibration_attempt1.csv).
So now:
- ample stage: both currencies = REFERENCE x 2^d (unchanged);
- grid and H4b stages: only JPY is lowered. USD stays at REFERENCE_USD x 2^d,
  JPY = REFERENCE_JPY x 2^d x multiplier.

Run once with: python -m src.calibration
"""

from __future__ import annotations

import argparse
import math
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from src import metrics, simulator, transactions
from src.simulator import Model, SimulationParams

CALIBRATION_SEEDS = range(101, 111)
MODELS = (Model.SEQUENTIAL, Model.PREFUNDED, Model.ATOMIC)
FAILURE_PROBABILITY = 0.0
REFERENCE_USD = 100_000_000  # placeholder, same as SimulationParams default
REFERENCE_JPY = 15_000_000_000  # ample stage scales both; grid/H4b scale JPY only
ATTEMPT = 2  # attempt 1 (both currencies scaled in the grid) failed; see findings.md sec. 2
GRID_SCALING = "jpy_only"  # grid and H4b stages: USD fixed, JPY x multiplier
MAX_DOUBLINGS = 5
LOWER_MULTIPLIERS = (0.75, 0.50, 0.25, 0.10)
MIN_SHORT_LEVELS = 2
MAX_HALVINGS = 3
H4B_DELAYS = (0, 60, 300)
H4B_MIN_SEED_SHARE = 0.5

OUTPUT_FILES = ("calibration.csv", "calibration_checks.csv")
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

# Column names of the count tables.
FUNDS = "n_insufficient_funds"
PARTIAL_FUNDS = "n_partial_insufficient_funds"
TABLE_COLUMNS = [
    "stage", "attempt", "condition", "model", "seed", "count", "n_banks", "arrival",
    "delay_seconds", "doublings", "multiplier", "usd", "jpy", "scaled_currency",
    FUNDS, PARTIAL_FUNDS,
]  # fmt: skip


@dataclass(frozen=True)
class Condition:
    """One experiment setting (everything except liquidity, model and seed)."""

    name: str
    count: int = 500
    n_banks: int = 2
    arrival: str = "sequential"
    delay_seconds: float = 60


BASELINE = Condition("baseline")
AMPLE_CONDITIONS = (
    BASELINE,
    replace(BASELINE, name="count_100", count=100),
    replace(BASELINE, name="count_1000", count=1000),
    replace(BASELINE, name="banks_5", n_banks=5),
    replace(BASELINE, name="banks_10", n_banks=10),
    replace(BASELINE, name="arrival_burst", arrival="burst"),
    replace(BASELINE, name="delay_0", delay_seconds=0),
    replace(BASELINE, name="delay_300", delay_seconds=300),
)
EXP3_CONDITION = BASELINE  # 500 tx, 2 banks, sequential, delay 60

# A run function takes (condition, model, seed, usd, jpy) and returns the two counts.
RunFn = Callable[[Condition, Model, int, float, float], dict[str, int]]


# ---------------------------------------------------------------- real runner

def run_counts(
    condition: Condition, model: Model, seed: int, usd: float, jpy: float
) -> dict[str, int]:
    """Run one real simulation and return only the insufficient_funds counts."""
    data = transactions.generate_transactions(
        count=condition.count,
        seed=seed,
        n_banks=condition.n_banks,
        arrival=condition.arrival,
    )
    params = SimulationParams(
        seed=seed,
        initial_usd=usd,
        initial_jpy=jpy,
        delay_seconds=condition.delay_seconds,
        failure_probability=FAILURE_PROBABILITY,
        n_banks=condition.n_banks,
    )
    results, _ = simulator.run_model(data, model, params)
    counts = metrics.count_by_reason(results)
    return {FUNDS: counts["n_insufficient_funds"], PARTIAL_FUNDS: counts["n_partial_insufficient_funds"]}


def make_table(
    run_fn: RunFn,
    stage: str,
    conditions: Iterable[Condition],
    models: Iterable[Model],
    seeds: Iterable[int],
    doublings: int,
    multiplier: float,
    attempt: int = 0,
    jpy_only: bool = False,
) -> pd.DataFrame:
    """Run every condition x model x seed at one liquidity level; return the count rows.

    `attempt` labels the try: the doubling number (ample stage), the halving number
    (grid stage) or 0 (H4b stage).
    If `jpy_only` is True, USD stays at REFERENCE_USD x 2^doublings and only JPY is
    multiplied by `multiplier`. Otherwise both currencies are scaled together.
    """
    base = 2**doublings
    usd = REFERENCE_USD * base * (1.0 if jpy_only else multiplier)
    jpy = REFERENCE_JPY * base * multiplier
    scaled_currency = "jpy" if jpy_only else "both"
    rows = []
    for condition in conditions:
        for model in models:
            for seed in seeds:
                counts = run_fn(condition, model, seed, usd, jpy)
                rows.append({
                    "stage": stage, "attempt": attempt, "condition": condition.name, "model": str(model),
                    "seed": seed, "count": condition.count, "n_banks": condition.n_banks,
                    "arrival": condition.arrival, "delay_seconds": condition.delay_seconds,
                    "doublings": doublings, "multiplier": multiplier, "usd": usd, "jpy": jpy,
                    "scaled_currency": scaled_currency,
                    FUNDS: counts[FUNDS], PARTIAL_FUNDS: counts[PARTIAL_FUNDS],
                })  # fmt: skip
    return pd.DataFrame(rows, columns=TABLE_COLUMNS)


# ------------------------------------------------------- pure decision functions

def is_ample(table: pd.DataFrame) -> bool:
    """Ample = no insufficient_funds in any row (any model, seed, condition)."""
    return len(table) > 0 and bool((table[FUNDS] == 0).all())


def find_ample_doubling(
    ample_table_fn: Callable[[int], pd.DataFrame], max_doublings: int = MAX_DOUBLINGS
) -> tuple[int | None, list[pd.DataFrame]]:
    """Try doublings 0, 1, ... max_doublings; return (first ample doubling or None, tables)."""
    tables = []
    for doublings in range(max_doublings + 1):
        table = ample_table_fn(doublings)
        tables.append(table)
        if is_ample(table):
            return doublings, tables
    return None, tables


def seeds_with_shortage(rows: pd.DataFrame) -> int:
    """Number of distinct seeds with at least one partial caused by insufficient_funds."""
    return int(rows.loc[rows[PARTIAL_FUNDS] > 0, "seed"].nunique())


def qualifying_lower_levels(
    table: pd.DataFrame, multipliers: Sequence[float], seeds: Sequence[int]
) -> list[float]:
    """Lower levels where Model A has a funds-partial in EVERY calibration seed."""
    qualifying = []
    for multiplier in multipliers:
        rows = table[(table["multiplier"] == multiplier) & (table["model"] == str(Model.SEQUENTIAL))]
        if set(rows["seed"]) >= set(seeds) and seeds_with_shortage(rows) == len(seeds):
            qualifying.append(multiplier)
    return qualifying


def halve(multipliers: Sequence[float]) -> tuple[float, ...]:
    """Halve every lower multiplier."""
    return tuple(m / 2 for m in multipliers)


def find_grid(
    grid_table_fn: Callable[[tuple[float, ...], int], pd.DataFrame],
    seeds: Sequence[int],
    lower: Sequence[float] = LOWER_MULTIPLIERS,
    min_levels: int = MIN_SHORT_LEVELS,
    max_halvings: int = MAX_HALVINGS,
) -> tuple[tuple[float, ...], int, list[float] | None, list[pd.DataFrame]]:
    """Halve the lower multipliers until >= min_levels qualify, at most max_halvings times.

    Returns (final multipliers, halvings used, qualifying levels or None if the limit
    was reached without success, all tables used).
    """
    multipliers = tuple(lower)
    tables = []
    for halvings in range(max_halvings + 1):
        table = grid_table_fn(multipliers, halvings)
        tables.append(table)
        levels = qualifying_lower_levels(table, multipliers, seeds)
        if len(levels) >= min_levels:
            return multipliers, halvings, levels, tables
        if halvings < max_halvings:
            multipliers = halve(multipliers)
    return multipliers, max_halvings, None, tables


def h4b_level(
    table: pd.DataFrame,
    grid_multipliers: Sequence[float],
    seeds: Sequence[int],
    delays: Sequence[float] = H4B_DELAYS,
    min_share: float = H4B_MIN_SEED_SHARE,
) -> float | None:
    """Highest grid level where Model A has a funds-partial in >= half the seeds at EACH delay.

    `grid_multipliers` includes the reference (1.0). Returns None if no level qualifies.
    """
    needed = math.ceil(min_share * len(seeds))
    model_a = table[table["model"] == str(Model.SEQUENTIAL)]
    for multiplier in sorted(grid_multipliers, reverse=True):
        at_level = model_a[model_a["multiplier"] == multiplier]
        counts = [
            seeds_with_shortage(at_level[at_level["delay_seconds"] == delay]) for delay in delays
        ]
        if all(n >= needed for n in counts):
            return multiplier
    return None


# ------------------------------------------------------------------- orchestration

def seeds_label(seeds: Sequence[int]) -> str:
    """Return seeds as 'first-last' (they are consecutive)."""
    return f"{seeds[0]}-{seeds[-1]}"


def git_version() -> str:
    """Current git commit hash, plus '-dirty' if the working tree has changes."""
    try:
        root = Path(__file__).resolve().parent.parent
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return commit + ("-dirty" if status else "")


def run_calibration(
    run_fn: RunFn = run_counts,
    seeds: Sequence[int] = CALIBRATION_SEEDS,
    conditions: Sequence[Condition] = AMPLE_CONDITIONS,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Run the whole calibration; return (one summary row, all count rows used)."""
    seeds = list(seeds)
    tables: list[pd.DataFrame] = []

    # Step 1: reference. Double until ample (all models, seeds and conditions).
    def ample_fn(doublings: int) -> pd.DataFrame:
        return make_table(run_fn, "ample", conditions, MODELS, seeds, doublings, 1.0, doublings)

    doublings, ample_tables = find_ample_doubling(ample_fn)
    tables += ample_tables
    ample_reached = doublings is not None
    used = doublings if ample_reached else MAX_DOUBLINGS
    scale = 2**used
    row: dict[str, object] = {
        "attempt": ATTEMPT, "grid_scaling": GRID_SCALING,
        "status": "ok" if ample_reached else "failed",
        "failed_condition": "" if ample_reached else
            f"not ample after {MAX_DOUBLINGS} doublings (insufficient_funds still occurs)",
        "reference_usd": REFERENCE_USD * scale, "reference_jpy": REFERENCE_JPY * scale,
        "doublings_used": used, "ample_reached": ample_reached,
        "lower_multipliers": "", "halvings_used": "", "grid_condition_met": "",
        "qualifying_lower_levels": "", "h4b_multiplier": "", "h4b_testable": "",
        "seeds": seeds_label(seeds), "failure_probability": FAILURE_PROBABILITY,
        "git_commit": git_version(),
        "run_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }  # fmt: skip
    if not ample_reached:
        return row, pd.concat(tables, ignore_index=True)

    # Step 2: grid (JPY only). Exp3 settings, Model A only, delay 60. Halve lower levels if needed.
    def grid_fn(multipliers: tuple[float, ...], attempt: int) -> pd.DataFrame:
        return pd.concat(
            [make_table(run_fn, "grid", [EXP3_CONDITION], [Model.SEQUENTIAL], seeds, used, m,
                        attempt, jpy_only=True)
             for m in multipliers],
            ignore_index=True,
        )  # fmt: skip

    multipliers, halvings, levels, grid_tables = find_grid(grid_fn, seeds)
    tables += grid_tables
    row["lower_multipliers"] = " ".join(f"{m:g}" for m in multipliers)
    row["halvings_used"] = halvings
    row["grid_condition_met"] = levels is not None
    if levels is None:
        row["status"] = "failed"
        row["failed_condition"] = (
            f"fewer than {MIN_SHORT_LEVELS} lower levels with a funds-partial in every seed "
            f"after {MAX_HALVINGS} halvings"
        )
        return row, pd.concat(tables, ignore_index=True)
    row["qualifying_lower_levels"] = " ".join(f"{m:g}" for m in levels)

    # Step 3: H4b level over the final grid (reference + lower levels) at each delay (JPY only).
    grid = (1.0, *multipliers)
    h4b_tables = [
        make_table(
            run_fn, "h4b", [replace(EXP3_CONDITION, name=f"delay_{d:g}", delay_seconds=d)],
            [Model.SEQUENTIAL], seeds, used, m, jpy_only=True,
        )
        for m in grid
        for d in H4B_DELAYS
    ]  # fmt: skip
    h4b_table = pd.concat(h4b_tables, ignore_index=True)
    tables.append(h4b_table)
    level = h4b_level(h4b_table, grid, seeds)
    row["h4b_testable"] = level is not None
    row["h4b_multiplier"] = "" if level is None else f"{level:g}"
    return row, pd.concat(tables, ignore_index=True)


def write_outputs(row: dict[str, object], checks: pd.DataFrame, out_dir: Path = RESULTS_DIR) -> None:
    """Write calibration.csv (one row) and calibration_checks.csv (audit trail)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(out_dir / "calibration.csv", index=False)
    checks.to_csv(out_dir / "calibration_checks.csv", index=False)


def main(
    out_dir: Path = RESULTS_DIR, run_fn: RunFn = run_counts, force: bool = False
) -> dict[str, object]:
    """Run the calibration, write the CSV files and print a short summary.

    Refuses to run (FileExistsError) if an output file exists, unless force is True.
    """
    existing = [out_dir / name for name in OUTPUT_FILES if (out_dir / name).exists()]
    if existing and not force:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"Output already exists: {names}. Use --force to overwrite.")
    row, checks = run_calibration(run_fn)
    write_outputs(row, checks, out_dir)
    print(f"Calibration status: {row['status']} ({len(checks)} count rows)")
    print(f"Reference: USD {row['reference_usd']:,} / JPY {row['reference_jpy']:,} "
          f"(doublings {row['doublings_used']})")  # fmt: skip
    if row["status"] == "failed":
        print(f"FAILED CONDITION: {row['failed_condition']}")
        print("No main run may start. Record this in experiment_log.csv and findings.md.")
    else:
        print(f"Lower multipliers: {row['lower_multipliers']} (halvings {row['halvings_used']})")
        print(f"Qualifying lower levels: {row['qualifying_lower_levels']}")
        print(f"H4b testable: {row['h4b_testable']}, level: {row['h4b_multiplier'] or 'none'}")
    print(f"Wrote {out_dir / 'calibration.csv'} and {out_dir / 'calibration_checks.csv'}")
    return row


def cli(argv: Sequence[str] | None = None) -> int:
    """Command line entry point. Returns the exit code (0 = ok, 1 = refused)."""
    parser = argparse.ArgumentParser(description="Run the liquidity calibration once.")
    parser.add_argument("--force", action="store_true", help="overwrite existing results")
    args = parser.parse_args(argv)
    try:
        main(force=args.force)
    except FileExistsError as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())

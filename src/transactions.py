"""Generate synthetic USD/JPY transactions shared by all three settlement models."""

import json
import numbers
from enum import StrEnum
from pathlib import Path

import numpy as np
import pandas as pd

# Repo root = parent of the src/ folder, so paths do not depend on the cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CSV_PATH = DATA_DIR / "sample_transactions.csv"
META_PATH = DATA_DIR / "sample_transactions_meta.json"

BANK_NAMES = list("ABCDEFGHIJ")
MIN_BANKS = 2
MAX_BANKS = len(BANK_NAMES)

# Arrival patterns are deterministic (simulation seconds, no randomness).
SEQUENTIAL_SPACING_SECONDS = 10  # one transaction every 10 s
BURST_SIZE = 10  # transactions that arrive at the same time
BURST_SPACING_SECONDS = 100  # seconds between bursts


class Arrival(StrEnum):
    """Arrival pattern of the transactions."""

    SEQUENTIAL = "sequential"
    BURST = "burst"


def bank_names(n_banks: int) -> list[str]:
    """Return the first n_banks bank names ("A", "B", ...)."""
    _check_n_banks(n_banks)
    return BANK_NAMES[: int(n_banks)]


def _check_n_banks(n_banks: object) -> None:
    """Raise ValueError unless n_banks is an integer from MIN_BANKS to MAX_BANKS."""
    if (
        isinstance(n_banks, bool)
        or not isinstance(n_banks, numbers.Integral)
        or not MIN_BANKS <= n_banks <= MAX_BANKS
    ):
        raise ValueError(f"n_banks must be an integer from {MIN_BANKS} to {MAX_BANKS}")


def arrival_times(count: int, arrival: Arrival) -> np.ndarray:
    """Return deterministic arrival times in seconds (no randomness)."""
    index = np.arange(count)
    if arrival == Arrival.SEQUENTIAL:
        return index * SEQUENTIAL_SPACING_SECONDS * 1.0
    return (index // BURST_SIZE) * BURST_SPACING_SECONDS * 1.0


def draw_bank_pairs(
    rng: np.random.Generator, count: int, names: list[str]
) -> tuple[list[str], list[str]]:
    """Draw an ordered pair of two different banks (USD payer, JPY payer) per row."""
    n = len(names)
    # One call with shape (count, 2) keeps earlier rows unchanged when count grows.
    draws = rng.integers([0, 1], [n, n], size=(count, 2))
    usd_index = draws[:, 0]
    jpy_index = (usd_index + draws[:, 1]) % n
    return [names[i] for i in usd_index], [names[i] for i in jpy_index]


def generate_transactions(
    count: int = 100,
    fx_rate: float = 150.0,
    seed: int = 42,
    n_banks: int = 2,
    arrival: str = "sequential",
) -> pd.DataFrame:
    """Return a DataFrame of synthetic transactions (same seed -> same data).

    Amounts, bank pairs and failure draws use separate random streams, so
    changing n_banks or arrival does not change amounts or failure_draw.
    Note: amounts are synthetic uniform values, not a real FX distribution.
    """
    if isinstance(count, bool) or not isinstance(count, numbers.Integral) or count <= 0:
        raise ValueError("count must be a positive integer")
    if (
        isinstance(fx_rate, bool)
        or not isinstance(fx_rate, numbers.Real)
        or not np.isfinite(fx_rate)
        or fx_rate <= 0
    ):
        raise ValueError("fx_rate must be a finite number greater than 0")
    if isinstance(seed, bool) or not isinstance(seed, numbers.Integral) or seed < 0:
        raise ValueError("seed must be an integer >= 0")
    names = bank_names(n_banks)  # also validates n_banks
    try:
        arrival_pattern = Arrival(arrival)
    except ValueError:
        raise ValueError(f"arrival must be one of {[a.value for a in Arrival]}") from None
    count = int(count)
    seed = int(seed)

    amount_seed, bank_seed, failure_seed = np.random.SeedSequence(seed).spawn(3)
    amount_rng = np.random.default_rng(amount_seed)
    bank_rng = np.random.default_rng(bank_seed)
    failure_rng = np.random.default_rng(failure_seed)

    # Round USD first, then round JPY to 2 decimals to avoid float noise in the CSV.
    usd_amounts = np.round(amount_rng.uniform(100_000, 1_000_000, count), 2)
    usd_payers, jpy_payers = draw_bank_pairs(bank_rng, count, names)

    return pd.DataFrame(
        {
            "transaction_id": range(1, count + 1),
            "arrival_time": arrival_times(count, arrival_pattern),
            "usd_payer": usd_payers,
            "jpy_payer": jpy_payers,
            "usd_amount": usd_amounts,
            "jpy_amount": np.round(usd_amounts * fx_rate, 2),
            "fx_rate": fx_rate,
            "failure_draw": failure_rng.random(count),
        }
    )


def save_transactions(
    data: pd.DataFrame,
    count: int,
    fx_rate: float,
    seed: int,
    n_banks: int,
    arrival: str,
) -> None:
    """Write the CSV and a small JSON file that records the settings used."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data.to_csv(CSV_PATH, index=False)
    meta = {
        "count": count,
        "fx_rate": fx_rate,
        "seed": seed,
        "n_banks": n_banks,
        "arrival": str(Arrival(arrival).value),
        "generator": "src/transactions.py",
    }
    META_PATH.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    COUNT, FX_RATE, SEED, N_BANKS, ARRIVAL = 100, 150.0, 42, 2, "sequential"
    transactions = generate_transactions(COUNT, FX_RATE, SEED, N_BANKS, ARRIVAL)
    save_transactions(transactions, COUNT, FX_RATE, SEED, N_BANKS, ARRIVAL)
    print(transactions.head())

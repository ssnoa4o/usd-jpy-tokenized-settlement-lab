"""Generate synthetic USD/JPY transactions shared by all three settlement models."""

import json
import numbers
from pathlib import Path

import numpy as np
import pandas as pd

# Repo root = parent of the src/ folder, so paths do not depend on the cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CSV_PATH = DATA_DIR / "sample_transactions.csv"
META_PATH = DATA_DIR / "sample_transactions_meta.json"


def generate_transactions(
    count: int = 100, fx_rate: float = 150.0, seed: int = 42
) -> pd.DataFrame:
    """Return a DataFrame of synthetic transactions (same seed -> same data).

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
    count = int(count)
    seed = int(seed)

    rng = np.random.default_rng(seed)
    # Round USD first, then round JPY to 2 decimals to avoid float noise in the CSV.
    usd_amounts = np.round(rng.uniform(100_000, 1_000_000, count), 2)
    directions = rng.choice(["A_pays_USD", "B_pays_USD"], count)

    return pd.DataFrame(
        {
            "transaction_id": range(1, count + 1),
            "usd_amount": usd_amounts,
            "jpy_amount": np.round(usd_amounts * fx_rate, 2),
            "direction": directions,
            "fx_rate": fx_rate,
        }
    )


def save_transactions(
    data: pd.DataFrame, count: int, fx_rate: float, seed: int
) -> None:
    """Write the CSV and a small JSON file that records the seed used."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data.to_csv(CSV_PATH, index=False)
    meta = {
        "count": count,
        "fx_rate": fx_rate,
        "seed": seed,
        "generator": "src/transactions.py",
    }
    META_PATH.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    COUNT, FX_RATE, SEED = 100, 150.0, 42
    transactions = generate_transactions(COUNT, FX_RATE, SEED)
    save_transactions(transactions, COUNT, FX_RATE, SEED)
    print(transactions.head())

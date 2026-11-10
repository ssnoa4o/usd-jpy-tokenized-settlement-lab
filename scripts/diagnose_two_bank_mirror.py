"""Diagnostic for the failed Day 10 calibration. NOT an experiment and NOT a result.

Question: why did Model A show no second-leg (`partial`) `insufficient_funds` in the
calibration grid? This script uses test seeds 201 to 205 only (not the calibration
seeds 101-110, not the main seeds 1-30), Exp3-like settings (500 transactions,
sequential arrival, delay 60 s, failure 0%) and USD/JPY scaled together.

For each bank count, multiplier and seed it records the Model A counts of
`partial` / `failed` with `insufficient_funds`. With 2 banks it also records
|dJPY_A + fx * dUSD_A| at the end of the run (in JPY), which is 0 if bank A's JPY
change mirrors its USD change.

Run from the repository root:
    python -m scripts.diagnose_two_bank_mirror
Writes results/diagnostic_two_bank_mirror.csv.
"""

from pathlib import Path

import pandas as pd

from src.metrics import count_by_reason
from src.simulator import Currency, Model, SimulationParams, run_model, to_minor
from src.transactions import generate_transactions

SEEDS = range(201, 206)
BANK_COUNTS = (2, 5)
MULTIPLIERS = (0.25, 0.1, 0.05, 0.0125)
REFERENCE_USD = 100_000_000
REFERENCE_JPY = 15_000_000_000
FX_RATE = 150.0
OUT = Path(__file__).resolve().parent.parent / "results" / "diagnostic_two_bank_mirror.csv"


def main() -> None:
    rows = []
    for n_banks in BANK_COUNTS:
        for mult in MULTIPLIERS:
            for seed in SEEDS:
                data = generate_transactions(
                    count=500, fx_rate=FX_RATE, seed=seed, n_banks=n_banks, arrival="sequential"
                )
                params = SimulationParams(
                    seed=seed,
                    initial_usd=REFERENCE_USD * mult,
                    initial_jpy=REFERENCE_JPY * mult,
                    delay_seconds=60,
                    failure_probability=0.0,
                    n_banks=n_banks,
                )
                results, ledger = run_model(data, Model.SEQUENTIAL, params)
                counts = count_by_reason(results)
                mirror_gap_jpy = None
                if n_banks == 2:
                    d_usd = ledger.balance("A", Currency.USD) - to_minor(params.initial_usd)
                    d_jpy = ledger.balance("A", Currency.JPY) - to_minor(params.initial_jpy)
                    mirror_gap_jpy = abs(d_jpy + FX_RATE * d_usd) / 100
                rows.append(
                    {
                        "n_banks": n_banks,
                        "multiplier": mult,
                        "seed": seed,
                        "n_partial_insufficient_funds": counts["n_partial_insufficient_funds"],
                        "n_failed_insufficient_funds": counts["n_failed_insufficient_funds"],
                        "mirror_gap_jpy": mirror_gap_jpy,
                    }
                )
    table = pd.DataFrame(rows)
    table.to_csv(OUT, index=False)
    print(table.groupby(["n_banks", "multiplier"])[
        ["n_partial_insufficient_funds", "n_failed_insufficient_funds", "mirror_gap_jpy"]
    ].agg({"n_partial_insufficient_funds": "sum", "n_failed_insufficient_funds": "sum",
           "mirror_gap_jpy": "max"}).to_string())
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

"""Metric calculations. Definitions are in research/methodology.md, sec. 5.

Day 9: state counts, Success / Partial / Failure Rate, counts by failure reason and
Principal Exposure (amount-based and duration-weighted). The liquidity and time
metrics are added on Day 10.

Every function takes the results of ONE run of ONE model. A ratio with a zero
denominator is NaN, never 0 (methodology sec. 5). This differs on purpose from the
HANDOFF sketch, which returns 0 when there are no transactions.
"""

import math

import pandas as pd

from src.simulator import (
    FailureReason,
    Model,
    SettlementResult,
    SimulationParams,
    Status,
)


def safe_ratio(numerator: float, denominator: float) -> float:
    """Return numerator / denominator, or NaN if the denominator is 0.

    NaN, not 0, so that "no data" is never shown as "0% success".
    """
    if denominator == 0:
        return float("nan")
    return numerator / denominator


def check_one_run(results: list[SettlementResult]) -> None:
    """Raise ValueError if the results mix models or repeat a transaction."""
    if len({r.model for r in results}) > 1:
        raise ValueError("results must come from one model run, not several models")
    ids = [r.transaction_id for r in results]
    if len(ids) != len(set(ids)):
        raise ValueError("each transaction_id must appear once in a run")


def count_states(results: list[SettlementResult]) -> dict[str, int]:
    """N and the number of settled, partial and failed transactions."""
    check_one_run(results)
    return {
        "n_total": len(results),
        "n_settled": sum(r.status == Status.SETTLED for r in results),
        "n_partial": sum(r.status == Status.PARTIAL for r in results),
        "n_failed": sum(r.status == Status.FAILED for r in results),
    }


def settlement_rates(results: list[SettlementResult]) -> dict[str, float]:
    """Success, Partial and Failure Rate over N. Success counts `settled` only.

    A `partial` transaction is never a success: one leg is still open.
    With N = 0 every rate is NaN.
    """
    counts = count_states(results)
    n = counts["n_total"]
    return {
        "success_rate": safe_ratio(counts["n_settled"], n),
        "partial_rate": safe_ratio(counts["n_partial"], n),
        "failure_rate": safe_ratio(counts["n_failed"], n),
    }


def count_by_reason(results: list[SettlementResult]) -> dict[str, int]:
    """Counts by failure reason, split by state, for every reason (zeros included).

    Keys: `n_<state>_<reason>` for state partial / failed, and `n_<reason>` for the
    two states together. Every reason is listed, so `timeout` shows as 0 instead of
    being missing.
    """
    check_one_run(results)
    counts: dict[str, int] = {}
    for reason in FailureReason:
        for state in (Status.PARTIAL, Status.FAILED):
            counts[f"n_{state}_{reason}"] = sum(
                r.status == state and r.failure_reason == reason for r in results
            )
    for reason in FailureReason:
        counts[f"n_{reason}"] = counts[f"n_partial_{reason}"] + counts[f"n_failed_{reason}"]
    return counts


def principal_exposure_usd(results: list[SettlementResult]) -> float:
    """Amount-based Principal Exposure: sum of `usd_amount` over `partial` transactions."""
    check_one_run(results)
    return math.fsum(r.principal_exposure_usd for r in results if r.status == Status.PARTIAL)


def principal_exposure_usd_seconds(
    results: list[SettlementResult], transactions: pd.DataFrame, cutoff_seconds: float
) -> float:
    """Duration-weighted Principal Exposure in USD-seconds (descriptive only).

    For each transaction whose first leg completed: usd_amount x window. The window
    runs from first-leg completion to second-leg completion; for a `partial` it is
    closed at first-leg completion + cutoff_seconds (W). W only closes the window.
    - A and B: the USD leg completes at arrival, the JPY leg at `end_time`.
    - C: both legs complete in one commit, so the window is 0.
    - `failed`: no leg completed, so nothing is counted.
    """
    check_one_run(results)
    if not math.isfinite(cutoff_seconds) or cutoff_seconds < 0:
        raise ValueError("cutoff_seconds must be a finite number >= 0")
    amounts = _usd_amounts(transactions)
    terms = []
    for r in results:
        if r.status == Status.FAILED or r.model == Model.ATOMIC:
            continue
        if r.transaction_id not in amounts:
            raise KeyError(f"transaction_id {r.transaction_id} is not in the input data")
        if r.status == Status.PARTIAL:
            window = cutoff_seconds
        else:
            window = r.end_time - r.arrival_time  # first leg at arrival, second at end
        terms.append(amounts[r.transaction_id] * window)
    return math.fsum(terms)


def calculate_metrics(
    results: list[SettlementResult], transactions: pd.DataFrame, params: SimulationParams
) -> dict[str, float]:
    """All Day 9 metrics for one run, as one flat row (a future run_metrics.csv row)."""
    return {
        **count_states(results),
        **settlement_rates(results),
        **count_by_reason(results),
        "principal_exposure_usd": principal_exposure_usd(results),
        "principal_exposure_usd_seconds": principal_exposure_usd_seconds(
            results, transactions, params.cutoff_seconds
        ),
        "cutoff_seconds": params.cutoff_seconds,
    }


def _usd_amounts(transactions: pd.DataFrame) -> dict[int, float]:
    """transaction_id -> usd_amount, as plain Python values (same as the engine reads)."""
    ids = [int(i) for i in transactions["transaction_id"]]
    if len(ids) != len(set(ids)):
        raise ValueError("transaction_id must be unique")
    return dict(zip(ids, (float(a) for a in transactions["usd_amount"])))

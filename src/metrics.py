"""Metric calculations. Definitions are in research/methodology.md, sec. 5.

Day 9: state counts, Success / Partial / Failure Rate, counts by failure reason and
Principal Exposure (amount-based and duration-weighted).
Day 10: Gross Prefunding, Liquidity Utilization, Peak Liquidity Proxy, Average
Settlement Time and Operational Delay. Gross Prefunding is NOT Peak Liquidity, and
the peak value is only a proxy (no netting, no credit lines).

Every function takes the results of ONE run of ONE model. A ratio with a zero
denominator is NaN, never 0 (methodology sec. 5). This differs on purpose from the
HANDOFF sketch, which returns 0 when there are no transactions.
"""

import math

import pandas as pd

from src.simulator import (
    MINOR_UNITS_PER_UNIT,
    Currency,
    FailureReason,
    Ledger,
    Model,
    SettlementResult,
    SimulationParams,
    Status,
)
from src.transactions import bank_names


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


def gross_prefunding_usd(results: list[SettlementResult], transactions: pd.DataFrame) -> float:
    """Gross Prefunding in USD: both legs (USD + JPY / fx_rate) of every reserved transaction.

    - Model B: `settled` and `partial` (both legs were reserved at arrival).
    - Model C: `settled` and `failed` with `technical_failure` (funds validation passed).
    - `failed` / `insufficient_funds` adds 0 in B and C.
    - Model A has no prefunding: NaN (not applicable, NOT 0).
    - No results: the model is unknown, so NaN.
    This is a sum over the run, not Peak Liquidity.
    """
    check_one_run(results)
    if not results or results[0].model == Model.SEQUENTIAL:
        return float("nan")
    values = _leg_values(transactions)
    terms = []
    for r in results:
        if _was_prefunded(r):
            terms.append(_both_legs(values, r.transaction_id))
    return math.fsum(terms)


def liquidity_utilization(results: list[SettlementResult], transactions: pd.DataFrame) -> float:
    """USD value of legs that completed / Gross Prefunding (B and C only).

    B settled: both legs. B partial: the USD leg only. C settled: both legs. Failed: 0.
    A, no results, or Gross Prefunding 0: NaN. Descriptive only.
    """
    gross = gross_prefunding_usd(results, transactions)
    if math.isnan(gross):
        return float("nan")
    values = _leg_values(transactions)
    done = []
    for r in results:
        usd, jpy_in_usd = _leg_usd_parts(values, r.transaction_id)
        done.append(usd * r.usd_leg_done + jpy_in_usd * r.jpy_leg_done)
    return safe_ratio(math.fsum(done), gross)


def peak_liquidity_proxy_usd(ledger: Ledger, params: SimulationParams, fx_rate: float) -> float:
    """Peak Liquidity PROXY in USD: summed peak drawdown of every bank and currency.

    The ledger stores hundredths; they are converted back to units, and JPY is
    divided by fx_rate. Proxy only: no netting, no credit lines. Applies to all models.
    """
    total = []
    for bank in bank_names(params.n_banks):
        usd = ledger.peak_drawdown(bank, Currency.USD) / MINOR_UNITS_PER_UNIT
        jpy = ledger.peak_drawdown(bank, Currency.JPY) / MINOR_UNITS_PER_UNIT
        total.extend([usd, jpy / fx_rate])
    return math.fsum(total)


def average_settlement_time(results: list[SettlementResult]) -> float:
    """Mean of (end_time - arrival_time) over `settled` transactions only; NaN if none."""
    check_one_run(results)
    times = [r.end_time - r.arrival_time for r in results if r.status == Status.SETTLED]
    return safe_ratio(math.fsum(times), len(times))


def operational_delay(results: list[SettlementResult], params: SimulationParams) -> float:
    """Mean injected delay in seconds over transactions that reached a leg or commit attempt.

    In this engine every transaction does, and there is no queue, so the mean equals
    `params.delay_seconds`. NaN if there are no transactions. Descriptive only.
    """
    check_one_run(results)
    delays = [params.delay_seconds for _ in results]
    return safe_ratio(math.fsum(delays), len(delays))


def run_fx_rate(transactions: pd.DataFrame) -> float:
    """The single fx_rate of a run. NaN if there are no rows.

    ValueError if a rate is not a finite number > 0, or if the rows hold more than one rate.
    """
    rates = {float(rate) for rate in transactions["fx_rate"]}
    if any(not math.isfinite(rate) or rate <= 0 for rate in rates):
        raise ValueError("fx_rate must be a finite number > 0")
    if len(rates) > 1:
        raise ValueError("fx_rate must have one value per run")
    return rates.pop() if rates else float("nan")


def calculate_metrics(
    results: list[SettlementResult],
    transactions: pd.DataFrame,
    params: SimulationParams,
    ledger: Ledger,
) -> dict[str, float]:
    """All Day 9 and Day 10 metrics for one run, as one flat row (a future run_metrics.csv row).

    `ledger` must be the ledger returned by the same `run_model` call as `results`.
    This is not checked: a ledger from another run gives a wrong Peak Liquidity Proxy.
    """
    return {
        **count_states(results),
        **settlement_rates(results),
        **count_by_reason(results),
        "principal_exposure_usd": principal_exposure_usd(results),
        "principal_exposure_usd_seconds": principal_exposure_usd_seconds(
            results, transactions, params.cutoff_seconds
        ),
        "cutoff_seconds": params.cutoff_seconds,
        "gross_prefunding_usd": gross_prefunding_usd(results, transactions),
        "liquidity_utilization": liquidity_utilization(results, transactions),
        "peak_liquidity_proxy_usd": peak_liquidity_proxy_usd(
            ledger, params, run_fx_rate(transactions)
        ),
        "average_settlement_time_seconds": average_settlement_time(results),
        "operational_delay_seconds": operational_delay(results, params),
    }


def _was_prefunded(result: SettlementResult) -> bool:
    """True if funds for both legs were set aside / validated for this transaction."""
    if result.status == Status.SETTLED:
        return True
    if result.model == Model.PREFUNDED:
        return result.status == Status.PARTIAL
    return result.failure_reason == FailureReason.TECHNICAL_FAILURE  # Model C failed


def _leg_values(transactions: pd.DataFrame) -> dict[int, tuple[float, float]]:
    """transaction_id -> (usd_amount, jpy_amount / fx_rate), as plain Python floats."""
    usd = _usd_amounts(transactions)
    jpy_in_usd = {
        int(i): float(j) / float(f)
        for i, j, f in zip(
            transactions["transaction_id"], transactions["jpy_amount"], transactions["fx_rate"]
        )
    }
    return {tid: (usd[tid], jpy_in_usd[tid]) for tid in usd}


def _leg_usd_parts(values: dict[int, tuple[float, float]], tid: int) -> tuple[float, float]:
    """The (USD leg, JPY leg in USD) of one transaction; KeyError if the id is unknown."""
    if tid not in values:
        raise KeyError(f"transaction_id {tid} is not in the input data")
    return values[tid]


def _both_legs(values: dict[int, tuple[float, float]], tid: int) -> float:
    """USD-equivalent value of both legs of one transaction."""
    return sum(_leg_usd_parts(values, tid))


def _usd_amounts(transactions: pd.DataFrame) -> dict[int, float]:
    """transaction_id -> usd_amount, as plain Python values (same as the engine reads)."""
    ids = [int(i) for i in transactions["transaction_id"]]
    if len(ids) != len(set(ids)):
        raise ValueError("transaction_id must be unique")
    return dict(zip(ids, (float(a) for a in transactions["usd_amount"])))

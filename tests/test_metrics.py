"""Tests for src/metrics.py (definitions: research/methodology.md, sec. 5)."""

import dataclasses
import math

import pandas as pd
import pytest

from src.metrics import (
    calculate_metrics,
    count_by_reason,
    count_states,
    principal_exposure_usd,
    principal_exposure_usd_seconds,
    safe_ratio,
    settlement_rates,
)
from src.simulator import FailureReason, Model, SettlementResult, SimulationParams, Status

SHORT = FailureReason.INSUFFICIENT_FUNDS
TECH = FailureReason.TECHNICAL_FAILURE


def settled(
    tid: int, model: Model = Model.SEQUENTIAL, delay: float = 60.0, arrival: float = 0.0
) -> SettlementResult:
    end = arrival + delay
    return SettlementResult(
        tid, model, Status.SETTLED, None, True, True, arrival, arrival, end, 0.0
    )


def partial(
    tid: int, usd_amount: float, reason: FailureReason = TECH, model: Model = Model.SEQUENTIAL
) -> SettlementResult:
    return SettlementResult(
        tid, model, Status.PARTIAL, reason, True, False, 0.0, 0.0, 60.0, usd_amount
    )


def failed(
    tid: int, reason: FailureReason = SHORT, model: Model = Model.SEQUENTIAL
) -> SettlementResult:
    return SettlementResult(tid, model, Status.FAILED, reason, False, False, 0.0, 0.0, 0.0, 0.0)


def amounts(**by_id: float) -> pd.DataFrame:
    """Input rows with only the columns the metrics read: {"t1": 100.0} -> id 1."""
    ids = [int(key[1:]) for key in by_id]
    return pd.DataFrame({"transaction_id": ids, "usd_amount": list(by_id.values())})


# 2 settled, 1 partial (technical failure, USD 300), 1 failed (insufficient funds).
MIXED = [settled(1), settled(2), partial(3, 300.0), failed(4)]
MIXED_DATA = amounts(t1=100.0, t2=200.0, t3=300.0, t4=400.0)


# --- safe_ratio ---


def test_safe_ratio_normal_case() -> None:
    assert safe_ratio(1, 4) == 0.25
    assert safe_ratio(0, 4) == 0


def test_safe_ratio_zero_denominator_is_nan_not_zero() -> None:
    assert math.isnan(safe_ratio(0, 0))
    assert math.isnan(safe_ratio(3, 0))


# --- counts and rates ---


def test_counts_and_rates_by_hand() -> None:
    assert count_states(MIXED) == {"n_total": 4, "n_settled": 2, "n_partial": 1, "n_failed": 1}
    assert settlement_rates(MIXED) == {
        "success_rate": 0.5,
        "partial_rate": 0.25,
        "failure_rate": 0.25,
    }


def test_success_rate_does_not_count_partial_as_success() -> None:
    rates = settlement_rates([partial(1, 10.0), partial(2, 20.0)])
    assert rates["success_rate"] == 0.0
    assert rates["partial_rate"] == 1.0
    assert rates["failure_rate"] == 0.0


def test_turning_a_settled_into_partial_lowers_success_rate() -> None:
    before = settlement_rates([settled(1), settled(2)])
    after = settlement_rates([settled(1), partial(2, 20.0)])
    assert before["success_rate"] == 1.0
    assert after["success_rate"] == 0.5
    assert after["partial_rate"] == 0.5


def test_no_transactions_gives_zero_counts_and_nan_rates() -> None:
    assert count_states([]) == {"n_total": 0, "n_settled": 0, "n_partial": 0, "n_failed": 0}
    rates = settlement_rates([])
    assert all(math.isnan(value) for value in rates.values())
    assert principal_exposure_usd([]) == 0.0
    assert all(value == 0 for value in count_by_reason([]).values())


# --- counts by reason ---


def test_count_by_reason_lists_every_reason_and_state() -> None:
    results = [partial(1, 1.0, SHORT), partial(2, 1.0, TECH), failed(3, SHORT), failed(4, SHORT)]
    counts = count_by_reason(results)
    assert counts["n_partial_insufficient_funds"] == 1
    assert counts["n_partial_technical_failure"] == 1
    assert counts["n_failed_insufficient_funds"] == 2
    assert counts["n_failed_technical_failure"] == 0
    assert counts["n_insufficient_funds"] == 3
    assert counts["n_technical_failure"] == 1
    assert counts["n_timeout"] == 0  # reserved reason: present as 0, not missing
    assert counts["n_partial_timeout"] == counts["n_failed_timeout"] == 0


def test_reason_counts_add_up_to_partial_plus_failed() -> None:
    counts = count_by_reason(MIXED)
    states = count_states(MIXED)
    assert sum(counts[f"n_{reason}"] for reason in FailureReason) == (
        states["n_partial"] + states["n_failed"]
    )


# --- Principal Exposure ---


def test_amount_based_exposure_sums_partial_only() -> None:
    assert principal_exposure_usd(MIXED) == 300.0
    assert principal_exposure_usd([settled(1), failed(2)]) == 0.0


def test_duration_weighted_exposure_by_hand() -> None:
    # settled 1 and 2: 100 x 60 + 200 x 60; partial 3: 300 x W (1,000); failed 4: 0.
    value = principal_exposure_usd_seconds(MIXED, MIXED_DATA, cutoff_seconds=1_000)
    assert value == 100 * 60 + 200 * 60 + 300 * 1_000


def test_duration_weighted_window_starts_at_arrival_not_at_time_zero() -> None:
    data = amounts(t1=100.0, t2=200.0)
    results = [settled(1, arrival=1_000.0, delay=60.0), settled(2, arrival=500.0, delay=0.0)]
    assert principal_exposure_usd_seconds(results, data, 3_600) == 100 * 60 + 200 * 0


def test_duration_weighted_exposure_of_partial_ignores_the_delay() -> None:
    data = amounts(t1=300.0)
    short_delay = partial(1, 300.0)  # end_time 60
    long_delay = dataclasses.replace(short_delay, end_time=300.0)
    assert principal_exposure_usd_seconds([short_delay], data, 3_600) == 300 * 3_600
    assert principal_exposure_usd_seconds([long_delay], data, 3_600) == 300 * 3_600


def test_model_c_has_no_exposure_window() -> None:
    results = [settled(1, Model.ATOMIC), failed(2, TECH, Model.ATOMIC)]
    data = amounts(t1=100.0, t2=200.0)
    assert principal_exposure_usd(results) == 0.0
    assert principal_exposure_usd_seconds(results, data, 3_600) == 0.0


def test_duration_weighted_exposure_needs_the_amount_of_every_counted_transaction() -> None:
    with pytest.raises(KeyError):
        principal_exposure_usd_seconds([settled(9)], MIXED_DATA, 3_600)


@pytest.mark.parametrize("cutoff", [-1.0, math.inf, math.nan])
def test_bad_cutoff_is_rejected(cutoff: float) -> None:
    with pytest.raises(ValueError):
        principal_exposure_usd_seconds(MIXED, MIXED_DATA, cutoff)


# --- one run only ---


def test_mixed_models_are_rejected() -> None:
    with pytest.raises(ValueError):
        settlement_rates([settled(1, Model.SEQUENTIAL), settled(2, Model.PREFUNDED)])


def test_repeated_transaction_is_rejected() -> None:
    with pytest.raises(ValueError):
        count_states([settled(1), settled(1)])


def test_calculate_metrics_with_no_transactions() -> None:
    empty = pd.DataFrame(columns=["transaction_id", "usd_amount"])
    row = calculate_metrics([], empty, SimulationParams(seed=1))
    assert row["n_total"] == 0
    assert math.isnan(row["success_rate"])
    assert row["principal_exposure_usd"] == 0.0
    assert row["principal_exposure_usd_seconds"] == 0.0


def test_calculate_metrics_gives_one_flat_row() -> None:
    params = SimulationParams(seed=1, cutoff_seconds=1_000)
    row = calculate_metrics(MIXED, MIXED_DATA, params)
    assert row["n_total"] == 4
    assert row["success_rate"] == 0.5
    assert row["n_failed_insufficient_funds"] == 1
    assert row["principal_exposure_usd"] == 300.0
    assert row["principal_exposure_usd_seconds"] == 100 * 60 + 200 * 60 + 300 * 1_000
    assert row["cutoff_seconds"] == 1_000
    assert all(not isinstance(value, (dict, list)) for value in row.values())

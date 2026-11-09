"""Tests for src/metrics.py (definitions: research/methodology.md, sec. 5)."""

import dataclasses
import math

import pandas as pd
import pytest

from src.metrics import (
    average_settlement_time,
    calculate_metrics,
    count_by_reason,
    count_states,
    gross_prefunding_usd,
    liquidity_utilization,
    operational_delay,
    peak_liquidity_proxy_usd,
    principal_exposure_usd,
    principal_exposure_usd_seconds,
    run_fx_rate,
    safe_ratio,
    settlement_rates,
)
from src.simulator import (
    Currency,
    FailureReason,
    Ledger,
    Leg,
    Model,
    SettlementResult,
    SimulationParams,
    Status,
    run_model,
)
from src.transactions import generate_transactions

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


def full(fx_rate: float = 150.0, **by_id: float) -> pd.DataFrame:
    """Input rows with usd_amount, jpy_amount (= usd x fx_rate) and fx_rate."""
    data = amounts(**by_id)
    data["jpy_amount"] = data["usd_amount"] * fx_rate
    data["fx_rate"] = fx_rate
    return data


def new_ledger(params: SimulationParams) -> Ledger:
    """A fresh ledger with the starting balances of `params` (no payments made)."""
    return Ledger(
        ["A", "B", "C"][: params.n_banks],
        {Currency.USD: round(params.initial_usd * 100), Currency.JPY: round(params.initial_jpy * 100)},
    )


# 2 settled, 1 partial (technical failure, USD 300), 1 failed (insufficient funds).
MIXED = [settled(1), settled(2), partial(3, 300.0), failed(4)]
MIXED_DATA = full(t1=100.0, t2=200.0, t3=300.0, t4=400.0)


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


NEW_KEYS = (
    "gross_prefunding_usd",
    "liquidity_utilization",
    "peak_liquidity_proxy_usd",
    "average_settlement_time_seconds",
    "operational_delay_seconds",
)


def test_calculate_metrics_with_no_transactions() -> None:
    empty = pd.DataFrame(columns=["transaction_id", "usd_amount", "jpy_amount", "fx_rate"])
    params = SimulationParams(seed=1)
    row = calculate_metrics([], empty, params, new_ledger(params))
    assert row["n_total"] == 0
    assert math.isnan(row["success_rate"])
    assert row["principal_exposure_usd"] == 0.0
    assert row["principal_exposure_usd_seconds"] == 0.0
    for key in (
        "gross_prefunding_usd",
        "liquidity_utilization",
        "peak_liquidity_proxy_usd",
        "average_settlement_time_seconds",
        "operational_delay_seconds",
    ):
        assert math.isnan(row[key]), key


def test_calculate_metrics_gives_one_flat_row() -> None:
    params = SimulationParams(seed=1, cutoff_seconds=1_000)
    row = calculate_metrics(MIXED, MIXED_DATA, params, new_ledger(params))
    assert row["n_total"] == 4
    assert row["success_rate"] == 0.5
    assert row["n_failed_insufficient_funds"] == 1
    assert row["principal_exposure_usd"] == 300.0
    assert row["principal_exposure_usd_seconds"] == 100 * 60 + 200 * 60 + 300 * 1_000
    assert row["cutoff_seconds"] == 1_000
    for key in NEW_KEYS:
        assert key in row
    assert all(not isinstance(value, (dict, list)) for value in row.values())


# --- Day 10: Gross Prefunding and Liquidity Utilization ---
# fx 150: USD amount u has JPY leg u x 150, i.e. u in USD, so a transaction is worth 2u.


def b_partial(tid: int, usd_amount: float) -> SettlementResult:
    return partial(tid, usd_amount, TECH, Model.PREFUNDED)


def test_model_b_prefunding_and_utilization_by_hand() -> None:
    data = full(t1=100.0, t2=200.0, t3=300.0, t4=400.0)
    results = [
        settled(1, Model.PREFUNDED),
        settled(2, Model.PREFUNDED),
        b_partial(3, 300.0),
        failed(4, SHORT, Model.PREFUNDED),
    ]
    # Reserved: 1, 2 and 3 with both legs = 200 + 400 + 600; the failed one adds 0.
    assert gross_prefunding_usd(results, data) == 1_200.0
    # Completed: 200 + 400 + only the USD leg of 3 (300) = 900.
    assert liquidity_utilization(results, data) == 900 / 1_200


def test_model_c_prefunding_counts_technical_failure_but_not_shortage() -> None:
    data = full(t1=100.0, t2=200.0, t3=300.0)
    results = [
        settled(1, Model.ATOMIC),
        failed(2, TECH, Model.ATOMIC),
        failed(3, SHORT, Model.ATOMIC),
    ]
    assert gross_prefunding_usd(results, data) == 200.0 + 400.0  # settled 1 + tech failure 2
    assert liquidity_utilization(results, data) == 200.0 / 600.0  # failed legs never completed


def test_model_a_prefunding_and_utilization_are_nan_not_zero() -> None:
    gross = gross_prefunding_usd(MIXED, MIXED_DATA)
    utilization = liquidity_utilization(MIXED, MIXED_DATA)
    assert math.isnan(gross) and math.isnan(utilization)
    assert gross != 0 and utilization != 0


def test_no_results_give_nan_prefunding() -> None:
    assert math.isnan(gross_prefunding_usd([], full()))


def test_zero_prefunding_gives_nan_utilization() -> None:
    data = full(t1=100.0)
    results = [failed(1, SHORT, Model.PREFUNDED)]
    assert gross_prefunding_usd(results, data) == 0.0
    assert math.isnan(liquidity_utilization(results, data))


def test_prefunding_uses_a_non_150_fx_rate() -> None:
    data = full(fx_rate=140.5, t1=100.0)  # JPY leg 14,050 / 140.5 = 100
    assert gross_prefunding_usd([settled(1, Model.PREFUNDED)], data) == 200.0
    data["jpy_amount"] = 14_050.0 + 1_405.0  # JPY leg now worth 110 USD
    assert gross_prefunding_usd([settled(1, Model.ATOMIC)], data) == pytest.approx(210.0)


def test_prefunding_needs_the_amount_of_every_counted_transaction() -> None:
    with pytest.raises(KeyError):
        gross_prefunding_usd([settled(9, Model.PREFUNDED)], full(t1=100.0))
    with pytest.raises(KeyError):
        liquidity_utilization([settled(9, Model.ATOMIC)], full(t1=100.0))


def test_prefunding_rejects_mixed_models() -> None:
    results = [settled(1, Model.PREFUNDED), settled(2, Model.ATOMIC)]
    with pytest.raises(ValueError):
        gross_prefunding_usd(results, full(t1=1.0, t2=1.0))


# --- Day 10: fx rate and Peak Liquidity Proxy ---


def test_run_fx_rate() -> None:
    assert run_fx_rate(full(fx_rate=140.5, t1=1.0, t2=2.0)) == 140.5
    assert math.isnan(run_fx_rate(full().iloc[0:0]))


@pytest.mark.parametrize("bad", [0.0, -150.0, float("nan"), float("inf")])
def test_bad_fx_rate_is_rejected(bad: float) -> None:
    data = full(t1=1.0, t2=2.0)
    data["fx_rate"] = bad
    with pytest.raises(ValueError, match="finite number > 0"):
        run_fx_rate(data)


def test_two_fx_rates_in_one_run_are_rejected() -> None:
    data = full(t1=1.0, t2=2.0)
    data.loc[1, "fx_rate"] = 151.0
    with pytest.raises(ValueError):
        run_fx_rate(data)


def test_peak_proxy_by_hand_with_three_banks() -> None:
    params = SimulationParams(seed=1, initial_usd=5_000, initial_jpy=1_000_000, n_banks=3)
    ledger = new_ledger(params)
    # A pays USD 1,000 to B; B pays JPY 150,000 to A. Bank C does nothing.
    assert ledger.transfer(Leg("A", "B", Currency.USD, 100_000))
    assert ledger.transfer(Leg("B", "A", Currency.JPY, 15_000_000))
    assert peak_liquidity_proxy_usd(ledger, params, 150.0) == 1_000 + 150_000 / 150
    assert peak_liquidity_proxy_usd(ledger, params, 140.5) == pytest.approx(1_000 + 150_000 / 140.5)
    # Bank C pays USD 500 as well: its activity adds to the proxy.
    assert ledger.transfer(Leg("C", "A", Currency.USD, 50_000))
    assert peak_liquidity_proxy_usd(ledger, params, 150.0) == 1_000 + 1_000 + 500


def test_peak_proxy_keeps_the_maximum_after_money_comes_back() -> None:
    params = SimulationParams(seed=1, initial_usd=5_000, initial_jpy=1_000_000)
    ledger = new_ledger(params)
    assert ledger.transfer(Leg("A", "B", Currency.USD, 100_000))
    assert ledger.transfer(Leg("B", "A", Currency.USD, 100_000))  # A is whole again
    assert peak_liquidity_proxy_usd(ledger, params, 150.0) == 1_000


def test_peak_proxy_of_a_tiny_real_run() -> None:
    data = generate_transactions(count=1, seed=202)
    params = SimulationParams(seed=202, delay_seconds=60, failure_probability=0.0)
    results, ledger = run_model(data, Model.ATOMIC, params)
    row = data.iloc[0]
    # One settled transaction: the USD payer loses usd_amount, the JPY payer jpy_amount.
    assert results[0].status == Status.SETTLED
    expected = row.usd_amount + row.jpy_amount / row.fx_rate
    assert peak_liquidity_proxy_usd(ledger, params, row.fx_rate) == pytest.approx(expected)


# --- Day 10: Average Settlement Time and Operational Delay ---


def test_average_settlement_time_uses_settled_only_and_arrival_offset() -> None:
    results = [
        settled(1, arrival=1_000.0, delay=60.0),  # 60
        settled(2, arrival=500.0, delay=120.0),  # 120
        partial(3, 10.0),  # end_time 60: would give 60 if wrongly included
        failed(4),
    ]
    assert average_settlement_time(results) == 90.0


def test_average_settlement_time_is_nan_without_settled() -> None:
    assert math.isnan(average_settlement_time([partial(1, 1.0), failed(2)]))
    assert math.isnan(average_settlement_time([]))


def test_operational_delay_is_the_injected_delay_or_nan_without_transactions() -> None:
    params = SimulationParams(seed=1, delay_seconds=300)
    assert operational_delay(MIXED, params) == 300.0
    assert operational_delay([failed(1)], SimulationParams(seed=1, delay_seconds=0)) == 0.0
    assert math.isnan(operational_delay([], params))


# --- Day 10: properties with the real engine (seeds 201-205) ---

SEEDS = (201, 202, 203, 204, 205)
FX = 150.0


def engine_runs(initial_usd: float, failure_probability: float, delay: float):
    """Yield (model, params, data, results, ledger) for every seed and model."""
    for seed in SEEDS:
        data = generate_transactions(count=60, fx_rate=FX, seed=seed)
        params = SimulationParams(
            seed=seed,
            initial_usd=initial_usd,
            initial_jpy=initial_usd * FX,
            delay_seconds=delay,
            failure_probability=failure_probability,
        )
        for model in Model:
            results, ledger = run_model(data, model, params)
            yield model, params, data, results, ledger


@pytest.mark.parametrize("failure_probability", [0.0, 0.01, 0.05])
@pytest.mark.parametrize("delay", [0.0, 60.0, 300.0])
def test_engine_properties_under_stress(failure_probability: float, delay: float) -> None:
    for model, params, data, results, ledger in engine_runs(3_000_000, failure_probability, delay):
        row = calculate_metrics(results, data, params, ledger)
        if model == Model.SEQUENTIAL:
            assert math.isnan(row["gross_prefunding_usd"])
            assert math.isnan(row["liquidity_utilization"])
        else:
            assert 0.0 <= row["liquidity_utilization"] <= 1.0
        if row["n_settled"] > 0:
            assert row["average_settlement_time_seconds"] == pytest.approx(delay)
        total_liquidity = params.n_banks * (params.initial_usd + params.initial_jpy / FX)
        assert 0.0 <= row["peak_liquidity_proxy_usd"] <= total_liquidity * (1 + 1e-9)
        assert row["operational_delay_seconds"] == delay


def test_stress_level_really_causes_failures() -> None:
    runs = engine_runs(3_000_000, 0.0, 60.0)
    assert any(r.status == Status.FAILED for _, _, _, results, _ in runs for r in results)


@pytest.mark.parametrize("model", [Model.PREFUNDED, Model.ATOMIC])
def test_ample_liquidity_without_failures_gives_full_utilization(model: Model) -> None:
    for m, params, data, results, ledger in engine_runs(1e12, 0.0, 60.0):
        if m == model:
            assert all(r.status == Status.SETTLED for r in results)
            assert liquidity_utilization(results, data) == pytest.approx(1.0)

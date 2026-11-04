"""Tests for the ledger and shared types, plus placeholders for the required engine tests."""

import numpy as np
import pandas as pd
import pytest

from src.simulator import (
    Currency,
    EventType,
    FailureReason,
    Leg,
    Ledger,
    Model,
    SettlementResult,
    SimulationParams,
    Status,
    run_model,
    to_minor,
)
from src.transactions import bank_names, generate_transactions

USD = Currency.USD
JPY = Currency.JPY


def make_ledger(usd: int = 1_000, jpy: int = 150_000) -> Ledger:
    return Ledger(["A", "B"], {USD: usd, JPY: jpy})


def snapshot(ledger: Ledger) -> list[int]:
    return [
        value
        for bank in ("A", "B")
        for currency in Currency
        for value in (
            ledger.balance(bank, currency),
            ledger.reserved(bank, currency),
            ledger.peak_drawdown(bank, currency),
        )
    ]


def make_result(**changes) -> SettlementResult:
    fields = {
        "transaction_id": 1,
        "model": Model.SEQUENTIAL,
        "status": Status.SETTLED,
        "failure_reason": None,
        "usd_leg_done": True,
        "jpy_leg_done": True,
        "arrival_time": 0.0,
        "start_time": 0.0,
        "end_time": 60.0,
        "principal_exposure_usd": 0.0,
    }
    return SettlementResult(**(fields | changes))


# --- Ledger ---


def test_transfer_moves_funds_and_keeps_currency_total() -> None:
    ledger = make_ledger()
    assert ledger.transfer(Leg("A", "B", USD, 300))
    assert ledger.balance("A", USD) == 700
    assert ledger.balance("B", USD) == 1_300
    assert ledger.total(USD) == 2_000
    assert ledger.total(JPY) == 300_000


def test_transfer_of_exact_balance_succeeds() -> None:
    ledger = make_ledger()
    assert ledger.transfer(Leg("A", "B", USD, 1_000))
    assert ledger.balance("A", USD) == 0


def test_transfer_short_of_funds_changes_nothing() -> None:
    ledger = make_ledger()
    before = snapshot(ledger)
    assert not ledger.transfer(Leg("A", "B", USD, 1_001))
    assert snapshot(ledger) == before


def test_reserve_lowers_available_but_not_balance() -> None:
    ledger = make_ledger()
    assert ledger.reserve("A", USD, 400)
    assert ledger.balance("A", USD) == 1_000
    assert ledger.available("A", USD) == 600


def test_reserve_short_of_funds_changes_nothing() -> None:
    ledger = make_ledger()
    ledger.reserve("A", USD, 800)
    before = snapshot(ledger)
    assert not ledger.reserve("A", USD, 201)
    assert snapshot(ledger) == before


def test_reserved_funds_cannot_be_spent_by_normal_transfer() -> None:
    ledger = make_ledger()
    ledger.reserve("A", USD, 800)
    assert not ledger.transfer(Leg("A", "B", USD, 201))


def test_transfer_from_reserved_uses_the_reservation() -> None:
    ledger = make_ledger()
    ledger.reserve("A", USD, 400)
    assert ledger.transfer(Leg("A", "B", USD, 400), from_reserved=True)
    assert ledger.balance("A", USD) == 600
    assert ledger.reserved("A", USD) == 0
    assert ledger.available("A", USD) == 600


def test_transfer_from_reserved_above_reservation_raises() -> None:
    ledger = make_ledger()
    ledger.reserve("A", USD, 100)
    with pytest.raises(ValueError):
        ledger.transfer(Leg("A", "B", USD, 101), from_reserved=True)


def test_release_restores_available() -> None:
    ledger = make_ledger()
    ledger.reserve("A", USD, 400)
    ledger.release("A", USD, 400)
    assert ledger.available("A", USD) == 1_000
    with pytest.raises(ValueError):
        ledger.release("A", USD, 1)


def test_commit_both_applies_both_legs() -> None:
    ledger = make_ledger()
    assert ledger.commit_both(Leg("A", "B", USD, 100), Leg("B", "A", JPY, 15_000))
    assert ledger.balance("A", USD) == 900
    assert ledger.balance("B", USD) == 1_100
    assert ledger.balance("A", JPY) == 165_000
    assert ledger.balance("B", JPY) == 135_000
    assert ledger.total(USD) == 2_000
    assert ledger.total(JPY) == 300_000
    assert ledger.peak_drawdown("A", USD) == 100
    assert ledger.peak_drawdown("B", JPY) == 15_000


@pytest.mark.parametrize(
    ("usd_amount", "jpy_amount"),
    [(1_001, 15_000), (100, 150_001), (1_001, 150_001)],
)
def test_commit_both_short_on_any_leg_changes_nothing(
    usd_amount: int, jpy_amount: int
) -> None:
    ledger = make_ledger()
    before = snapshot(ledger)
    legs = Leg("A", "B", USD, usd_amount), Leg("B", "A", JPY, jpy_amount)
    assert not ledger.commit_both(*legs)
    assert snapshot(ledger) == before


def test_commit_both_counts_reserved_funds_as_unavailable() -> None:
    ledger = make_ledger()
    ledger.reserve("B", JPY, 140_000)
    before = snapshot(ledger)
    assert not ledger.commit_both(Leg("A", "B", USD, 100), Leg("B", "A", JPY, 15_000))
    assert snapshot(ledger) == before


def test_commit_both_unknown_bank_changes_nothing() -> None:
    ledger = make_ledger()
    before = snapshot(ledger)
    with pytest.raises(KeyError):
        ledger.commit_both(Leg("A", "B", USD, 100), Leg("B", "Z", JPY, 15_000))
    assert snapshot(ledger) == before


def test_peak_drawdown_keeps_maximum_and_counts_reservations() -> None:
    ledger = make_ledger()
    ledger.transfer(Leg("A", "B", USD, 300))
    assert ledger.peak_drawdown("A", USD) == 300
    ledger.reserve("A", USD, 200)
    assert ledger.peak_drawdown("A", USD) == 500
    ledger.release("A", USD, 200)
    ledger.transfer(Leg("B", "A", USD, 300))
    assert ledger.peak_drawdown("A", USD) == 500


def test_peak_drawdown_stays_zero_for_receiver() -> None:
    ledger = make_ledger()
    ledger.transfer(Leg("A", "B", USD, 300))
    assert ledger.peak_drawdown("B", USD) == 0


def test_paying_from_reservation_does_not_count_twice() -> None:
    ledger = make_ledger()
    ledger.reserve("A", USD, 400)
    ledger.transfer(Leg("A", "B", USD, 400), from_reserved=True)
    assert ledger.peak_drawdown("A", USD) == 400


@pytest.mark.parametrize("amount", [0, -1, 1.5, True])
def test_bad_amount_is_rejected(amount) -> None:
    ledger = make_ledger()
    with pytest.raises(ValueError):
        ledger.transfer(Leg("A", "B", USD, amount))
    with pytest.raises(ValueError):
        ledger.reserve("A", USD, amount)


def test_payer_and_receiver_must_differ() -> None:
    with pytest.raises(ValueError):
        make_ledger().transfer(Leg("A", "A", USD, 1))


def test_commit_both_rejects_same_currency() -> None:
    with pytest.raises(ValueError):
        make_ledger().commit_both(Leg("A", "B", USD, 1), Leg("B", "A", USD, 1))


def test_to_minor_gives_exact_integers() -> None:
    assert to_minor(100_000.29) == 10_000_029
    assert to_minor(0.07) == 7
    assert isinstance(to_minor(1.5), int)


# --- Shared types ---


def test_enums_are_written_as_the_agreed_words() -> None:
    assert [str(s) for s in Status] == ["settled", "partial", "failed"]
    assert str(FailureReason.INSUFFICIENT_FUNDS) == "insufficient_funds"
    assert [str(m) for m in Model] == ["sequential", "prefunded", "atomic"]


def test_valid_results_are_accepted() -> None:
    make_result()
    make_result(
        status=Status.PARTIAL,
        failure_reason=FailureReason.TECHNICAL_FAILURE,
        jpy_leg_done=False,
    )
    make_result(
        status=Status.FAILED,
        failure_reason=FailureReason.INSUFFICIENT_FUNDS,
        usd_leg_done=False,
        jpy_leg_done=False,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"jpy_leg_done": False},
        {"status": Status.PARTIAL, "failure_reason": FailureReason.TIMEOUT},
        {"status": Status.FAILED, "failure_reason": FailureReason.TIMEOUT},
        {"failure_reason": FailureReason.TIMEOUT},
        {"status": Status.PARTIAL, "jpy_leg_done": False},
        {"usd_leg_done": np.True_, "jpy_leg_done": np.True_},
        {"usd_leg_done": 1},
        {
            "model": Model.ATOMIC,
            "status": Status.PARTIAL,
            "failure_reason": FailureReason.TECHNICAL_FAILURE,
            "jpy_leg_done": False,
        },
        {"principal_exposure_usd": 5.0},
        {
            "status": Status.PARTIAL,
            "failure_reason": FailureReason.TECHNICAL_FAILURE,
            "jpy_leg_done": False,
            "principal_exposure_usd": -5.0,
        },
        {"start_time": -1.0},
        {"end_time": -1.0},
    ],
)
def test_inconsistent_results_are_rejected(changes: dict) -> None:
    with pytest.raises(ValueError):
        make_result(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"failure_probability": 1.5},
        {"failure_probability": -0.1},
        {"initial_usd": -1},
        {"delay_seconds": -1},
        {"initial_usd": float("nan")},
        {"delay_seconds": float("inf")},
    ],
)
def test_bad_params_are_rejected(changes: dict) -> None:
    with pytest.raises(ValueError):
        SimulationParams(seed=1, **changes)


@pytest.mark.parametrize("seed", [None, 1.5, True])
def test_bad_seed_is_rejected(seed) -> None:
    with pytest.raises(ValueError):
        SimulationParams(seed=seed)


# --- Model A (Sequential) ---

TX_COLUMNS = [
    "transaction_id",
    "arrival_time",
    "usd_payer",
    "jpy_payer",
    "usd_amount",
    "jpy_amount",
    "fx_rate",
    "failure_draw",
]
# Seeds 1-30 are main experiment seeds and 101-110 calibration seeds; tests use others.
TEST_SEEDS = [201, 202, 203, 204, 205]


def tx(
    transaction_id: int,
    arrival_time: float,
    usd_payer: str,
    jpy_payer: str,
    usd_amount: float,
    jpy_amount: float,
    failure_draw: float = 0.5,
) -> dict:
    """One transaction row. The default draw 0.5 never hits a failure probability <= 5%."""
    return {
        "transaction_id": transaction_id,
        "arrival_time": arrival_time,
        "usd_payer": usd_payer,
        "jpy_payer": jpy_payer,
        "usd_amount": usd_amount,
        "jpy_amount": jpy_amount,
        "fx_rate": 150.0,
        "failure_draw": failure_draw,
    }


def frame(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=TX_COLUMNS)


def params_a(**changes) -> SimulationParams:
    """Small balances: every bank starts with USD 1,000 and JPY 150,000."""
    values = {
        "seed": 1,
        "initial_usd": 1_000,
        "initial_jpy": 150_000,
        "delay_seconds": 60,
        "failure_probability": 0.01,
    }
    return SimulationParams(**(values | changes))


def run_a(*rows: dict, **changes) -> tuple[list[SettlementResult], Ledger]:
    return run_model(frame(*rows), Model.SEQUENTIAL, params_a(**changes))


def balances(ledger: Ledger, banks: tuple[str, ...] = ("A", "B")) -> dict[str, float]:
    """Balances in whole currency units, keyed like 'A USD'."""
    return {
        f"{bank} {currency}": ledger.balance(bank, currency) / 100
        for currency in Currency
        for bank in banks
    }


def test_model_a_settled_moves_both_legs_after_the_delay() -> None:
    results, ledger = run_a(tx(1, 0.0, "A", "B", 100, 15_000))
    (r,) = results
    assert r.model == Model.SEQUENTIAL
    assert (r.status, r.failure_reason) == (Status.SETTLED, None)
    assert (r.usd_leg_done, r.jpy_leg_done) == (True, True)
    assert (r.arrival_time, r.start_time, r.end_time) == (0.0, 0.0, 60.0)
    assert r.principal_exposure_usd == 0.0
    assert balances(ledger) == {
        "A USD": 900, "B USD": 1_100, "A JPY": 165_000, "B JPY": 135_000,
    }  # fmt: skip


def test_model_a_second_leg_technical_failure_leaves_partial() -> None:
    results, ledger = run_a(tx(1, 5.0, "A", "B", 100, 15_000, failure_draw=0.005))
    (r,) = results
    assert (r.status, r.failure_reason) == (Status.PARTIAL, FailureReason.TECHNICAL_FAILURE)
    assert (r.usd_leg_done, r.jpy_leg_done) == (True, False)
    assert (r.arrival_time, r.start_time, r.end_time) == (5.0, 5.0, 65.0)
    assert r.principal_exposure_usd == 100.0
    assert balances(ledger) == {
        "A USD": 900, "B USD": 1_100, "A JPY": 150_000, "B JPY": 150_000,
    }  # fmt: skip


def test_model_a_first_leg_shortage_fails_and_moves_nothing() -> None:
    results, ledger = run_a(tx(1, 5.0, "A", "B", 1_001, 15_000))
    (r,) = results
    assert (r.status, r.failure_reason) == (Status.FAILED, FailureReason.INSUFFICIENT_FUNDS)
    assert (r.usd_leg_done, r.jpy_leg_done) == (False, False)
    assert (r.arrival_time, r.start_time, r.end_time) == (5.0, 5.0, 5.0)
    assert r.principal_exposure_usd == 0.0
    assert balances(ledger) == {
        "A USD": 1_000, "B USD": 1_000, "A JPY": 150_000, "B JPY": 150_000,
    }  # fmt: skip


def test_model_a_second_leg_shortage_leaves_partial() -> None:
    results, ledger = run_a(tx(1, 0.0, "A", "B", 100, 150_001))
    (r,) = results
    assert (r.status, r.failure_reason) == (Status.PARTIAL, FailureReason.INSUFFICIENT_FUNDS)
    assert (r.usd_leg_done, r.jpy_leg_done) == (True, False)
    assert (r.start_time, r.end_time) == (0.0, 60.0)
    assert r.principal_exposure_usd == 100.0
    assert balances(ledger) == {
        "A USD": 900, "B USD": 1_100, "A JPY": 150_000, "B JPY": 150_000,
    }  # fmt: skip


def test_model_a_failure_hit_and_shortage_together_is_technical_failure() -> None:
    results, _ = run_a(tx(1, 0.0, "A", "B", 100, 150_001, failure_draw=0.0))
    (r,) = results
    assert (r.status, r.failure_reason) == (Status.PARTIAL, FailureReason.TECHNICAL_FAILURE)


def test_model_a_failure_draw_equal_to_probability_is_not_a_hit() -> None:
    results, _ = run_a(tx(1, 0.0, "A", "B", 100, 15_000, failure_draw=0.01))
    assert results[0].status == Status.SETTLED


def test_model_a_probability_zero_never_hits() -> None:
    rows = [tx(1, 0.0, "A", "B", 10, 1_500, failure_draw=0.0)]
    rows.append(tx(2, 10.0, "A", "B", 10, 1_500, failure_draw=1e-12))
    results, _ = run_a(*rows, failure_probability=0.0)
    assert [r.status for r in results] == [Status.SETTLED, Status.SETTLED]


def test_model_a_exact_balance_payment_succeeds() -> None:
    results, ledger = run_a(tx(1, 0.0, "A", "B", 1_000, 150_000))
    assert results[0].status == Status.SETTLED
    assert balances(ledger) == {
        "A USD": 0, "B USD": 2_000, "A JPY": 300_000, "B JPY": 0,
    }  # fmt: skip


def test_model_a_jpy_not_yet_received_cannot_be_spent_during_the_delay() -> None:
    # Tx 2 pays A its JPY at t=70, but tx 1's second leg needs A's JPY at t=60.
    results, ledger = run_a(
        tx(1, 0.0, "B", "A", 10, 1_500),
        tx(2, 10.0, "A", "B", 4, 600),
        initial_usd=1_000,
        initial_jpy=1_000,
    )
    first, second = results
    assert (first.status, first.failure_reason) == (
        Status.PARTIAL,
        FailureReason.INSUFFICIENT_FUNDS,
    )
    assert first.end_time == 60.0
    assert first.principal_exposure_usd == 10.0
    assert (second.status, second.end_time) == (Status.SETTLED, 70.0)
    assert balances(ledger) == {
        "A USD": 1_006, "B USD": 994, "A JPY": 1_600, "B JPY": 400,
    }  # fmt: skip


def test_model_a_received_funds_are_usable_from_the_time_they_arrive() -> None:
    # Tx 2 arrives at t=60, the same time as tx 1's second leg. USD that B received
    # at t=0 is usable at once; JPY that A receives at t=60 is usable at t=120.
    results, ledger = run_a(
        tx(1, 0.0, "A", "B", 100, 15_000),
        tx(2, 60.0, "B", "A", 1_100, 165_000),
    )
    assert [r.status for r in results] == [Status.SETTLED, Status.SETTLED]
    assert [r.end_time for r in results] == [60.0, 120.0]
    assert balances(ledger) == {
        "A USD": 2_000, "B USD": 0, "A JPY": 0, "B JPY": 300_000,
    }  # fmt: skip


def test_model_a_second_leg_event_sorts_before_an_arrival_at_equal_time() -> None:
    assert EventType.DELAYED_STEP < EventType.ARRIVAL


def test_model_a_delay_zero_completes_both_legs_at_arrival() -> None:
    results, ledger = run_a(
        tx(1, 7.0, "A", "B", 100, 15_000),
        tx(2, 7.0, "B", "A", 100, 165_000),
        delay_seconds=0,
    )
    # Note: this does not discriminate second-leg vs arrival order. In Model A the two
    # touch different currencies (JPY vs USD); the order becomes observable in Model B.
    assert [r.status for r in results] == [Status.SETTLED, Status.SETTLED]
    assert all(r.start_time == r.end_time == 7.0 for r in results)
    assert balances(ledger) == {
        "A USD": 1_000, "B USD": 1_000, "A JPY": 0, "B JPY": 300_000,
    }  # fmt: skip


def test_model_a_burst_arrival_is_served_in_transaction_id_order() -> None:
    # Rows are listed in reverse order on purpose. USD 1,000 covers only one of the two.
    # This tests the transaction_id tiebreak, not second-leg vs arrival order (see above).
    results, ledger = run_a(
        tx(2, 0.0, "A", "B", 600, 90_000),
        tx(1, 0.0, "A", "B", 600, 90_000),
    )
    assert [r.transaction_id for r in results] == [1, 2]
    assert results[0].status == Status.SETTLED
    assert (results[1].status, results[1].failure_reason) == (
        Status.FAILED,
        FailureReason.INSUFFICIENT_FUNDS,
    )
    assert balances(ledger)["A USD"] == 400


def test_model_a_same_time_second_legs_run_in_transaction_id_order() -> None:
    # Both pay JPY from B at t=60; B holds 150,000 and each needs 100,000.
    # This tests the transaction_id tiebreak, not second-leg vs arrival order (see above).
    results, ledger = run_a(
        tx(2, 0.0, "A", "B", 10, 100_000),
        tx(1, 0.0, "A", "B", 10, 100_000),
    )
    assert [r.status for r in results] == [Status.SETTLED, Status.PARTIAL]
    assert results[1].failure_reason == FailureReason.INSUFFICIENT_FUNDS
    assert results[1].principal_exposure_usd == 10.0
    assert balances(ledger)["B JPY"] == 50_000


def test_model_a_with_three_banks_moves_only_the_named_banks() -> None:
    results, ledger = run_a(tx(1, 0.0, "C", "A", 100, 15_000), n_banks=3)
    assert results[0].status == Status.SETTLED
    assert balances(ledger, ("A", "B", "C")) == {
        "A USD": 1_100, "B USD": 1_000, "C USD": 900,
        "A JPY": 135_000, "B JPY": 150_000, "C JPY": 165_000,
    }  # fmt: skip


def test_model_a_bank_in_no_transaction_still_counts_in_ledger_totals() -> None:
    _, ledger = run_a(tx(1, 0.0, "A", "B", 100, 15_000), n_banks=4)
    assert ledger.balance("D", USD) == to_minor(1_000)
    assert ledger.total(USD) == 4 * to_minor(1_000)
    assert ledger.total(JPY) == 4 * to_minor(150_000)


@pytest.mark.parametrize("row", [tx(1, 0.0, "Z", "B", 1, 150), tx(1, 0.0, "A", "C", 1, 150)])
def test_model_a_unknown_bank_raises_key_error(row: dict) -> None:
    with pytest.raises(KeyError):
        run_a(row)  # default n_banks = 2, so "C" and "Z" are unknown


@pytest.mark.parametrize("n_banks", [1, 11, 0, 2.5, True, None])
def test_bad_n_banks_is_rejected(n_banks) -> None:
    with pytest.raises(ValueError):
        SimulationParams(seed=1, n_banks=n_banks)


def test_model_a_duplicate_transaction_id_raises() -> None:
    with pytest.raises(ValueError):
        run_a(tx(1, 0.0, "A", "B", 1, 150), tx(1, 10.0, "A", "B", 1, 150))


def test_model_a_empty_input_gives_no_results_and_an_untouched_ledger() -> None:
    results, ledger = run_a()
    assert results == []
    assert ledger.total(USD) == 2 * to_minor(1_000)
    assert ledger.total(JPY) == 2 * to_minor(150_000)
    assert [ledger.peak_drawdown(b, c) for b in ("A", "B") for c in Currency] == [0] * 4


# Low liquidity so that shortages really occur: USD 1,000,000 per bank is at most
# one large payment. Each case is (n_banks, arrival pattern).
STRESS_CASES = [(2, "sequential"), (3, "burst"), (5, "sequential"), (10, "burst")]


def stress_run(seed: int, n_banks: int, arrival: str, probability: float = 0.05):
    data = generate_transactions(count=200, seed=seed, n_banks=n_banks, arrival=arrival)
    params = SimulationParams(
        seed=seed,
        initial_usd=1_000_000,
        initial_jpy=150_000_000,
        failure_probability=probability,
        n_banks=n_banks,
    )
    return data, params, run_model(data, Model.SEQUENTIAL, params)


def expected_balances(data: pd.DataFrame, results, params) -> dict[tuple[str, Currency], int]:
    """Rebuild every balance from the result flags, without using the ledger."""
    expected = {
        (bank, currency): to_minor(
            params.initial_usd if currency == USD else params.initial_jpy
        )
        for bank in bank_names(params.n_banks)
        for currency in Currency
    }
    rows = data.set_index("transaction_id")
    for r in results:
        row = rows.loc[r.transaction_id]
        if r.usd_leg_done:
            amount = to_minor(row["usd_amount"])
            expected[(row["usd_payer"], USD)] -= amount
            expected[(row["jpy_payer"], USD)] += amount
        if r.jpy_leg_done:
            amount = to_minor(row["jpy_amount"])
            expected[(row["jpy_payer"], JPY)] -= amount
            expected[(row["usd_payer"], JPY)] += amount
    return expected


@pytest.mark.parametrize("seed", TEST_SEEDS)
@pytest.mark.parametrize(("n_banks", "arrival"), STRESS_CASES)
def test_model_a_keeps_totals_and_status_consistent_under_stress(
    seed: int, n_banks: int, arrival: str
) -> None:
    data, params, (results, ledger) = stress_run(seed, n_banks, arrival)
    assert [r.transaction_id for r in results] == sorted(data["transaction_id"])
    # Not vacuous: shortages happened.
    assert any(r.failure_reason == FailureReason.INSUFFICIENT_FUNDS for r in results)
    initial = {USD: to_minor(params.initial_usd), JPY: to_minor(params.initial_jpy)}
    for currency in Currency:
        assert ledger.total(currency) == n_banks * initial[currency]
    for r in results:
        legs = r.usd_leg_done + r.jpy_leg_done
        assert (r.status == Status.SETTLED) == (legs == 2)
        assert (r.status == Status.PARTIAL) == (legs == 1)
        assert (r.status == Status.FAILED) == (legs == 0)
        assert r.jpy_leg_done <= r.usd_leg_done  # the JPY leg never goes first
    expected = expected_balances(data, results, params)
    for (bank, currency), amount in expected.items():
        assert ledger.balance(bank, currency) == amount
        assert amount >= 0
        # Peak drawdown stays within [0, initial] and covers the final drawdown.
        peak = ledger.peak_drawdown(bank, currency)
        assert max(0, initial[currency] - amount) <= peak <= initial[currency]
        assert ledger.reserved(bank, currency) == 0


def naive_model_a(data: pd.DataFrame, params: SimulationParams):
    """Plain-dict Model A used as an oracle: no Ledger, no simulator helpers."""
    bal = {}
    for bank in bank_names(params.n_banks):
        bal[(bank, "USD")] = to_minor(params.initial_usd)
        bal[(bank, "JPY")] = to_minor(params.initial_jpy)
    rows = {int(r.transaction_id): r for r in data.itertuples()}
    todo = [(r.arrival_time, 1, tid) for tid, r in rows.items()]  # kind 0 = second leg
    out = {}
    while todo:
        todo.sort()
        now, kind, tid = todo.pop(0)
        r = rows[tid]
        usd, jpy = to_minor(r.usd_amount), to_minor(r.jpy_amount)
        if kind == 1 and bal[(r.usd_payer, "USD")] < usd:
            out[tid] = ("failed", "insufficient_funds")
        elif kind == 1:
            bal[(r.usd_payer, "USD")] -= usd
            bal[(r.jpy_payer, "USD")] += usd
            todo.append((now + params.delay_seconds, 0, tid))
        elif r.failure_draw < params.failure_probability:
            out[tid] = ("partial", "technical_failure")
        elif bal[(r.jpy_payer, "JPY")] < jpy:
            out[tid] = ("partial", "insufficient_funds")
        else:
            bal[(r.jpy_payer, "JPY")] -= jpy
            bal[(r.usd_payer, "JPY")] += jpy
            out[tid] = ("settled", None)
    return out, bal


def outcome_kind(status: Status, reason: FailureReason | None) -> str:
    return f"{status}/{reason}"


@pytest.mark.parametrize("seed", TEST_SEEDS)
@pytest.mark.parametrize(("n_banks", "arrival"), STRESS_CASES)
def test_model_a_matches_a_naive_oracle_and_failure_rules(
    seed: int, n_banks: int, arrival: str
) -> None:
    data, params, (results, ledger) = stress_run(seed, n_banks, arrival)
    expected, bal = naive_model_a(data, params)
    draws = data.set_index("transaction_id")["failure_draw"]
    for r in results:
        assert (str(r.status), r.failure_reason and str(r.failure_reason)) == expected[
            r.transaction_id
        ]
        hit = r.usd_leg_done and draws[r.transaction_id] < params.failure_probability
        assert (r.failure_reason == FailureReason.TECHNICAL_FAILURE) == hit
        if r.status == Status.FAILED:
            assert r.failure_reason == FailureReason.INSUFFICIENT_FUNDS
    for (bank, currency), amount in bal.items():
        assert ledger.balance(bank, Currency(currency)) == amount


def test_model_a_stress_cases_cover_all_four_outcomes() -> None:
    kinds = set()
    for seed in TEST_SEEDS:
        for n_banks, arrival in STRESS_CASES:
            _, _, (results, _) = stress_run(seed, n_banks, arrival)
            kinds |= {outcome_kind(r.status, r.failure_reason) for r in results}
    assert kinds == {
        "failed/insufficient_funds",
        "partial/insufficient_funds",
        "partial/technical_failure",
        "settled/None",
    }


def test_model_a_peak_drawdown_is_not_the_sum_of_payments() -> None:
    # Bank A's USD: pays 100 (drawdown 100), receives 50 (50), pays 30 (80). Peak stays 100.
    results, ledger = run_a(
        tx(1, 0.0, "A", "B", 100, 15_000),
        tx(2, 10.0, "B", "A", 50, 7_500),
        tx(3, 20.0, "A", "B", 30, 4_500),
    )
    assert all(r.status == Status.SETTLED for r in results)
    assert ledger.balance("A", USD) == to_minor(920)
    assert ledger.peak_drawdown("A", USD) == to_minor(100)


@pytest.mark.parametrize("column", ["failure_draw", "arrival_time"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_model_a_non_finite_draw_or_time_raises(column: str, bad: float) -> None:
    row = tx(1, 0.0, "A", "B", 1, 150) | {column: bad}
    with pytest.raises(ValueError):
        run_a(row)


@pytest.mark.parametrize("seed", TEST_SEEDS)
def test_model_a_same_data_and_params_give_identical_results(seed: int) -> None:
    data, params, (results, ledger) = stress_run(seed, 3, "burst")
    results_again, ledger_again = run_model(data, Model.SEQUENTIAL, params)
    assert results == results_again
    assert expected_balances(data, results, params) == expected_balances(
        data, results_again, params
    )
    assert [ledger.balance(b, c) for b in "ABC" for c in Currency] == [
        ledger_again.balance(b, c) for b in "ABC" for c in Currency
    ]


@pytest.mark.parametrize("seed", TEST_SEEDS)
def test_model_a_does_not_change_the_input_data(seed: int) -> None:
    data = generate_transactions(count=100, seed=seed, n_banks=3)
    before = data.copy()
    run_model(data, Model.SEQUENTIAL, SimulationParams(seed=seed, n_banks=3))
    pd.testing.assert_frame_equal(data, before)


@pytest.mark.parametrize("seed", TEST_SEEDS)
def test_model_a_exposure_does_not_fall_as_failure_probability_rises(seed: int) -> None:
    data = generate_transactions(count=500, seed=seed)
    totals = []
    for probability in (0.0, 0.01, 0.05):
        params = SimulationParams(
            seed=seed,
            initial_usd=1e12,
            initial_jpy=1.5e14,
            failure_probability=probability,
        )
        results, _ = run_model(data, Model.SEQUENTIAL, params)
        assert all(r.failure_reason != FailureReason.INSUFFICIENT_FUNDS for r in results)
        totals.append(sum(r.principal_exposure_usd for r in results))
        hit_amounts = data.loc[data["failure_draw"] < probability, "usd_amount"]
        assert totals[-1] == pytest.approx(hit_amounts.sum())
    assert totals[0] == 0.0
    assert totals[0] <= totals[1] <= totals[2]
    assert totals[2] > totals[0]


# --- Model B (Prefunded) ---


def run_b(*rows: dict, **changes) -> tuple[list[SettlementResult], Ledger]:
    return run_model(frame(*rows), Model.PREFUNDED, params_a(**changes))


def all_reserved(ledger: Ledger, banks: tuple[str, ...] = ("A", "B")) -> list[int]:
    return [ledger.reserved(bank, currency) for bank in banks for currency in Currency]


def all_peaks(ledger: Ledger, banks: tuple[str, ...] = ("A", "B")) -> list[int]:
    return [ledger.peak_drawdown(bank, currency) for bank in banks for currency in Currency]


def test_model_b_jpy_shortage_leaves_peak_drawdown_unchanged() -> None:
    results, ledger = run_b(tx(1, 0.0, "A", "B", 900, 200_000))
    assert results[0].status == Status.FAILED
    assert ledger.peak_drawdown("A", USD) == 0
    assert all_peaks(ledger) == [0, 0, 0, 0]
    assert snapshot(ledger) == snapshot(make_ledger(to_minor(1_000), to_minor(150_000)))


def test_model_b_successful_reservation_raises_peak_by_both_legs() -> None:
    _, ledger = run_b(tx(1, 0.0, "A", "B", 100, 15_000))
    assert ledger.peak_drawdown("A", USD) == to_minor(100)
    assert ledger.peak_drawdown("B", JPY) == to_minor(15_000)
    assert ledger.peak_drawdown("A", JPY) == 0
    assert ledger.peak_drawdown("B", USD) == 0


def test_can_reserve_both_changes_nothing_and_checks_input() -> None:
    ledger = make_ledger()
    before = snapshot(ledger)
    assert ledger.can_reserve_both(Leg("A", "B", USD, 1_000), Leg("B", "A", JPY, 150_000))
    assert not ledger.can_reserve_both(Leg("A", "B", USD, 1_001), Leg("B", "A", JPY, 1))
    assert not ledger.can_reserve_both(Leg("A", "B", USD, 1), Leg("B", "A", JPY, 150_001))
    assert snapshot(ledger) == before
    with pytest.raises(ValueError):
        ledger.can_reserve_both(Leg("A", "B", USD, 1), Leg("B", "A", USD, 1))
    with pytest.raises(KeyError):
        ledger.can_reserve_both(Leg("A", "B", USD, 1), Leg("B", "Z", JPY, 1))


def test_model_b_settled_pays_usd_at_arrival_and_jpy_after_the_delay() -> None:
    results, ledger = run_b(tx(1, 0.0, "A", "B", 100, 15_000))
    (r,) = results
    assert r.model == Model.PREFUNDED
    assert (r.status, r.failure_reason) == (Status.SETTLED, None)
    assert (r.usd_leg_done, r.jpy_leg_done) == (True, True)
    assert (r.arrival_time, r.start_time, r.end_time) == (0.0, 0.0, 60.0)
    assert r.principal_exposure_usd == 0.0
    assert balances(ledger) == {
        "A USD": 900, "B USD": 1_100, "A JPY": 165_000, "B JPY": 135_000,
    }  # fmt: skip
    assert all_reserved(ledger) == [0, 0, 0, 0]


def test_model_b_usd_reservation_fails_when_usd_payer_is_short() -> None:
    results, ledger = run_b(tx(1, 5.0, "A", "B", 1_001, 15_000))
    (r,) = results
    assert (r.status, r.failure_reason) == (Status.FAILED, FailureReason.INSUFFICIENT_FUNDS)
    assert (r.usd_leg_done, r.jpy_leg_done) == (False, False)
    assert (r.arrival_time, r.start_time, r.end_time) == (5.0, 5.0, 5.0)
    assert r.principal_exposure_usd == 0.0
    assert balances(ledger) == {
        "A USD": 1_000, "B USD": 1_000, "A JPY": 150_000, "B JPY": 150_000,
    }  # fmt: skip
    assert all_reserved(ledger) == [0, 0, 0, 0]


def test_model_b_jpy_shortage_reserves_nothing() -> None:
    results, ledger = run_b(tx(1, 5.0, "A", "B", 100, 150_001))
    (r,) = results
    assert (r.status, r.failure_reason) == (Status.FAILED, FailureReason.INSUFFICIENT_FUNDS)
    assert (r.usd_leg_done, r.jpy_leg_done) == (False, False)
    assert r.end_time == 5.0
    assert balances(ledger) == {
        "A USD": 1_000, "B USD": 1_000, "A JPY": 150_000, "B JPY": 150_000,
    }  # fmt: skip
    assert all_reserved(ledger) == [0, 0, 0, 0]
    assert all_peaks(ledger) == [0, 0, 0, 0]  # nothing was even set aside temporarily


def test_model_b_technical_failure_leaves_partial_and_releases_the_jpy_reservation() -> None:
    results, ledger = run_b(tx(1, 5.0, "A", "B", 100, 15_000, failure_draw=0.005))
    (r,) = results
    assert (r.status, r.failure_reason) == (Status.PARTIAL, FailureReason.TECHNICAL_FAILURE)
    assert (r.usd_leg_done, r.jpy_leg_done) == (True, False)
    assert (r.arrival_time, r.start_time, r.end_time) == (5.0, 5.0, 65.0)
    assert r.principal_exposure_usd == 100.0
    assert balances(ledger) == {
        "A USD": 900, "B USD": 1_100, "A JPY": 150_000, "B JPY": 150_000,
    }  # fmt: skip
    assert all_reserved(ledger) == [0, 0, 0, 0]


def test_model_b_reservation_blocks_a_later_arrival_while_it_is_held() -> None:
    # Tx 1 holds all of B's JPY (150,000) until t=60. Tx 2 arrives at t=10 and cannot
    # reserve any of it, although in Model A the JPY would still be there at t=10.
    results, ledger = run_b(
        tx(1, 0.0, "A", "B", 100, 150_000),
        tx(2, 10.0, "A", "B", 10, 1_500),
    )
    assert [r.status for r in results] == [Status.SETTLED, Status.FAILED]
    assert results[1].failure_reason == FailureReason.INSUFFICIENT_FUNDS
    assert results[1].end_time == 10.0
    assert all_reserved(ledger) == [0, 0, 0, 0]


def test_model_b_failed_draw_releases_funds_before_a_same_time_arrival() -> None:
    # Tx 1 (technical failure) frees B's 100,000 JPY at t=60, the same time as tx 2
    # arrives and needs 120,000 of B's 150,000. If the arrival ran first, only 50,000
    # would be available and tx 2 would fail.
    results, ledger = run_b(
        tx(1, 0.0, "A", "B", 600, 100_000, failure_draw=0.0),
        tx(2, 60.0, "A", "B", 100, 120_000),
    )
    first, second = results
    assert (first.status, first.failure_reason) == (
        Status.PARTIAL,
        FailureReason.TECHNICAL_FAILURE,
    )
    assert (second.status, second.end_time) == (Status.SETTLED, 120.0)
    assert balances(ledger) == {
        "A USD": 300, "B USD": 1_700, "A JPY": 270_000, "B JPY": 30_000,
    }  # fmt: skip
    assert all_reserved(ledger) == [0, 0, 0, 0]


def test_model_b_completed_second_leg_is_received_before_a_same_time_arrival() -> None:
    # Tx 1 pays A 15,000 JPY at t=60, so A holds 165,000. Tx 2 arrives at t=60 and needs
    # all 165,000 from A. If the arrival ran first, A would hold only 150,000 and fail.
    results, ledger = run_b(
        tx(1, 0.0, "A", "B", 100, 15_000),
        tx(2, 60.0, "B", "A", 1_100, 165_000),
    )
    assert [r.status for r in results] == [Status.SETTLED, Status.SETTLED]
    assert [r.end_time for r in results] == [60.0, 120.0]
    assert balances(ledger) == {
        "A USD": 2_000, "B USD": 0, "A JPY": 0, "B JPY": 300_000,
    }  # fmt: skip
    assert all_reserved(ledger) == [0, 0, 0, 0]


# --- Model C (Atomic PvP) ---


def run_c(*rows: dict, **changes) -> tuple[list[SettlementResult], Ledger]:
    return run_model(frame(*rows), Model.ATOMIC, params_a(**changes))


def untouched_c_state() -> list[int]:
    """Snapshot of a ledger nobody has used (balances, reserved, peaks)."""
    return snapshot(make_ledger(to_minor(1_000), to_minor(150_000)))


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (tx(1, 5.0, "A", "B", 1_001, 15_000), FailureReason.INSUFFICIENT_FUNDS),  # USD short
        (tx(1, 5.0, "A", "B", 100, 150_001), FailureReason.INSUFFICIENT_FUNDS),  # JPY short
        (tx(1, 5.0, "A", "B", 1_001, 150_001), FailureReason.INSUFFICIENT_FUNDS),  # both short
        (tx(1, 5.0, "A", "B", 100, 15_000, failure_draw=0.0), FailureReason.TECHNICAL_FAILURE),
        # Funds are checked first: short and hit by the draw gives insufficient_funds.
        (tx(1, 5.0, "A", "B", 100, 150_001, failure_draw=0.0), FailureReason.INSUFFICIENT_FUNDS),
        (tx(1, 5.0, "A", "B", 1_001, 15_000, failure_draw=0.0), FailureReason.INSUFFICIENT_FUNDS),
    ],
)
def test_model_c_failure_leaves_every_balance_reservation_and_peak_unchanged(
    row: dict, reason: FailureReason
) -> None:
    results, ledger = run_c(row)
    (r,) = results
    assert (r.status, r.failure_reason) == (Status.FAILED, reason)
    assert (r.usd_leg_done, r.jpy_leg_done) == (False, False)
    assert (r.arrival_time, r.start_time, r.end_time) == (5.0, 5.0, 65.0)
    assert r.principal_exposure_usd == 0.0
    assert snapshot(ledger) == untouched_c_state()


def test_model_c_success_moves_both_legs_at_arrival_plus_delay() -> None:
    results, ledger = run_c(tx(1, 5.0, "A", "B", 100, 15_000), delay_seconds=300)
    (r,) = results
    assert r.model == Model.ATOMIC
    assert (r.status, r.failure_reason) == (Status.SETTLED, None)
    assert (r.usd_leg_done, r.jpy_leg_done) == (True, True)
    assert (r.arrival_time, r.start_time, r.end_time) == (5.0, 5.0, 305.0)
    assert r.principal_exposure_usd == 0.0
    assert balances(ledger) == {
        "A USD": 900, "B USD": 1_100, "A JPY": 165_000, "B JPY": 135_000,
    }  # fmt: skip
    assert all_reserved(ledger) == [0, 0, 0, 0]
    assert ledger.peak_drawdown("A", USD) == to_minor(100)
    assert ledger.peak_drawdown("B", JPY) == to_minor(15_000)


def test_model_c_exact_balance_commit_succeeds() -> None:
    results, _ = run_c(tx(1, 0.0, "A", "B", 1_000, 150_000))
    assert results[0].status == Status.SETTLED


def test_model_c_checks_funds_at_commit_time_not_at_arrival() -> None:
    # Tx 2 needs A's USD 1,100 but A holds 1,000 when it arrives (t=10). Tx 1 pays A
    # 100 USD at its commit (t=60), before tx 2's commit (t=70), so tx 2 can settle.
    # Nothing is reserved for tx 2 at arrival.
    results, ledger = run_c(
        tx(1, 0.0, "B", "A", 100, 15_000),
        tx(2, 10.0, "A", "B", 1_100, 165_000),
    )
    assert [r.status for r in results] == [Status.SETTLED, Status.SETTLED]
    assert [r.end_time for r in results] == [60.0, 70.0]
    assert all_reserved(ledger) == [0, 0, 0, 0]


def test_model_c_does_not_reserve_funds_during_the_delay() -> None:
    # Both transactions need all of A's USD. The first commits at t=60 and the second
    # at t=70 finds nothing left. Same-time ties go to the lower transaction_id.
    results, ledger = run_c(
        tx(2, 10.0, "A", "B", 1_000, 100_000),
        tx(1, 0.0, "A", "B", 1_000, 100_000),
    )
    assert [r.status for r in results] == [Status.SETTLED, Status.FAILED]
    assert results[1].failure_reason == FailureReason.INSUFFICIENT_FUNDS
    assert balances(ledger)["A USD"] == 0


def test_can_commit_both_gives_the_answer_without_changing_anything() -> None:
    ledger = make_ledger()
    ledger.reserve("B", JPY, 100_000)
    before = snapshot(ledger)
    fits = Leg("A", "B", USD, 1_000), Leg("B", "A", JPY, 50_000)
    usd_short = Leg("A", "B", USD, 1_001), Leg("B", "A", JPY, 1)
    jpy_short = Leg("A", "B", USD, 1), Leg("B", "A", JPY, 50_001)  # reserved JPY counts
    assert ledger.can_commit_both(*fits)
    assert not ledger.can_commit_both(*usd_short)
    assert not ledger.can_commit_both(*jpy_short)
    assert snapshot(ledger) == before


def test_can_commit_both_checks_its_input_like_commit_both() -> None:
    ledger = make_ledger()
    with pytest.raises(ValueError):
        ledger.can_commit_both(Leg("A", "B", USD, 1), Leg("B", "A", USD, 1))
    with pytest.raises(ValueError):
        ledger.can_commit_both(Leg("A", "B", USD, 0), Leg("B", "A", JPY, 1))
    with pytest.raises(KeyError):
        ledger.can_commit_both(Leg("A", "B", USD, 1), Leg("B", "Z", JPY, 1))


# --- Boundary cases for Models B and C ---


@pytest.mark.parametrize("model", [Model.PREFUNDED, Model.ATOMIC])
def test_draw_equal_to_probability_is_not_a_hit(model: Model) -> None:
    results, _ = run_model(
        frame(tx(1, 0.0, "A", "B", 100, 15_000, failure_draw=0.05)),
        model,
        params_a(failure_probability=0.05),
    )
    assert results[0].status == Status.SETTLED


@pytest.mark.parametrize("model", [Model.PREFUNDED, Model.ATOMIC])
def test_probability_one_hits_every_draw_below_one(model: Model) -> None:
    results, ledger = run_model(
        frame(
            tx(1, 0.0, "A", "B", 100, 15_000, failure_draw=0.0),
            tx(2, 10.0, "A", "B", 100, 15_000, failure_draw=0.999999),
        ),
        model,
        params_a(failure_probability=1.0),
    )
    expected = Status.PARTIAL if model == Model.PREFUNDED else Status.FAILED
    assert [r.status for r in results] == [expected, expected]
    assert all(r.failure_reason == FailureReason.TECHNICAL_FAILURE for r in results)
    assert all_reserved(ledger) == [0, 0, 0, 0]


def test_model_b_delay_zero_orders_second_leg_before_a_same_time_arrival() -> None:
    # Tx 1 (arrives first by id) completes at t=0 and pays A 165,000 JPY in total; tx 2
    # arrives at the same time and needs all of it. With delay 0 the step of tx 1 is
    # scheduled at t=0 and must run before tx 2's arrival.
    results, ledger = run_b(
        tx(1, 0.0, "A", "B", 100, 15_000),
        tx(2, 0.0, "B", "A", 1_100, 165_000),
        delay_seconds=0,
    )
    assert [r.status for r in results] == [Status.SETTLED, Status.SETTLED]
    assert all(r.end_time == 0.0 for r in results)
    assert balances(ledger) == {
        "A USD": 2_000, "B USD": 0, "A JPY": 0, "B JPY": 300_000,
    }  # fmt: skip


def test_model_c_delay_zero_commits_at_arrival_time() -> None:
    results, ledger = run_c(
        tx(1, 0.0, "A", "B", 100, 15_000),
        tx(2, 0.0, "B", "A", 1_100, 165_000),
        delay_seconds=0,
    )
    assert [r.status for r in results] == [Status.SETTLED, Status.SETTLED]
    assert all(r.start_time == r.end_time == 0.0 for r in results)
    assert balances(ledger)["A USD"] == 2_000


@pytest.mark.parametrize("model", [Model.PREFUNDED, Model.ATOMIC])
def test_untouched_banks_keep_their_balances_with_three_banks(model: Model) -> None:
    rows = frame(
        tx(1, 0.0, "C", "A", 100, 15_000),
        tx(2, 10.0, "C", "A", 5_000, 750_000),  # fails: C holds only 1,000 USD
    )
    results, ledger = run_model(rows, model, params_a(n_banks=3))
    assert [r.status for r in results] == [Status.SETTLED, Status.FAILED]
    assert balances(ledger, ("A", "B", "C")) == {
        "A USD": 1_100, "B USD": 1_000, "C USD": 900,
        "A JPY": 135_000, "B JPY": 150_000, "C JPY": 165_000,
    }  # fmt: skip
    assert all_reserved(ledger, ("A", "B", "C")) == [0] * 6
    assert all_peaks(ledger, ("B",)) == [0, 0]


# --- Required engine tests (methodology sec. 7) ---
# These are correctness checks: they hold by design, so they are not evidence for any
# hypothesis. They run over several seeds, bank counts and arrival patterns.

ALL_MODELS = [Model.SEQUENTIAL, Model.PREFUNDED, Model.ATOMIC]
PROBABILITIES = [0.0, 0.01, 0.05]
# (n_banks, arrival) for the ample-liquidity tests: 2 and 5 banks, both arrival patterns.
AMPLE_CASES = [(2, "sequential"), (2, "burst"), (5, "sequential"), (5, "burst")]
AMPLE_USD = 1e12
AMPLE_JPY = 1.5e14


def case_inputs(
    seed: int, n_banks: int, arrival: str, probability: float, ample: bool, count: int = 200
) -> tuple[pd.DataFrame, SimulationParams]:
    """Transactions and parameters for a stressed (shortages) or ample-liquidity run."""
    data = generate_transactions(count=count, seed=seed, n_banks=n_banks, arrival=arrival)
    params = SimulationParams(
        seed=seed,
        initial_usd=AMPLE_USD if ample else 1_000_000,
        initial_jpy=AMPLE_JPY if ample else 150_000_000,
        failure_probability=probability,
        n_banks=n_banks,
    )
    return data, params


def exposure(results: list[SettlementResult]) -> float:
    return sum(r.principal_exposure_usd for r in results)


def has_shortage(results: list[SettlementResult]) -> bool:
    return any(r.failure_reason == FailureReason.INSUFFICIENT_FUNDS for r in results)


@pytest.mark.parametrize("seed", TEST_SEEDS)
@pytest.mark.parametrize(("n_banks", "arrival"), STRESS_CASES)
@pytest.mark.parametrize("ample", [True, False])
def test_model_c_has_no_partial_and_no_exposure(
    seed: int, n_banks: int, arrival: str, ample: bool
) -> None:
    for probability in PROBABILITIES:
        data, params = case_inputs(seed, n_banks, arrival, probability, ample)
        results, _ = run_model(data, Model.ATOMIC, params)
        assert len(results) == len(data)
        assert not any(r.status == Status.PARTIAL for r in results)
        assert exposure(results) == 0.0
        assert all(r.principal_exposure_usd == 0.0 for r in results)


@pytest.mark.parametrize("seed", TEST_SEEDS)
@pytest.mark.parametrize(("n_banks", "arrival"), STRESS_CASES)
def test_failed_model_c_transaction_leaves_every_balance_unchanged(
    seed: int, n_banks: int, arrival: str
) -> None:
    # A failed transaction changes nothing, so removing it from the input must not
    # change any other result, any final balance or any peak drawdown.
    data, params = case_inputs(seed, n_banks, arrival, 0.05, ample=False)
    results, ledger = run_model(data, Model.ATOMIC, params)
    failed_ids = {r.transaction_id for r in results if r.status == Status.FAILED}
    reasons = {r.failure_reason for r in results if r.status == Status.FAILED}
    # Not vacuous: both failure reasons occurred.
    assert reasons == {FailureReason.INSUFFICIENT_FUNDS, FailureReason.TECHNICAL_FAILURE}
    without = data[~data["transaction_id"].isin(failed_ids)]
    results_without, ledger_without = run_model(without, Model.ATOMIC, params)
    assert results_without == [r for r in results if r.transaction_id not in failed_ids]
    for bank in bank_names(n_banks):
        for currency in Currency:
            assert ledger.balance(bank, currency) == ledger_without.balance(bank, currency)
            assert ledger.peak_drawdown(bank, currency) == ledger_without.peak_drawdown(
                bank, currency
            )
            assert ledger.reserved(bank, currency) == 0


@pytest.mark.parametrize("seed", TEST_SEEDS)
@pytest.mark.parametrize(("n_banks", "arrival"), AMPLE_CASES)
def test_a_and_b_have_same_exposure_without_insufficient_funds(
    seed: int, n_banks: int, arrival: str
) -> None:
    for probability in PROBABILITIES:
        data, params = case_inputs(seed, n_banks, arrival, probability, ample=True)
        results_a, _ = run_model(data, Model.SEQUENTIAL, params)
        results_b, _ = run_model(data, Model.PREFUNDED, params)
        assert not has_shortage(results_a)
        assert not has_shortage(results_b)
        assert exposure(results_a) == exposure(results_b)
        assert [r.status for r in results_a] == [r.status for r in results_b]


@pytest.mark.parametrize("model", [Model.SEQUENTIAL, Model.PREFUNDED])
@pytest.mark.parametrize("seed", TEST_SEEDS)
@pytest.mark.parametrize(("n_banks", "arrival"), AMPLE_CASES)
def test_exposure_in_a_and_b_does_not_fall_as_failure_probability_rises(
    model: Model, seed: int, n_banks: int, arrival: str
) -> None:
    # Ample liquidity only: under stress a hit changes later balances.
    totals = []
    for probability in PROBABILITIES:
        data, params = case_inputs(seed, n_banks, arrival, probability, True, count=500)
        results, _ = run_model(data, model, params)
        assert not has_shortage(results)
        totals.append(exposure(results))
    assert totals[0] == 0.0
    assert totals[0] <= totals[1] <= totals[2]
    assert totals[2] > totals[0]  # with 500 transactions, 5% is above 0%


@pytest.mark.parametrize("model", ALL_MODELS)
@pytest.mark.parametrize("seed", TEST_SEEDS)
@pytest.mark.parametrize(("n_banks", "arrival"), STRESS_CASES)
def test_status_matches_legs_done_in_every_run(
    model: Model, seed: int, n_banks: int, arrival: str
) -> None:
    for probability in PROBABILITIES:
        for ample in (True, False):
            data, params = case_inputs(seed, n_banks, arrival, probability, ample)
            results, _ = run_model(data, model, params)
            assert [r.transaction_id for r in results] == sorted(data["transaction_id"])
            for r in results:
                assert r.model == model
                legs = r.usd_leg_done + r.jpy_leg_done
                assert (r.status == Status.SETTLED) == (legs == 2)
                assert (r.status == Status.PARTIAL) == (legs == 1)
                assert (r.status == Status.FAILED) == (legs == 0)
                assert (r.failure_reason is None) == (r.status == Status.SETTLED)


@pytest.mark.skip(reason="Rates are metrics; they are implemented on Day 9 (src/metrics.py)")
def test_success_partial_and_failure_rates_sum_to_one() -> None:
    pass


@pytest.mark.parametrize("model", ALL_MODELS)
@pytest.mark.parametrize("seed", TEST_SEEDS)
@pytest.mark.parametrize(("n_banks", "arrival"), STRESS_CASES)
def test_total_usd_and_jpy_are_unchanged_by_any_run(
    model: Model, seed: int, n_banks: int, arrival: str
) -> None:
    for ample in (True, False):
        data, params = case_inputs(seed, n_banks, arrival, 0.05, ample)
        results, ledger = run_model(data, model, params)
        if not ample:
            assert has_shortage(results)  # Not vacuous: the stressed case has shortages.
        assert ledger.total(USD) == n_banks * to_minor(params.initial_usd)
        assert ledger.total(JPY) == n_banks * to_minor(params.initial_jpy)


@pytest.mark.parametrize("model", ALL_MODELS)
@pytest.mark.parametrize("seed", TEST_SEEDS)
@pytest.mark.parametrize(("n_banks", "arrival"), STRESS_CASES)
def test_nothing_is_left_reserved_and_balances_match_the_result_flags(
    model: Model, seed: int, n_banks: int, arrival: str
) -> None:
    data, params = case_inputs(seed, n_banks, arrival, 0.05, ample=False)
    results, ledger = run_model(data, model, params)
    expected = expected_balances(data, results, params)
    for (bank, currency), amount in expected.items():
        assert ledger.reserved(bank, currency) == 0
        assert ledger.balance(bank, currency) == amount


@pytest.mark.parametrize("model", ALL_MODELS)
def test_models_are_deterministic_and_do_not_change_the_input(model: Model) -> None:
    data, params = case_inputs(201, 3, "burst", 0.05, ample=False)
    before = data.copy()
    first, _ = run_model(data, model, params)
    second, _ = run_model(data, model, params)
    assert first == second
    pd.testing.assert_frame_equal(data, before)

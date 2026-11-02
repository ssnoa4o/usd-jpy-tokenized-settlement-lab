"""Tests for the ledger and shared types, plus placeholders for the required engine tests."""

import numpy as np
import pytest

from src.simulator import (
    Currency,
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

USD = Currency.USD
JPY = Currency.JPY
ENGINE_PENDING = "Required test (methodology sec. 7): implement on Day 6-8"


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


def test_run_model_is_not_implemented_yet() -> None:
    with pytest.raises(NotImplementedError):
        run_model(None, Model.ATOMIC, SimulationParams(seed=1))


# --- Required engine tests (methodology sec. 7) ---


@pytest.mark.skip(reason=ENGINE_PENDING)
def test_model_c_has_no_partial_and_no_exposure() -> None:
    pass


@pytest.mark.skip(reason=ENGINE_PENDING)
def test_failed_model_c_transaction_leaves_every_balance_unchanged() -> None:
    pass


@pytest.mark.skip(reason=ENGINE_PENDING)
def test_a_and_b_have_same_exposure_without_insufficient_funds() -> None:
    pass


@pytest.mark.skip(reason=ENGINE_PENDING)
def test_exposure_in_a_and_b_does_not_fall_as_failure_probability_rises() -> None:
    # Ample liquidity only. Also assert: with 500 transactions, higher at 5% than at 0%.
    pass


@pytest.mark.skip(reason=ENGINE_PENDING)
def test_status_matches_legs_done_in_every_run() -> None:
    pass


@pytest.mark.skip(reason=ENGINE_PENDING)
def test_success_partial_and_failure_rates_sum_to_one() -> None:
    pass


@pytest.mark.skip(reason=ENGINE_PENDING)
def test_total_usd_and_jpy_are_unchanged_by_any_run() -> None:
    pass

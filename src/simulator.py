"""Shared types and the bank ledger for the three settlement models.

Definitions follow research/methodology.md. The settlement logic is added on Day 6-7.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import NamedTuple

import pandas as pd

MINOR_UNITS_PER_UNIT = 100


class Status(StrEnum):
    SETTLED = "settled"
    PARTIAL = "partial"
    FAILED = "failed"


class FailureReason(StrEnum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    TECHNICAL_FAILURE = "technical_failure"
    TIMEOUT = "timeout"  # Reserved: not triggered in the main experiments.


class Model(StrEnum):
    SEQUENTIAL = "sequential"
    PREFUNDED = "prefunded"
    ATOMIC = "atomic"


class Currency(StrEnum):
    USD = "USD"
    JPY = "JPY"


def to_minor(amount: float) -> int:
    """Convert a 2-decimal amount to integer hundredths, avoiding float noise."""
    return round(amount * MINOR_UNITS_PER_UNIT)


@dataclass(frozen=True)
class SimulationParams:
    """Inputs for one run. All values are synthetic design values, not real-world ones."""

    seed: int
    initial_usd: float = 100_000_000
    initial_jpy: float = 15_000_000_000
    delay_seconds: float = 60
    failure_probability: float = 0.01
    cutoff_seconds: float = 3_600

    def __post_init__(self) -> None:
        values = (
            self.initial_usd,
            self.initial_jpy,
            self.delay_seconds,
            self.failure_probability,
            self.cutoff_seconds,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("parameters must be finite numbers")
        if _is_not_int(self.seed):
            raise ValueError("seed must be an integer")
        if not 0 <= self.failure_probability <= 1:
            raise ValueError("failure_probability must be between 0 and 1")
        if self.initial_usd < 0 or self.initial_jpy < 0:
            raise ValueError("initial balances must be >= 0")
        if self.delay_seconds < 0 or self.cutoff_seconds < 0:
            raise ValueError("times must be >= 0")


@dataclass(frozen=True)
class SettlementResult:
    """Outcome of one transaction in one model run."""

    transaction_id: int
    model: Model
    status: Status
    failure_reason: FailureReason | None
    usd_leg_done: bool
    jpy_leg_done: bool
    arrival_time: float
    start_time: float
    end_time: float
    principal_exposure_usd: float

    def __post_init__(self) -> None:
        # Strict bool: numpy's True_ + True_ is True, not 2, which would hide a bad status.
        if type(self.usd_leg_done) is not bool or type(self.jpy_leg_done) is not bool:
            raise ValueError("usd_leg_done and jpy_leg_done must be plain bool")
        legs_done = self.usd_leg_done + self.jpy_leg_done
        expected = {2: Status.SETTLED, 1: Status.PARTIAL, 0: Status.FAILED}[legs_done]
        if self.status != expected:
            raise ValueError(f"{legs_done} legs done requires status {expected}")
        if (self.status == Status.SETTLED) != (self.failure_reason is None):
            raise ValueError("only a settled transaction has no failure_reason")
        if self.model == Model.ATOMIC and self.status == Status.PARTIAL:
            raise ValueError("the atomic model cannot leave a partial transaction")
        if self.principal_exposure_usd < 0 or (
            self.status != Status.PARTIAL and self.principal_exposure_usd != 0
        ):
            raise ValueError("only a partial transaction has principal exposure")
        if not self.arrival_time <= self.start_time <= self.end_time:
            raise ValueError("times must satisfy arrival <= start <= end")


class Leg(NamedTuple):
    """One currency movement. The amount is in integer hundredths."""

    payer: str
    receiver: str
    currency: Currency
    amount: int


class Ledger:
    """Balances, reservations and peak drawdown per bank and currency.

    All amounts are integer hundredths of a currency unit (see to_minor).
    Available balance = balance - reserved funds.
    """

    def __init__(self, banks: list[str], initial: dict[Currency, int]) -> None:
        if len(set(banks)) != len(banks) or len(banks) < 2:
            raise ValueError("banks must contain at least 2 different names")
        if set(initial) != set(Currency) or any(
            _is_not_int(value) or value < 0 for value in initial.values()
        ):
            raise ValueError("initial must give an integer >= 0 for USD and JPY")
        accounts = [(bank, currency) for bank in banks for currency in Currency]
        self._initial = {key: initial[key[1]] for key in accounts}
        self._balance = dict(self._initial)
        self._reserved = dict.fromkeys(accounts, 0)
        self._peak_drawdown = dict.fromkeys(accounts, 0)

    def balance(self, bank: str, currency: Currency) -> int:
        return self._balance[(bank, currency)]

    def reserved(self, bank: str, currency: Currency) -> int:
        return self._reserved[(bank, currency)]

    def available(self, bank: str, currency: Currency) -> int:
        return self.balance(bank, currency) - self.reserved(bank, currency)

    def peak_drawdown(self, bank: str, currency: Currency) -> int:
        """Largest (initial balance - available balance) so far; input to the proxy."""
        return self._peak_drawdown[(bank, currency)]

    def total(self, currency: Currency) -> int:
        return sum(
            amount for (_, cur), amount in self._balance.items() if cur == currency
        )

    def reserve(self, bank: str, currency: Currency, amount: int) -> bool:
        """Set funds aside. Returns False and changes nothing if funds are short."""
        _check_amount(amount)
        if self.available(bank, currency) < amount:
            return False
        self._reserved[(bank, currency)] += amount
        self._update_peak(bank, currency)
        return True

    def release(self, bank: str, currency: Currency, amount: int) -> None:
        """Return reserved funds to the available balance."""
        _check_amount(amount)
        if self.reserved(bank, currency) < amount:
            raise ValueError("cannot release more than is reserved")
        self._reserved[(bank, currency)] -= amount

    def transfer(self, leg: Leg, from_reserved: bool = False) -> bool:
        """Move one leg. Returns False and changes nothing if funds are short."""
        _check_leg(leg, self._balance)
        if from_reserved:
            if self.reserved(leg.payer, leg.currency) < leg.amount:
                raise ValueError("cannot pay more than is reserved")
            self._reserved[(leg.payer, leg.currency)] -= leg.amount
        elif self.available(leg.payer, leg.currency) < leg.amount:
            return False
        self._apply(leg)
        return True

    def commit_both(self, first: Leg, second: Leg) -> bool:
        """Validate both legs, then apply both. If either is short, change nothing."""
        _check_leg(first, self._balance)
        _check_leg(second, self._balance)
        if first.currency == second.currency:
            raise ValueError("the two legs must use different currencies")
        if any(self.available(leg.payer, leg.currency) < leg.amount for leg in (first, second)):
            return False
        self._apply(first)
        self._apply(second)
        return True

    def _apply(self, leg: Leg) -> None:
        self._balance[(leg.payer, leg.currency)] -= leg.amount
        self._balance[(leg.receiver, leg.currency)] += leg.amount
        self._update_peak(leg.payer, leg.currency)

    def _update_peak(self, bank: str, currency: Currency) -> None:
        key = (bank, currency)
        drawdown = self._initial[key] - self.available(bank, currency)
        self._peak_drawdown[key] = max(self._peak_drawdown[key], drawdown)


def _is_not_int(value: object) -> bool:
    return isinstance(value, bool) or not isinstance(value, int)


def _check_amount(amount: int) -> None:
    if _is_not_int(amount) or amount <= 0:
        raise ValueError("amount must be a positive integer (hundredths)")


def _check_leg(leg: Leg, balances: dict[tuple[str, Currency], int]) -> None:
    _check_amount(leg.amount)
    if leg.payer == leg.receiver:
        raise ValueError("payer and receiver must be different banks")
    for bank in (leg.payer, leg.receiver):
        if (bank, leg.currency) not in balances:
            raise KeyError(f"unknown account: {bank} {leg.currency}")


def run_model(
    transactions: pd.DataFrame, model: Model, params: SimulationParams
) -> tuple[list[SettlementResult], Ledger]:
    """Run one settlement model over the transactions. Implemented on Day 6-7."""
    raise NotImplementedError("settlement logic is implemented on Day 6-7")

"""Tests for the synthetic transaction generator."""

import json

import numpy as np
import pandas as pd
import pytest

from src.simulator import Currency, Ledger, Leg, to_minor
from src.transactions import (
    CSV_PATH,
    META_PATH,
    bank_names,
    generate_transactions,
)

COLUMNS = [
    "transaction_id",
    "arrival_time",
    "usd_payer",
    "jpy_payer",
    "usd_amount",
    "jpy_amount",
    "fx_rate",
    "failure_draw",
]


def test_columns_and_length() -> None:
    df = generate_transactions(count=20)
    assert list(df.columns) == COLUMNS
    assert len(df) == 20


def test_same_seed_same_data_different_seed_differs() -> None:
    a = generate_transactions(seed=1)
    b = generate_transactions(seed=1)
    c = generate_transactions(seed=2)
    pd.testing.assert_frame_equal(a, b, check_exact=True)
    assert not a.equals(c)


def test_jpy_matches_usd_times_rate() -> None:
    df = generate_transactions(fx_rate=151.37)
    assert np.isclose(df["jpy_amount"], df["usd_amount"] * df["fx_rate"], atol=0.01).all()


def test_no_nan_and_ids_and_no_direction_column() -> None:
    df = generate_transactions(count=50)
    assert not df.isna().any().any()
    assert "direction" not in df.columns
    assert list(df["transaction_id"]) == list(range(1, 51))


@pytest.mark.parametrize("count", [0, -1, True, 2.5])
def test_bad_count(count) -> None:
    with pytest.raises(ValueError):
        generate_transactions(count=count)


@pytest.mark.parametrize("fx_rate", [0, -1, float("inf"), float("nan")])
def test_bad_fx_rate(fx_rate) -> None:
    with pytest.raises(ValueError):
        generate_transactions(fx_rate=fx_rate)


@pytest.mark.parametrize("seed", [None, -1, True])
def test_bad_seed(seed) -> None:
    with pytest.raises(ValueError):
        generate_transactions(seed=seed)


def test_numpy_int_count_works() -> None:
    assert len(generate_transactions(count=np.int64(7))) == 7


def test_changing_n_banks_or_arrival_keeps_amounts_and_failure_draw() -> None:
    base = generate_transactions(count=60, seed=7)
    other = generate_transactions(count=60, seed=7, n_banks=10, arrival="burst")
    for column in ["usd_amount", "jpy_amount", "failure_draw"]:
        pd.testing.assert_series_equal(base[column], other[column], check_exact=True)


def test_more_rows_keep_earlier_rows_unchanged() -> None:
    small = generate_transactions(count=30, seed=5, n_banks=5)
    large = generate_transactions(count=80, seed=5, n_banks=5)
    pd.testing.assert_frame_equal(small, large.head(30), check_exact=True)


@pytest.mark.parametrize("n_banks", [2, 3, 10])
def test_bank_pairs_differ_and_use_valid_names(n_banks: int) -> None:
    df = generate_transactions(count=500, n_banks=n_banks)
    names = set(bank_names(n_banks))
    assert (df["usd_payer"] != df["jpy_payer"]).all()
    assert set(df["usd_payer"]) <= names
    assert set(df["jpy_payer"]) <= names


def test_bank_names_and_ten_banks_all_appear() -> None:
    assert bank_names(2) == ["A", "B"]
    assert bank_names(10) == list("ABCDEFGHIJ")
    df = generate_transactions(count=1000, n_banks=10)
    assert set(df["usd_payer"]) == set(bank_names(10))
    assert set(df["jpy_payer"]) == set(bank_names(10))


@pytest.mark.parametrize("n_banks", [3, 10])
def test_bank_pairs_are_roughly_uniform(n_banks: int) -> None:
    # n banks -> n * (n - 1) ordered pairs; the seed is fixed, so this is not flaky.
    pairs = n_banks * (n_banks - 1)
    expected = 1000
    df = generate_transactions(count=expected * pairs, seed=42, n_banks=n_banks)
    counts = df.groupby(["usd_payer", "jpy_payer"]).size()
    assert len(counts) == pairs
    assert counts.min() >= expected * 0.85
    assert counts.max() <= expected * 1.15


def test_sequential_arrival_every_10_seconds() -> None:
    df = generate_transactions(count=25, arrival="sequential")
    assert df["arrival_time"].dtype == float
    assert list(df["arrival_time"]) == [10.0 * i for i in range(25)]


@pytest.mark.parametrize("count", [30, 25, 7])
def test_burst_arrival_10_at_a_time_every_100_seconds(count: int) -> None:
    df = generate_transactions(count=count, arrival="burst")
    assert df["arrival_time"].dtype == float
    assert list(df["arrival_time"]) == [100.0 * (i // 10) for i in range(count)]


def test_failure_draw_in_unit_interval() -> None:
    draws = generate_transactions(count=1000)["failure_draw"]
    assert ((draws >= 0) & (draws < 1)).all()


def test_failure_draw_looks_uniform_and_changes_with_seed() -> None:
    draws = generate_transactions(count=10_000, seed=42)["failure_draw"]
    other = generate_transactions(count=10_000, seed=43)["failure_draw"]
    assert draws.nunique() > 9_000
    assert abs(draws.mean() - 0.5) < 0.02
    assert (draws < 0.05).mean() == pytest.approx(0.05, abs=0.01)
    assert not draws.equals(other)


def test_random_streams_are_not_correlated() -> None:
    # If two streams shared a seed, failures would follow transaction size.
    df = generate_transactions(count=10_000, seed=42, n_banks=10)
    usd_index = df["usd_payer"].map(bank_names(10).index)
    assert abs(df["usd_amount"].corr(df["failure_draw"])) < 0.05
    assert abs(df["usd_amount"].corr(usd_index)) < 0.05
    assert abs(df["failure_draw"].corr(usd_index)) < 0.05


def test_to_minor_gives_python_int_that_ledger_accepts() -> None:
    df = generate_transactions(count=5, n_banks=3)
    row = df.iloc[0]
    amount = to_minor(row["usd_amount"])
    assert type(amount) is int
    ledger = Ledger(bank_names(3), {Currency.USD: amount, Currency.JPY: 0})
    leg = Leg(row["usd_payer"], row["jpy_payer"], Currency.USD, amount)
    assert ledger.transfer(leg)


def test_jpy_is_exactly_150_times_usd_in_minor_units() -> None:
    df = generate_transactions(count=500, fx_rate=150.0)
    for usd, jpy in zip(df["usd_amount"], df["jpy_amount"]):
        assert to_minor(jpy) == 150 * to_minor(usd)


def test_jpy_is_rounded_to_nearest_minor_unit_at_other_rate() -> None:
    df = generate_transactions(count=500, fx_rate=151.37)
    for usd, jpy in zip(df["usd_amount"], df["jpy_amount"]):
        assert abs(to_minor(jpy) - to_minor(usd) * 151.37) <= 0.5 + 1e-6


@pytest.mark.parametrize("n_banks", [1, 11, 0, True, 2.5, None])
def test_bad_n_banks(n_banks) -> None:
    with pytest.raises(ValueError):
        generate_transactions(n_banks=n_banks)
    with pytest.raises(ValueError):
        bank_names(n_banks)


def test_numpy_int_n_banks_works() -> None:
    assert len(bank_names(np.int64(4))) == 4
    assert len(generate_transactions(count=5, n_banks=np.int64(4))) == 5


@pytest.mark.parametrize("arrival", ["random", "", None, 1, True])
def test_bad_arrival(arrival) -> None:
    with pytest.raises(ValueError):
        generate_transactions(arrival=arrival)


def test_saved_csv_matches_generator() -> None:
    # Detects a stale data/sample_transactions.csv after the generator changes.
    # The pinned pandas 3.1.0 reads floats exactly by default (float_precision is deprecated).
    saved = pd.read_csv(CSV_PATH)
    pd.testing.assert_frame_equal(
        saved, generate_transactions(100, 150.0, 42), check_exact=True
    )
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    assert (meta["count"], meta["fx_rate"], meta["seed"]) == (100, 150.0, 42)
    assert (meta["n_banks"], meta["arrival"]) == (2, "sequential")

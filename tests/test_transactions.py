"""Tests for the synthetic transaction generator."""

import numpy as np
import pandas as pd
import pytest

from src.transactions import generate_transactions

COLUMNS = ["transaction_id", "usd_amount", "jpy_amount", "direction", "fx_rate"]


def test_columns_and_length() -> None:
    df = generate_transactions(count=20)
    assert list(df.columns) == COLUMNS
    assert len(df) == 20


def test_same_seed_same_data_different_seed_differs() -> None:
    a = generate_transactions(seed=1)
    b = generate_transactions(seed=1)
    c = generate_transactions(seed=2)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(c)


def test_jpy_matches_usd_times_rate() -> None:
    df = generate_transactions(fx_rate=151.37)
    assert np.isclose(df["jpy_amount"], df["usd_amount"] * df["fx_rate"], atol=0.01).all()


def test_no_nan_and_valid_directions_and_ids() -> None:
    df = generate_transactions(count=50)
    assert not df.isna().any().any()
    assert set(df["direction"]) <= {"A_pays_USD", "B_pays_USD"}
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

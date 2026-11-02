"""Tests for metric helpers."""

import math

from src.metrics import safe_ratio


def test_safe_ratio_normal_case() -> None:
    assert safe_ratio(1, 4) == 0.25
    assert safe_ratio(0, 4) == 0


def test_safe_ratio_zero_denominator_is_nan_not_zero() -> None:
    assert math.isnan(safe_ratio(0, 0))
    assert math.isnan(safe_ratio(3, 0))

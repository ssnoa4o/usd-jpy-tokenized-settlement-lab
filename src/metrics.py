"""Metric calculations. Definitions are in research/methodology.md, sec. 5.

The metrics themselves are added on Day 9-10.
"""


def safe_ratio(numerator: float, denominator: float) -> float:
    """Return numerator / denominator, or NaN if the denominator is 0.

    NaN, not 0, so that "no data" is never shown as "0% success".
    """
    if denominator == 0:
        return float("nan")
    return numerator / denominator

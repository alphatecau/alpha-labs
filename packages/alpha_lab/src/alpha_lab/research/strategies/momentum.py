"""Predeclared EMA trend baseline. Indicator only uses observed closes."""

from decimal import Decimal


def ema_series(closes: list[Decimal], length: int) -> list[Decimal]:
    if length <= 1:
        raise ValueError("EMA length must exceed one")
    alpha = Decimal(2) / (length + 1)
    series = []
    for close in closes:
        series.append(close if not series else alpha * close + (1 - alpha) * series[-1])
    return series


def ema_signal(closes: list[Decimal], fast: int = 12, slow: int = 48) -> list[bool]:
    if fast >= slow or fast <= 1:
        raise ValueError("Need 1 < fast < slow")
    a, b = ema_series(closes, fast), ema_series(closes, slow)
    return [(i >= slow and a[i] > b[i]) for i in range(len(closes))]

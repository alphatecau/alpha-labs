"""Fail-closed numeric boundary policy for research accounting inputs.

This is a proposed canonical policy, not an exchange tick-size or tax policy.
Money rounding must happen only at explicitly defined settlement boundaries.
"""
from decimal import Decimal, ROUND_HALF_EVEN
from alpha_lab.research.phase1_accounting import D

MAX_SIGNIFICANT_DIGITS = 28
MAX_ABSOLUTE_EXPONENT = 18


def bounded_decimal(value, *, allow_zero=True, allow_negative=False):
    if isinstance(value, bool):
        raise ValueError("Boolean is not an accounting number")
    amount = D(value)
    if len(amount.as_tuple().digits) > MAX_SIGNIFICANT_DIGITS:
        raise ValueError("Excessive decimal precision")
    if abs(amount.adjusted()) > MAX_ABSOLUTE_EXPONENT and amount != 0:
        raise ValueError("Accounting magnitude out of bounds")
    if amount < 0 and not allow_negative:
        raise ValueError("Negative accounting value")
    if amount == 0 and not allow_zero:
        raise ValueError("Zero accounting value")
    return amount


def quantise_aud(amount):
    """Illustrative AUD cent settlement rounding, ROUND_HALF_EVEN."""
    value = bounded_decimal(amount, allow_negative=True)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)

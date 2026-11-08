"""Conservative split-only ETF price-adjustment reconciliation.

Requires independently verified daily raw/adjusted closes and dated split
factors. Cash-dividend days are deliberately unsupported: vendor-specific
total-return adjustments cannot be inferred from raw closes alone.
"""
from decimal import Decimal, InvalidOperation


def reconcile_split_adjusted_close(*, raw_closes, adjusted_closes, split_factors,
                                   cash_dividends, tolerance="0.000001"):
    dates = sorted(raw_closes)
    if not dates or set(dates) != set(adjusted_closes) or set(dates) != set(split_factors) or set(dates) != set(cash_dividends):
        raise ValueError("Complete identical date coverage required")
    try:
        tol = Decimal(str(tolerance))
        if not tol.is_finite() or tol < 0:
            raise ValueError("Invalid tolerance")
        raw = {d: Decimal(str(raw_closes[d])) for d in dates}
        adjusted = {d: Decimal(str(adjusted_closes[d])) for d in dates}
        factors = {d: Decimal(str(split_factors[d])) for d in dates}
        dividends = {d: Decimal(str(cash_dividends[d])) for d in dates}
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid numeric evidence") from exc
    for d in dates:
        if any(not v.is_finite() for v in (raw[d], adjusted[d], factors[d], dividends[d])):
            raise ValueError("Nonfinite evidence")
        if raw[d] <= 0 or adjusted[d] <= 0 or factors[d] <= 0 or dividends[d] < 0:
            raise ValueError("Invalid price or corporate-action value")
        if dividends[d] != 0:
            raise ValueError("Dividend adjustment requires documented vendor methodology")
    # Ex-date split factor applies to prices strictly before the ex-date.
    cumulative = Decimal("1")
    discrepancies = []
    for d in reversed(dates):
        expected = raw[d] / cumulative
        if abs(expected - adjusted[d]) > tol:
            discrepancies.append(str(d))
        cumulative *= factors[d]
    if discrepancies:
        raise ValueError("Split-adjusted price mismatch: " + ",".join(reversed(discrepancies)))
    return {"status": "SPLIT_ARITHMETIC_CONSISTENT_NOT_AUTHENTICATED",
            "observations": len(dates), "publisher_identity_verified": False,
            "eligible_for_strategy_promotion": False}

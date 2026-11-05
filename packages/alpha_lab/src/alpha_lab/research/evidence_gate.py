"""Truthful, fail-closed summaries of offline hypothesis-screen results.

This module cannot certify alpha. The holdout is not sealed, prices unverified,
and fixed-cost historical fills are not executable quotes.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

EXPECTED_STATUS = "HYPOTHESIS_SCREEN_ONLY_NOT_VALIDATED_ALPHA"


def _num(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"Invalid {label}")
    try:
        v = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}") from exc
    if not v.is_finite():
        raise ValueError(f"Invalid {label}")
    return v


def summarise_offline_research(report: dict) -> dict:
    """Extract after-modelled-cost evidence; do not promote it to verified profit."""
    if not isinstance(report, dict) or report.get("status") != EXPECTED_STATUS:
        raise ValueError("Only the offline hypothesis-screen contract is supported")
    ds = report.get("dataset")
    if not isinstance(ds, dict) or not isinstance(ds.get("provenance"), str) or not ds["provenance"].strip():
        raise ValueError("Missing dataset provenance")
    if not isinstance(ds.get("sha256"), str) or len(ds["sha256"]) != 64 or any(c not in '0123456789abcdef' for c in ds["sha256"]):
        raise ValueError("Invalid dataset checksum")
    if ds.get("quote_currency") not in {"USD", "USDC", "USDT", "AUD", "EUR"}:
        raise ValueError("Unknown quote currency")
    if not isinstance(report.get("configuration_sha256"), str) or len(report["configuration_sha256"]) != 64 or any(c not in '0123456789abcdef' for c in report["configuration_sha256"]):
        raise ValueError("Invalid configuration checksum")
    periods = report.get("periods")
    if not isinstance(periods, dict) or set(periods) != {"training", "holdout"}:
        raise ValueError("Expected training and holdout periods")
    results = {}
    for name, entry in periods.items():
        if not isinstance(entry, dict):
            raise ValueError("Invalid period")
        values = {}
        for key in ("strategy", "equal_allocation_buy_hold", "double_cost_strategy"):
            item = entry.get(key)
            if not isinstance(item, dict):
                raise ValueError("Missing evaluation comparator")
            values[key] = _num(item.get("return_pct"), key)
        strategy = values["strategy"]
        passive = values["equal_allocation_buy_hold"]
        stress = values["double_cost_strategy"]
        results[name] = {
            "strategy_net_modelled_return_pct": float(strategy),
            "passive_net_modelled_return_pct": float(passive),
            "double_cost_modelled_return_pct": float(stress),
            "excess_vs_passive_pct_points": float(strategy - passive),
            "outperforms_passive": strategy > passive,
            "survives_double_costs_with_positive_return": stress > 0,
        }
    return {
        "status": "EVIDENCE_INSUFFICIENT_RESEARCH_ONLY",
        "trading_enabled": False,
        "dataset_sha256": ds["sha256"],
        "configuration_sha256": report["configuration_sha256"],
        "quote_currency": ds["quote_currency"],
        "data_provenance_declared": ds["provenance"],
        "price_authenticity_verified": False,
        "holdout_independently_sealed": False,
        "execution_costs_observed": False,
        "operating_expenses_included": False,
        "statistical_significance_verified": False,
        "periods": results,
        "note": "Descriptive returns after assumed fees/slippage only. No actual profit, realised fill, approved trade or independently validated alpha.",
    }

"""Deterministic, fail-closed advisory gate. Never grants execution authority.

The research engine may describe a trend but cannot promote it to a trade.
No network, broker, paper journal, or account access.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Any

VALID_TRENDS = frozenset({"UPTREND_OBSERVED", "DOWNTREND_OBSERVED", "MIXED"})
VALID_PRODUCTS = frozenset({"BTC-USD", "ETH-USD", "SOL-USD"})
REQUIRED = frozenset({"status", "product_id", "granularity", "source_sha256",
                      "candle_count", "trend_observation", "decision",
                      "risk_override", "paper_execution_authorised",
                      "live_execution_authorised"})


def advisory_decision(report: Mapping[str, Any] | None, *, now: datetime | None = None) -> dict:
    """Convert descriptive research into a non-executable, auditable decision.

    Untrusted or incomplete reports always produce UNVERIFIED / HALT.
    Valid descriptive observations produce NO_TRADE / HALT, irrespective of trend.
    """
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    result = {
        "schema_version": 1,
        "evaluated_at_utc": timestamp.astimezone(timezone.utc).isoformat(),
        "decision": "UNVERIFIED",
        "risk_override": "HALT",
        "paper_execution_authorised": False,
        "live_execution_authorised": False,
        "reason": "INVALID_OR_INCOMPLETE_RESEARCH",
        "product_id": None,
        "source_sha256": None,
        "trend_observation": None,
    }
    if not isinstance(report, Mapping) or not REQUIRED.issubset(report):
        return result
    if (report.get("status") != "RESEARCH_ONLY_NOT_VALIDATED_ALPHA"
            or report.get("product_id") not in VALID_PRODUCTS
            or report.get("trend_observation") not in VALID_TRENDS
            or report.get("decision") != "FLAT"
            or report.get("risk_override") != "HALT"
            or report.get("paper_execution_authorised") is not False
            or report.get("live_execution_authorised") is not False
            or type(report.get("candle_count")) is not int
            or report["candle_count"] < 60
            or type(report.get("granularity")) is not int
            or report["granularity"] <= 0
            or not isinstance(report.get("source_sha256"), str)
            or len(report["source_sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in report["source_sha256"])):
        return result
    result.update(
        decision="NO_TRADE",
        reason="DESCRIPTIVE_TREND_HAS_NO_VALIDATED_AFTER_COST_EDGE",
        product_id=report["product_id"],
        source_sha256=report["source_sha256"],
        trend_observation=report["trend_observation"],
    )
    return result

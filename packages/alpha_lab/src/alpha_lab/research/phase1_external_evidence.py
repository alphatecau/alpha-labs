"""Fail-closed cross-source ETF session and corporate-action evidence checks.

This module checks consistency of supplied independent evidence files. It cannot
authenticate their publisher, provenance or completeness by itself.
"""
from __future__ import annotations

import csv
import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

def _read_evidence(path, expected_sha256, required):
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ValueError("Missing independently pinned evidence hash")
    payload = Path(path).read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256.lower():
        raise ValueError("Evidence hash mismatch")
    try:
        reader = csv.DictReader(payload.decode("utf-8-sig").splitlines(), strict=True)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("Invalid evidence CSV header")
        if not required.issubset(reader.fieldnames):
            raise ValueError("Missing evidence columns")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("Malformed evidence CSV") from exc
    if not rows or any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("Incomplete evidence CSV")
    return rows

def verify_external_etf_evidence(*, symbol, observed_sessions, calendar_csv,
                                 calendar_sha256, actions_csv, actions_sha256,
                                 calendar_publisher, actions_publisher,
                                 calendar_retrieved_at, actions_retrieved_at,
                                 as_of):
    """Require independently sourced session and action evidence with pinned hashes.

    Action rows use date,symbol,split_factor,cash_dividend. Split factor 1 and
    dividend 0 mean no action. Every observed session requires an action row,
    preventing silent omission. This does not certify adjusted-price accuracy.
    """
    if not calendar_publisher or not actions_publisher or calendar_publisher == actions_publisher:
        raise ValueError("Distinct identified evidence publishers required")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise ValueError("Timezone-aware as_of required")
    as_of = as_of.astimezone(timezone.utc)
    for stamp in (calendar_retrieved_at, actions_retrieved_at):
        if not isinstance(stamp, datetime) or stamp.tzinfo is None:
            raise ValueError("Timezone-aware evidence retrieval required")
        if stamp.astimezone(timezone.utc) > as_of:
            raise ValueError("Future evidence is not point-in-time available")
    sessions = set(observed_sessions)
    if not sessions or any(not isinstance(d, date) or isinstance(d, datetime) for d in sessions):
        raise ValueError("Invalid observed session dates")
    cal = _read_evidence(calendar_csv, calendar_sha256, {"date", "symbol", "is_session"})
    actions = _read_evidence(actions_csv, actions_sha256,
                             {"date", "symbol", "split_factor", "cash_dividend"})
    expected = set()
    calendar_seen = set()
    for row in cal:
        if row["symbol"] != symbol or row["is_session"] not in ("true", "false"):
            raise ValueError("Invalid calendar evidence")
        day = date.fromisoformat(row["date"])
        if day in calendar_seen or day in sessions and row["is_session"] == "false":
            raise ValueError("Conflicting calendar evidence")
        calendar_seen.add(day)
        if row["is_session"] == "true":
            expected.add(day)
    if expected != sessions:
        raise ValueError("External calendar session mismatch")
    observed_actions = set()
    for row in actions:
        if row["symbol"] != symbol:
            raise ValueError("Corporate-action symbol mismatch")
        day = date.fromisoformat(row["date"])
        if day in observed_actions or day not in sessions:
            raise ValueError("Duplicate or out-of-range corporate-action evidence")
        try:
            split = Decimal(row["split_factor"])
            dividend = Decimal(row["cash_dividend"])
        except (InvalidOperation, TypeError) as exc:
            raise ValueError("Invalid corporate-action values") from exc
        if not split.is_finite() or split <= 0 or not dividend.is_finite() or dividend < 0:
            raise ValueError("Invalid corporate-action values")
        observed_actions.add(day)
    if observed_actions != sessions:
        raise ValueError("Incomplete corporate-action coverage")
    return {
        "status": "EVIDENCE_CONSISTENT_NOT_AUTHENTICATED",
        "symbol": symbol, "sessions": len(sessions),
        "calendar_sha256": calendar_sha256, "actions_sha256": actions_sha256,
        "calendar_publisher": calendar_publisher, "actions_publisher": actions_publisher,
        "publisher_identity_verified": False,
        "adjusted_prices_independently_reconciled": False,
        "eligible_for_strategy_promotion": False,
    }

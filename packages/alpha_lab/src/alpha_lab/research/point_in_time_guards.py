"""Research-only, fail-closed point-in-time and accounting guards.

These functions do not place orders or infer source authenticity.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re

_DATE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")


def utc_instant(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(timezone.utc)


def calendar_date(value):
    if not isinstance(value, str):
        raise ValueError("date must be a string")
    match = _DATE.fullmatch(value)
    if not match:
        raise ValueError("date must be YYYY-M-D or YYYY-MM-DD")
    from datetime import date
    try:
        return date(*(int(part) for part in match.groups()))
    except ValueError as exc:
        raise ValueError("invalid calendar date") from exc


def available_by(publication_time, decision_time):
    """Publication must be known no later than the decision; unknown is rejected."""
    return utc_instant(publication_time) <= utc_instant(decision_time)


def require_available(publication_time, decision_time):
    if not available_by(publication_time, decision_time):
        raise ValueError("future publication cannot inform historical decision")


def require_final_candle(open_time, interval_minutes, decision_time):
    opened = utc_instant(open_time)
    decision = utc_instant(decision_time)
    if not isinstance(interval_minutes, int) or isinstance(interval_minutes, bool) or interval_minutes <= 0:
        raise ValueError("positive integer interval required")
    if opened + timedelta(minutes=interval_minutes) > decision:
        raise ValueError("unfinished candle cannot inform decision")


def finite_decimal(value, *, nonnegative=False):
    if isinstance(value, bool):
        raise ValueError("boolean is not an accounting value")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("invalid accounting number") from exc
    if not result.is_finite() or (nonnegative and result < 0):
        raise ValueError("nonfinite or negative accounting number")
    return result


def reconcile_nav(cash, holdings, marks):
    """Explicit canonical instrument keys; reject missing/extra prices and nonfinite NAV."""
    balance = finite_decimal(cash, nonnegative=True)
    if not isinstance(holdings, dict) or not isinstance(marks, dict):
        raise ValueError("holdings and marks must be mappings")
    if set(holdings) != set(marks):
        raise ValueError("instrument/mark mismatch; normalise symbols upstream")
    for instrument, quantity in holdings.items():
        if not isinstance(instrument, str) or not instrument:
            raise ValueError("invalid canonical instrument")
        balance += finite_decimal(quantity, nonnegative=True) * finite_decimal(marks[instrument], nonnegative=True)
    return finite_decimal(balance, nonnegative=True)


def validate_manifest(raw_bytes, expected_sha256, provenance):
    import hashlib
    if not isinstance(raw_bytes, bytes) or not isinstance(expected_sha256, str):
        raise ValueError("manifest requires raw bytes and SHA256")
    if not isinstance(provenance, str) or not provenance.strip() or provenance.lower().startswith("unknown"):
        raise ValueError("explicit provenance required")
    actual = hashlib.sha256(raw_bytes).hexdigest()
    if len(expected_sha256) != 64 or actual != expected_sha256.lower():
        raise ValueError("source checksum mismatch")
    return actual


def register_run_id(registry, run_id, evidence_sha256):
    """Fail closed on duplicate run identifiers, including exact duplicate submissions."""
    if not isinstance(registry, dict):
        raise ValueError("run registry must be a mapping")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("nonempty run id required")
    if not isinstance(evidence_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", evidence_sha256):
        raise ValueError("SHA256 evidence identifier required")
    if run_id in registry:
        raise ValueError("duplicate run id")
    registry[run_id] = evidence_sha256.lower()
    return run_id

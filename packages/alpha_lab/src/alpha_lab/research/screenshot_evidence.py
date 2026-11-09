"""Untrusted screenshot statement evidence, deliberately separate from broker fills.

No OCR, broker API, authentication claims, account identifiers or live execution.
Transcriptions must be manually reviewed against their source screenshots.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path

STATUS = "USER_SUPPLIED_UNAUTHENTICATED"
MAX_SOURCE_BYTES = 15_000_000


def decimal(value: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("Use explicit decimal strings")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid amount") from exc
    if not result.is_finite():
        raise ValueError("Non-finite amount")
    if result.as_tuple().exponent < -2:
        raise ValueError("Statement currency supports at most two decimals")
    return result


def source_digest(path: str | Path) -> str:
    """Hash original bytes; do not upload screenshots or PII to GitHub."""
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Source must be a regular non-symlink file")
    if not 0 < path.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("Invalid source size")
    return sha256(path.read_bytes()).hexdigest()


def reconcile_rows(rows: list[dict]) -> dict:
    """Verify contiguous, chronological screenshot statement rows.

    Each row requires date_time, amount, balance, source_sha256, description.
    Rows are oldest-first. No missing rows may be silently bridged.
    """
    if not isinstance(rows, list) or not rows or len(rows) > 10000:
        raise ValueError("Expected a bounded nonempty list")
    prior_balance = None
    prior_time = None
    seen = set()
    fees = Decimal("0")
    net = Decimal("0")
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "date_time", "amount", "balance", "source_sha256", "description"
        }:
            raise ValueError("Unexpected or missing statement fields")
        stamp = row["date_time"]
        if not isinstance(stamp, str) or len(stamp) != 19:
            raise ValueError("Timestamp must be YYYY-MM-DDTHH:MM:SS")
        from datetime import datetime
        try:
            datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S")
        except ValueError as exc:
            raise ValueError("Invalid timestamp") from exc
        if prior_time is not None and stamp < prior_time:
            raise ValueError("Rows must be chronological")
        prior_time = stamp
        digest = row["source_sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid source hash")
        description = row["description"]
        if description not in ("TRADE_RESULT", "COMMISSION", "DEPOSIT", "WITHDRAWAL", "TRANSFER"):
            raise ValueError("Unsupported transaction classification")
        amount = decimal(row["amount"])
        balance = decimal(row["balance"])
        if balance < 0:
            raise ValueError("Negative statement balance")
        identity = (stamp, row["amount"], row["balance"], digest, description)
        if identity in seen:
            raise ValueError("Duplicate statement row")
        seen.add(identity)
        if prior_balance is not None and prior_balance + amount != balance:
            raise ValueError("Balance continuity mismatch or missing row")
        prior_balance = balance
        net += amount
        if description == "COMMISSION":
            if amount >= 0:
                raise ValueError("Commission must be negative")
            fees -= amount
    return {
        "classification": STATUS,
        "broker_authenticated": False,
        "real_execution_verified": False,
        "accounting_reconciled": True,
        "rows": len(rows),
        "observed_net_change": str(net),
        "observed_commissions": str(fees),
        "ending_balance": str(prior_balance),
        "warning": "Arithmetic only; requires complete contiguous rows and manual transcription review",
    }

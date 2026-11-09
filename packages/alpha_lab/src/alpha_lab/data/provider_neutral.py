"""Offline canonical OHLCV boundary, reusing existing strict CSV and manifest checks.

No network, API credentials, broker integration, trading or authenticity claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import hashlib
import json

from alpha_lab.data.csv_import import Bar, load_csv
from alpha_lab.data.manifests import build_manifest, verify_manifest

SCHEMA = "alpha-labs.provider-neutral.v1"


@dataclass(frozen=True)
class CanonicalOHLCV:
    timestamp_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class ResearchDataset:
    bars: tuple[CanonicalOHLCV, ...]
    manifest: dict
    provenance_digest: str
    verified_prices: bool = False
    trading_enabled: bool = False


def load_offline_dataset(
    path: str | Path, *, quote_currency: str, interval_minutes: int,
    source_class: str, source_id: str, venue: str, instrument: str,
    retrieved_at_utc: str,
) -> ResearchDataset:
    """Load canonical, strictly spaced UTC bars and integrity-only provenance."""
    dataset = load_csv(path, quote_currency=quote_currency,
                       interval_minutes=interval_minutes, provenance=source_id)
    manifest = build_manifest(
        path, quote_currency=quote_currency, interval_minutes=interval_minutes,
        source_class=source_class, source_id=source_id, venue=venue,
        instrument=instrument, retrieved_at_utc=retrieved_at_utc)
    verify_manifest(path, manifest)
    if manifest["csv_sha256"] != dataset.sha256:
        raise ValueError("Dataset changed during ingestion")
    if manifest["candle_count"] != len(dataset.bars):
        raise ValueError("Dataset candle count mismatch")
    bars = tuple(CanonicalOHLCV(b.time, b.open, b.high, b.low, b.close, b.volume)
                 for b in dataset.bars)
    if any(b.timestamp_utc.tzinfo != timezone.utc for b in bars):
        raise ValueError("Canonical timestamps must be UTC")
    if manifest["price_source_authenticated"] or manifest["independent_price_verification"]:
        raise ValueError("Unauthorised authenticity claim")
    return ResearchDataset(bars, manifest, manifest["metadata_sha256"])


def verify_offline_dataset(path: str | Path, record: ResearchDataset) -> None:
    """Fail closed if bytes, manifest, canonical observations or claims change."""
    if record.verified_prices or record.trading_enabled:
        raise ValueError("Research dataset cannot claim verified prices or trading approval")
    verified = verify_manifest(path, record.manifest)
    if verified["metadata_sha256"] != record.provenance_digest:
        raise ValueError("Provenance digest mismatch")
    dataset = load_offline_dataset(
        path, quote_currency=verified["quote_currency"],
        interval_minutes=verified["interval_minutes"],
        source_class=verified["source_class"], source_id=verified["source_id"],
        venue=verified["venue"], instrument=verified["instrument"],
        retrieved_at_utc=verified["retrieved_at_utc"])
    if dataset.bars != record.bars:
        raise ValueError("Canonical observations changed")

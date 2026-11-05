"""Reproducible local dataset manifests. Hashes prove integrity, NOT price authenticity.

This offline helper neither downloads market data nor authenticates an exchange.
A manifest cannot turn user-supplied or synthetic observations into verified prices.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

from alpha_lab.data.csv_import import load_csv

SCHEMA = "alpha-labs.dataset-manifest.v1"
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,79}$")
_ALLOWED_CLASSES = {"synthetic", "user-supplied", "exchange-public"}


def _utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("UTC timestamp must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must include an offset")
    return parsed.astimezone(timezone.utc)


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ValueError(f"Invalid {field} identifier")
    return value


def build_manifest(
    csv_path: str | Path, *, quote_currency: str, interval_minutes: int,
    source_class: str, source_id: str, venue: str, instrument: str,
    retrieved_at_utc: str,
) -> dict:
    """Describe a local data file while explicitly retaining unverified status."""
    if source_class not in _ALLOWED_CLASSES:
        raise ValueError("Unrecognised source class")
    source_id = _identifier(source_id, "source")
    venue = _identifier(venue, "venue")
    instrument = _identifier(instrument, "instrument")
    retrieved = _utc(retrieved_at_utc)
    dataset = load_csv(
        csv_path, quote_currency=quote_currency, interval_minutes=interval_minutes,
        provenance=source_id,
    )
    first, last = dataset.bars[0].time, dataset.bars[-1].time
    if retrieved < last + timedelta(minutes=dataset.interval_minutes):
        raise ValueError("Retrieval timestamp predates the last complete candle close")
    record = {
        "schema": SCHEMA,
        "csv_sha256": dataset.sha256,
        "source_class": source_class,
        "source_id": source_id,
        "venue": venue,
        "instrument": instrument,
        "quote_currency": dataset.quote_currency,
        "interval_minutes": dataset.interval_minutes,
        "candle_count": len(dataset.bars),
        "first_candle_utc": first.isoformat(),
        "last_candle_utc": last.isoformat(),
        "retrieved_at_utc": retrieved.isoformat(),
        "price_source_authenticated": False,
        "independent_price_verification": False,
        "trading_enabled": False,
        "note": "Hashes and structural checks do not authenticate source prices, identifiers or executable fills.",
    }
    record["metadata_sha256"] = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return record


def verify_manifest(csv_path: str | Path, manifest: dict) -> dict:
    """Fail closed on file tampering, metadata mismatches, or inflated assurance."""
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ValueError("Unsupported dataset manifest")
    if (manifest.get("price_source_authenticated") is not False
            or manifest.get("independent_price_verification") is not False
            or manifest.get("trading_enabled") is not False):
        raise ValueError("Manifest improperly claims authentication or trading approval")
    expected = build_manifest(
        csv_path,
        quote_currency=manifest["quote_currency"],
        interval_minutes=manifest["interval_minutes"],
        source_class=manifest["source_class"],
        source_id=manifest["source_id"],
        venue=manifest["venue"],
        instrument=manifest["instrument"],
        retrieved_at_utc=manifest["retrieved_at_utc"],
    )
    if set(expected) != set(manifest) or any(manifest[k] != v for k, v in expected.items()):
        raise ValueError("Manifest does not match the CSV and canonical metadata")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline dataset manifest; source NOT authenticated")
    parser.add_argument("csv")
    parser.add_argument("--quote", required=True)
    parser.add_argument("--minutes", type=int, default=60)
    parser.add_argument("--source-class", choices=sorted(_ALLOWED_CLASSES), required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--venue", required=True)
    parser.add_argument("--instrument", required=True)
    parser.add_argument("--retrieved-at-utc", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    source = Path(args.csv)
    if output.resolve() == source.resolve():
        parser.error("Manifest output must not overwrite its source CSV")
    manifest = build_manifest(
        source, quote_currency=args.quote, interval_minutes=args.minutes,
        source_class=args.source_class, source_id=args.source_id,
        venue=args.venue, instrument=args.instrument,
        retrieved_at_utc=args.retrieved_at_utc,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify_manifest(source, json.loads(output.read_text(encoding="utf-8")))
    print(f"PASS: manifest integrity verified -> {output}; price authenticity UNVERIFIED")


if __name__ == "__main__":
    main()

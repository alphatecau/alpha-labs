"""Reproducible equity dataset metadata. Not source authentication."""
from datetime import date, datetime
from hashlib import sha256
import json

from alpha_lab.data.equity_csv import EquityImport, load_equity_csv
from alpha_lab.domain.assets import AssetClass, Instrument

SCHEMA = "alpha-labs.equity-provenance.v1"
PRICE_BASES = frozenset((
    "unknown", "raw", "split_adjusted", "total_return_adjusted"
))


def digest(record):
    raw = json.dumps(
        record, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(raw).hexdigest()


def build_manifest(imported, *, source_reference, price_basis):
    if not isinstance(imported, EquityImport):
        raise ValueError("EquityImport required")
    if not isinstance(source_reference, str) or not (
        0 < len(source_reference.strip()) <= 500
    ):
        raise ValueError("Source reference required")
    if price_basis not in PRICE_BASES:
        raise ValueError("Unsupported price adjustment declaration")

    instrument = imported.instrument
    record = {
        "schema": SCHEMA,
        "symbol": instrument.symbol,
        "asset_class": instrument.asset_class.value,
        "venue": instrument.venue,
        "calendar": instrument.calendar,
        "quote_currency": imported.dataset.quote_currency,
        "interval_minutes": imported.dataset.interval_minutes,
        "first_session": imported.start.isoformat(),
        "last_session": imported.end.isoformat(),
        "source_id": imported.source_id,
        "source_reference": source_reference.strip(),
        "retrieved_at_utc": imported.retrieved_at_utc.isoformat(),
        "csv_sha256": imported.dataset.sha256,
        "candle_count": len(imported.dataset.bars),
        "price_basis_declared": price_basis,
        "source_authenticity_verified": False,
        "source_rights_verified": False,
        "publication_time_verified": False,
        "corporate_actions_verified": False,
        "research_admissible": False,
        "trading_enabled": False,
    }
    record["metadata_sha256"] = digest(record)
    return record


def verify_manifest(csv_path, manifest):
    if not isinstance(manifest, dict):
        raise ValueError("Invalid manifest")
    if manifest.get("schema") != SCHEMA:
        raise ValueError("Unsupported manifest schema")

    flags = (
        "source_authenticity_verified",
        "source_rights_verified",
        "publication_time_verified",
        "corporate_actions_verified",
        "research_admissible",
        "trading_enabled",
    )
    if any(manifest.get(field) is not False for field in flags):
        raise ValueError("Unsupported verification claim")

    instrument = Instrument(
        manifest["symbol"],
        AssetClass(manifest["asset_class"]),
        manifest["venue"],
        manifest["quote_currency"],
        manifest["calendar"],
    )
    imported = load_equity_csv(
        csv_path,
        instrument=instrument,
        start=date.fromisoformat(manifest["first_session"]),
        end=date.fromisoformat(manifest["last_session"]),
        source_id=manifest["source_id"],
        retrieved_at_utc=datetime.fromisoformat(
            manifest["retrieved_at_utc"]
        ),
    )
    expected = build_manifest(
        imported,
        source_reference=manifest["source_reference"],
        price_basis=manifest["price_basis_declared"],
    )
    if expected != manifest:
        raise ValueError("CSV or provenance metadata mismatch")
    return expected

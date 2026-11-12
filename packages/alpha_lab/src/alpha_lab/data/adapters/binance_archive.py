"""Research-only Binance Vision monthly SPOT 1h downloader with checksums.

No account, keys, exchange order endpoints or trade execution. Source archives
are exchange-published but NOT independently cross-checked against another venue.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from calendar import monthrange
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

from alpha_lab.data.csv_import import load_csv
from alpha_lab.data.manifests import build_manifest, verify_manifest

BASE = "https://data.binance.vision/data/spot/monthly/klines"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
INTERVAL = "1h"
MAX_ARCHIVE_BYTES = 16_000_000
MAX_CSV_BYTES = 12_000_000
SHA256_LINE = re.compile(r"^([a-fA-F0-9]{64})\s+\*?([^\s/\\]+)\s*$")
UTC = timezone.utc


def _month(year: int, month: int) -> tuple[datetime, datetime]:
    if not 2017 <= year <= 2100 or not 1 <= month <= 12:
        raise ValueError("Invalid archive month")
    start = datetime(year, month, 1, tzinfo=UTC)
    end = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1, tzinfo=UTC)
    return start, end


def month_range(start: str, end: str) -> list[tuple[int, int]]:
    """Inclusive range of complete months, e.g. 2023-01 through 2025-12."""
    if not re.fullmatch(r"\d{4}-\d{2}", start) or not re.fullmatch(r"\d{4}-\d{2}", end):
        raise ValueError("Months must have format YYYY-MM")
    a, b = tuple(map(int, start.split("-"))), tuple(map(int, end.split("-")))
    _month(*a)
    _month(*b)
    if a > b or (b[0] - a[0]) * 12 + b[1] - a[1] > 119:
        raise ValueError("Invalid range or range exceeds 10 years")
    return [
        (year, month)
        for year in range(a[0], b[0] + 1)
        for month in range(1, 13)
        if a <= (year, month) <= b
    ]


def archive_name(symbol: str, year: int, month: int) -> str:
    if symbol not in SYMBOLS:
        raise ValueError("Unsupported market symbol; BTCUSDT/ETHUSDT/SOLUSDT only")
    _month(year, month)
    return f"{symbol}-{INTERVAL}-{year:04d}-{month:02d}.zip"


def _read_url(url: str) -> bytes:
    request = Request(
        url, headers={"User-Agent": "AlphaLabsResearch/0.7 (read-only-public-archive)"}
    )
    with urlopen(request, timeout=35) as response:
        # Limit network and disk cost, prevent oversized files.
        result = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(result) > MAX_ARCHIVE_BYTES:
        raise ValueError("Downloaded public archive exceeds file-size limit")
    return result


def verify_checksum(
    zip_bytes: bytes, checksum_bytes: bytes, expected_filename: str
) -> str:
    if len(zip_bytes) > MAX_ARCHIVE_BYTES:
        raise ValueError("Oversized archive")
    try:
        checksum = checksum_bytes.decode("ascii").strip()
    except UnicodeError as exc:
        raise ValueError("Checksum is not ASCII") from exc
    match = SHA256_LINE.fullmatch(checksum)
    if not match or match.group(2) != expected_filename:
        raise ValueError("Checksum filename or format mismatch")
    digest = hashlib.sha256(zip_bytes).hexdigest()
    if digest != match.group(1).lower():
        raise ValueError("Archive failed official SHA-256 checksum")
    return digest


def parse_archive(
    data: bytes,
    symbol: str,
    year: int,
    month: int,
    *,
    anomalies: list[dict] | None = None,
) -> list[tuple[str, ...]]:
    """Require a complete hourly open-time grid; flag early close metadata.

    Some checksum-valid Binance archives contain an early in-bar close_time.
    Never silently accept such rows: a caller must supply an anomaly ledger.
    No missing/open-time gaps, mixed timestamp units, late closes, or malformed
    OHLCV are accepted. This does NOT establish candle completeness.
    """
    expected = archive_name(symbol, year, month).removesuffix(".zip") + ".csv"
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("Oversized compressed archive")
    first, end = _month(year, month)
    rows: list[tuple[str, ...]] = []
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            members = [entry for entry in archive.infolist() if not entry.is_dir()]
            if len(members) != 1 or members[0].filename != expected:
                raise ValueError(
                    "Unexpected ZIP member, suspicious path or additional content"
                )
            if members[0].file_size > MAX_CSV_BYTES:
                raise ValueError("Uncompressed data exceeds safe limit")
            # zipfile performs CRC checks when reading the complete member.
            with archive.open(members[0]) as stream:
                content = stream.read(MAX_CSV_BYTES + 1)
            if len(content) > MAX_CSV_BYTES:
                raise ValueError("Decompressed data exceeds safe limit")
    except (BadZipFile, OSError, EOFError) as exc:
        raise ValueError("Invalid or corrupt ZIP archive") from exc
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("ZIP CSV is not UTF-8") from exc
    expected_stamp = first
    for idx, values in enumerate(csv.reader(io.StringIO(decoded)), 1):
        if (
            idx == 1
            and values
            and values[0].strip().lower() in {"open time", "open_time"}
        ):
            continue
        if len(values) != 12:
            raise ValueError(f"Invalid 12-column kline row {idx}")
        try:
            stamp = int(values[0])
            close_stamp = int(values[6])
            # Official Binance spot archive uses milliseconds before 2025,
            # microseconds from 1 January 2025 onward.
            factor = 1_000_000 if year >= 2025 else 1_000
            if stamp % (factor * 3600) != 0:
                raise ValueError("Non-hourly timestamp alignment")
            observed = datetime.fromtimestamp(stamp / factor, tz=UTC)
            if observed != expected_stamp or observed >= end:
                raise ValueError(
                    f"Missing, duplicated, reordered or out-of-month candle: expected {expected_stamp.isoformat()}, observed {observed.isoformat()}"
                )
            expected_close = stamp + factor * 3600 - 1
            if close_stamp != expected_close:
                if not (stamp <= close_stamp < expected_close):
                    raise ValueError(
                        "Incorrect close timestamp or timestamp units: "
                        f"open={stamp}, observed_close={close_stamp}, "
                        f"expected_close={expected_close}, unit={'us' if year >= 2025 else 'ms'}"
                    )
                if anomalies is None:
                    raise ValueError(
                        "Early close timestamp requires an explicit anomaly ledger"
                    )
                anomalies.append(
                    {
                        "row": idx,
                        "open_time_utc": observed.isoformat(),
                        "recorded_close_timestamp": close_stamp,
                        "expected_close_timestamp": expected_close,
                        "earliness_in_source_units": expected_close - close_stamp,
                        "timestamp_unit": "us" if year >= 2025 else "ms",
                        "classification": "exchange_archive_early_close_metadata",
                        "requires_independent_review": True,
                    }
                )
            open_price, high_price, low_price, close_price, volume = (
                Decimal(values[j]) for j in (1, 2, 3, 4, 5)
            )
            if not all(
                x.is_finite()
                for x in (open_price, high_price, low_price, close_price, volume)
            ):
                raise ValueError("Nonfinite OHLCV")
            if (
                min(open_price, high_price, low_price, close_price) <= 0
                or volume < 0
                or high_price < max(open_price, close_price, low_price)
                or low_price > min(open_price, close_price)
            ):
                raise ValueError("Invalid OHLCV consistency")
            rows.append(
                (
                    observed.isoformat(),
                    str(open_price),
                    str(high_price),
                    str(low_price),
                    str(close_price),
                    str(volume),
                )
            )
            expected_stamp += timedelta(hours=1)
        except (ValueError, InvalidOperation, OverflowError, OSError) as exc:
            raise ValueError(f"Invalid kline data at row {idx}: {exc}") from exc
    if expected_stamp != end:
        raise ValueError(
            f"Incomplete monthly series: {len(rows)} hours, expected {monthrange(year, month)[1] * 24}"
        )
    return rows


def fetch_month(
    symbol: str, year: int, month: int, raw_dir: Path, *, transport=_read_url
) -> tuple[list[tuple[str, ...]], dict]:
    """Download or check cached source archive; never accept missing checksums."""
    filename = archive_name(symbol, year, month)
    url = f"{BASE}/{symbol}/1h/{filename}"
    folder = Path(raw_dir) / symbol
    folder.mkdir(parents=True, exist_ok=True)
    zippath = folder / filename
    checkpath = folder / f"{filename}.CHECKSUM"
    if zippath.exists() and checkpath.exists():
        zipped = zippath.read_bytes()
        checked = checkpath.read_bytes()
    else:
        # Fetch both before storing anything as usable.
        zipped = transport(url)
        checked = transport(url + ".CHECKSUM")
    digest = verify_checksum(zipped, checked, filename)
    # Retain the checksum-verified original for forensics even if parsing fails.
    # A cached archive is NOT an accepted/research-ready dataset.
    if not zippath.exists() or not checkpath.exists():
        zippath.write_bytes(zipped)
        checkpath.write_bytes(checked)
    anomalies: list[dict] = []
    candles = parse_archive(zipped, symbol, year, month, anomalies=anomalies)
    return candles, {
        "month": f"{year:04d}-{month:02d}",
        "archive_url": url,
        "archive_sha256": digest,
        "official_checksum_matched": True,
        "bars": len(candles),
        "close_timestamp_anomalies": anomalies,
        "close_timestamp_anomaly_count": len(anomalies),
    }


def build_dataset(
    symbol: str, start: str, end: str, root: Path, *, transport=_read_url
) -> dict:
    """Assemble one uniform, checked multi-year 1h dataset and source manifest."""
    months = month_range(start, end)
    if symbol not in SYMBOLS:
        raise ValueError("Unsupported symbol")
    # Complete-month data only. Missing month => fail closed; never interpolate.
    now = datetime.now(UTC)
    if _month(*months[-1])[1] > now:
        raise ValueError("Latest requested month is not yet complete")
    root = Path(root)
    raw = root / "raw" / "binance-vision" / "spot-monthly-1h"
    curated = root / "curated" / "binance-vision"
    curated.mkdir(parents=True, exist_ok=True)
    dest = curated / f"{symbol}-1h-{start}_to_{end}.csv"
    manifest_path = dest.with_suffix(".manifest.json")
    # To avoid silently replacing a previous research dataset, reject
    # existing outputs. Reproducibility requires an explicit separate run.
    if dest.exists() or manifest_path.exists():
        raise FileExistsError(
            f"Dataset already exists: {dest}. Use a new date range or archive it first."
        )
    collected = []
    provenance = []
    for year, month in months:
        candle_rows, entry = fetch_month(symbol, year, month, raw, transport=transport)
        collected.extend(candle_rows)
        provenance.append(entry)
    # Atomic creation avoids presenting a partially written dataset as valid.
    pending = dest.with_name(dest.name + ".pending")
    try:
        with pending.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, lineterminator="\n")
            writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
            writer.writerows(collected)
        dataset = load_csv(
            pending,
            quote_currency="USDT",
            interval_minutes=60,
            provenance="binance-vision-spot-monthly-verified-archive-digest",
        )
        retrieved = datetime.now(UTC).isoformat()
        base = build_manifest(
            pending,
            quote_currency="USDT",
            interval_minutes=60,
            source_class="exchange-public",
            source_id="binance-vision-spot-monthly-1h",
            venue="binance-spot",
            instrument=symbol,
            retrieved_at_utc=retrieved,
        )
        verify_manifest(pending, base)
        full = {
            "schema": "alpha-labs.binance-vision-dataset.v1",
            "symbol": symbol,
            "market_type": "spot_only_long_flat_no_shorting",
            "first_month": start,
            "last_month": end,
            "csv_sha256": dataset.sha256,
            "candle_count": len(dataset.bars),
            "source_archives": provenance,
            "source_close_timestamp_anomaly_count": sum(
                entry["close_timestamp_anomaly_count"] for entry in provenance
            ),
            "source_close_timestamp_anomalies_require_review": any(
                entry["close_timestamp_anomaly_count"] for entry in provenance
            ),
            "dataset_manifest": base,
            "source_archive_checksums_verified": True,
            "independent_price_crosscheck_performed": False,
            "real_executable_quotes_available": False,
            "trading_enabled": False,
        }
        # Write manifest before making dataset visible; on failure clean up.
        manifest_path.write_text(
            json.dumps(full, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        pending.replace(dest)
        return {
            "csv": str(dest),
            "manifest": str(manifest_path),
            "sha256": dataset.sha256,
            "bars": len(dataset.bars),
            "months": len(months),
            "symbol": symbol,
        }
    finally:
        if pending.exists():
            pending.unlink()


def verify_dataset(path: Path, manifest_path: Path) -> dict:
    doc = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if (
        doc.get("schema") != "alpha-labs.binance-vision-dataset.v1"
        or doc.get("trading_enabled") is not False
    ):
        raise ValueError("Invalid dataset provenance contract")
    if (
        doc.get("source_archive_checksums_verified") is not True
        or doc.get("independent_price_crosscheck_performed") is not False
    ):
        raise ValueError("Misleading dataset verification declaration")
    from alpha_lab.data.manifests import verify_manifest

    original = doc["dataset_manifest"]
    verify_manifest(path, original)
    expected_provenance = {
        "source_class": "exchange-public",
        "source_id": "binance-vision-spot-monthly-1h",
        "venue": "binance-spot",
        "quote_currency": "USDT",
        "interval_minutes": 60,
    }
    if any(original.get(key) != value for key, value in expected_provenance.items()):
        raise ValueError("Incorrect Binance archive provenance metadata")
    if (
        doc["csv_sha256"] != original["csv_sha256"]
        or doc["candle_count"] != original["candle_count"]
    ):
        raise ValueError("Dataset metadata mismatch")
    if doc["symbol"] != original["instrument"] or doc["symbol"] not in SYMBOLS:
        raise ValueError("Wrong instrument")
    required = month_range(doc["first_month"], doc["last_month"])
    if len(required) != len(doc["source_archives"]):
        raise ValueError("Missing archive entries")
    reported_anomalies = sum(
        entry.get("close_timestamp_anomaly_count", -1)
        for entry in doc["source_archives"]
    )
    if doc.get("source_close_timestamp_anomaly_count") != reported_anomalies or doc.get(
        "source_close_timestamp_anomalies_require_review"
    ) is not bool(reported_anomalies):
        raise ValueError("Invalid source close timestamp anomaly declaration")
    raw_dir = (
        Path(path).resolve().parents[2]
        / "raw"
        / "binance-vision"
        / "spot-monthly-1h"
        / doc["symbol"]
    )
    if (
        sum(entry.get("bars", 0) for entry in doc["source_archives"])
        != doc["candle_count"]
    ):
        raise ValueError("Inconsistent archived candle counts")
    canonical_digest = hashlib.sha256()

    class DigestWriter:
        def write(self, value: str) -> int:
            canonical_digest.update(value.encode("utf-8"))
            return len(value)

    canonical_csv = csv.writer(DigestWriter(), lineterminator="\n")
    canonical_csv.writerow(("timestamp", "open", "high", "low", "close", "volume"))
    for (year, month), entry in zip(required, doc["source_archives"]):
        if (
            entry["month"] != f"{year:04d}-{month:02d}"
            or entry["official_checksum_matched"] is not True
        ):
            raise ValueError("Invalid archive provenance")
        if not re.fullmatch("[0-9a-f]{64}", entry["archive_sha256"]):
            raise ValueError("Invalid archived digest")
        filename = archive_name(doc["symbol"], year, month)
        expected_url = f"{BASE}/{doc['symbol']}/1h/{filename}"
        if (
            entry["archive_url"] != expected_url
            or entry["bars"] != monthrange(year, month)[1] * 24
        ):
            raise ValueError("Inconsistent archive source or month length")
        zipped = (raw_dir / filename).read_bytes()
        checks = (raw_dir / (filename + ".CHECKSUM")).read_bytes()
        if verify_checksum(zipped, checks, filename) != entry["archive_sha256"]:
            raise ValueError("Cached archive no longer matches recorded checksum")
        actual_anomalies: list[dict] = []
        source_rows = parse_archive(
            zipped, doc["symbol"], year, month, anomalies=actual_anomalies
        )
        canonical_csv.writerows(source_rows)
        if entry.get("close_timestamp_anomalies") != actual_anomalies or entry.get(
            "close_timestamp_anomaly_count"
        ) != len(actual_anomalies):
            raise ValueError(
                "Reported close timestamp anomalies do not match the source archive"
            )
    if canonical_digest.hexdigest() != doc["csv_sha256"]:
        raise ValueError(
            "Curated CSV does not match its checksum-verified source archives"
        )
    return doc

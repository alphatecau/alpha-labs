"""Offline, reproducible research evidence export. Never grants trading approval."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import tarfile
import tempfile

from alpha_lab.data.adapters.binance_archive import (
    SYMBOLS, archive_name, month_range, parse_archive, verify_checksum,
)
from alpha_lab.research.long_history import _read_spec, evaluate_spec

SCHEMA = "alpha-labs.research-evidence-bundle.v1"
MAX_TOTAL_BYTES = 128 * 1024 * 1024


def _same_result(left, right) -> bool:
    """Hashes/labels/counts are exact; allow only rounding-level float drift."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same_result(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_result(a, b) for a, b in zip(left, right))
    if isinstance(left, float):
        return math.isfinite(left) and math.isfinite(right) and math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
    return left == right


def _git_commit(root: Path) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def export_evidence(data_root: Path, symbols: list[str], start: str, end: str,
                    output: Path) -> dict:
    """Verify source linkage, reproduce reports, then capture a bounded bundle.

    Includes only selected public candles, provenance, research results and Python
    source. Does not search the home directory, call a network or modify inputs.
    Provider checksums and local replay do not authenticate prices independently.
    """
    month_range(start, end)
    if not symbols or len(symbols) != len(set(symbols)) or any(s not in SYMBOLS for s in symbols):
        raise ValueError("Select unique supported BTCUSDT/ETHUSDT/SOLUSDT symbols")
    output = Path(output).expanduser()
    if output.exists():
        raise FileExistsError("Refusing to overwrite an existing evidence bundle")
    root = Path(data_root).resolve()
    source_root = Path(__file__).resolve().parents[5]
    payloads: dict[str, bytes] = {}

    def capture(path: Path, name: str, boundary: Path) -> bytes:
        if path.is_symlink() or not path.resolve().is_relative_to(boundary):
            raise ValueError("Evidence member must be a regular file within its source directory")
        if path.stat().st_size > MAX_TOTAL_BYTES:
            raise ValueError("Evidence file exceeds the bundle size limit")
        content = path.read_bytes()
        payloads[name] = content
        if sum(map(len, payloads.values())) > MAX_TOTAL_BYTES:
            raise ValueError("Research evidence exceeds the bundle size limit")
        return content

    def capture_data(path: Path) -> bytes:
        return capture(path, "datasets/" + path.relative_to(root).as_posix(), root)

    markets = []
    with tempfile.TemporaryDirectory(prefix="alpha-evidence-replay-") as scratch:
        for symbol in symbols:
            stem = f"{symbol}-1h-{start}_to_{end}"
            csv_path = root / "curated/binance-vision" / (stem + ".csv")
            manifest_path = csv_path.with_suffix(".manifest.json")
            spec_path = root / "replay/experiments" / (stem + ".frozen.json")
            report_path = root / "replay/reports" / (stem + ".report.json")
            spec, manifest = _read_spec(csv_path, manifest_path, spec_path)
            stored = json.loads(report_path.read_text(encoding="utf-8"))
            reproduced = evaluate_spec(csv_path, manifest_path, spec_path,
                                       Path(scratch) / (symbol + ".json"))
            if not _same_result(stored, reproduced):
                raise ValueError(f"Stored research report does not reproduce: {symbol}")
            csv_bytes = capture_data(csv_path)
            manifest_bytes = capture_data(manifest_path)
            if (hashlib.sha256(csv_bytes).hexdigest() != spec["data_sha256"] or
                    hashlib.sha256(manifest_bytes).hexdigest() != spec["manifest_sha256"]):
                raise ValueError("Dataset changed during evidence export")
            if json.loads(capture_data(spec_path)) != spec or json.loads(capture_data(report_path)) != stored:
                raise ValueError("Experiment changed during evidence export")
            for entry in manifest["source_archives"]:
                year, month = map(int, entry["month"].split("-"))
                filename = archive_name(symbol, year, month)
                path = root / "raw/binance-vision/spot-monthly-1h" / symbol / filename
                zipped = capture_data(path)
                checked = capture_data(path.with_name(filename + ".CHECKSUM"))
                if verify_checksum(zipped, checked, filename) != entry["archive_sha256"]:
                    raise ValueError("Source archive changed during evidence export")
            markets.append({"symbol": symbol, "data_sha256": spec["data_sha256"],
                            "specification_sha256": spec["specification_sha256"],
                            "report_reproduced": True,
                            "close_timestamp_anomaly_count": manifest["source_close_timestamp_anomaly_count"]})

    forensic = []
    if "BTCUSDT" in symbols:
        for year, month in ((2023, 1), (2023, 3)):
            name = archive_name("BTCUSDT", year, month)
            path = root / "raw/binance-vision/spot-monthly-1h/BTCUSDT" / name
            check = path.with_name(name + ".CHECKSUM")
            record = {"symbol": "BTCUSDT", "month": f"{year}-{month:02d}",
                      "available": path.is_file() and check.is_file()}
            if record["available"]:
                zipped, checked = capture_data(path), capture_data(check)
                record["archive_sha256"] = verify_checksum(zipped, checked, name)
                anomalies = []
                try:
                    parse_archive(zipped, "BTCUSDT", year, month, anomalies=anomalies)
                    record["complete_hourly_grid"] = True
                except ValueError as exc:
                    record["complete_hourly_grid"] = False
                    record["structural_error"] = str(exc)
                record["close_timestamp_anomalies"] = anomalies
            forensic.append(record)

    for path in sorted((source_root / "packages/alpha_lab/src/alpha_lab").rglob("*.py")):
        capture(path, path.relative_to(source_root).as_posix(), source_root)
    for name in ("multi_year_research.py", "export_research_evidence.py"):
        path = source_root / "scripts" / name
        capture(path, path.relative_to(source_root).as_posix(), source_root)
    metadata = {
        "schema": SCHEMA, "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "first_month": start, "last_month": end, "source_git_commit": _git_commit(source_root),
        "markets": markets, "forensic_archives": forensic,
        "reports_reproduced_locally": True, "independent_price_verification": False,
        "independent_source_review_complete": False, "holdout_independently_sealed": False,
        "trading_enabled": False,
        "files": {name: {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
                  for name, content in sorted(payloads.items())},
    }
    payloads["EVIDENCE_MANIFEST.json"] = (json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in sorted(payloads.items()):
            member = tarfile.TarInfo(name)
            member.size, member.mode, member.mtime = len(content), 0o600, 0
            archive.addfile(member, io.BytesIO(content))
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation; failed validation never creates an output file.
    created = False
    try:
        with output.open("xb") as target:
            created = True
            target.write(buffer.getbuffer())
    except OSError:
        if created:
            output.unlink(missing_ok=True)
        raise
    return {"bundle": str(output.resolve()), "sha256": hashlib.sha256(buffer.getbuffer()).hexdigest(),
            "files": len(payloads), "bytes": output.stat().st_size,
            "reports_reproduced": len(markets), "trading_enabled": False}

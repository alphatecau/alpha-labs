"""Local-only Alpha Labs historical research bridge; no trade or exchange endpoints.

Replaces the development-only `python -m http.server` command on port 8000.
Serves the existing static UI plus one same-origin read-only JSON endpoint.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "/api/v1/research/solusd"  # retained for backwards compatibility
MARKET_CONFIG = {
    "xbtusd": ("XBTUSD", "BTC/USD"),
    "ethusd": ("ETHUSD", "ETH/USD"),
    "solusd": ("SOLUSD", "SOL/USD"),
}
SCHEMA = "alpha-labs.historical-research.v1"
MAX_JSON_BYTES = 2_000_000


def _json_file(path: Path) -> dict:
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Research JSON exceeds size limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Research document is not an object")
    return value


def _utc(iso: str) -> datetime:
    parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Missing timezone")
    return parsed.astimezone(timezone.utc)


def _metric(record: dict, name: str) -> float:
    value = record[name]["return_pct"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid research return metric")
    return round(value, 5)


def load_snapshot(root: Path = ROOT, *, market: str = "solusd", now: datetime | None = None) -> dict:
    if market not in MARKET_CONFIG:
        raise ValueError("Unsupported market")
    expected_pair, market_label = MARKET_CONFIG[market]
    root = Path(root)
    csv_path = root / f"{market}-recent.csv"
    manifest = _json_file(root / f"{market}-recent.csv.manifest.json")
    report = _json_file(root / f"{market}-research.json")
    csv_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    dataset = report["dataset"]
    if not (csv_hash == manifest["written_csv_sha256"] == dataset["sha256"]):
        raise ValueError("CSV and research hashes do not match")
    if (manifest["requested_pair"] != expected_pair or manifest["interval_minutes"] != 60
            or dataset["interval_minutes"] != 60 or dataset["quote_currency"] != "USD"
            or dataset["bars"] != manifest["record_count"] or dataset["bars"] < 80
            or not dataset["provenance"].startswith("kraken-public-ohlc")
            or report["status"] != "HYPOTHESIS_SCREEN_ONLY_NOT_VALIDATED_ALPHA"):
        raise ValueError("Inconsistent research source or unapproved research status")
    fetched = _utc(manifest["fetched_at_utc"])
    candle = _utc(manifest["last_complete_candle_utc"])
    current = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    if fetched > current.replace(microsecond=current.microsecond) and (fetched-current).total_seconds() > 300:
        raise ValueError("Research timestamp lies in the future")
    if candle > fetched:
        raise ValueError("Last candle is newer than retrieval time")
    age_hours = max(0, (current - candle).total_seconds() / 3600)
    results = {}
    for name in ("training", "holdout"):
        item = report["periods"][name]
        results[name] = {
            "strategy_pct": _metric(item, "strategy"),
            "passive_pct": _metric(item, "equal_allocation_buy_hold"),
            "double_cost_pct": _metric(item, "double_cost_strategy"),
        }
    return {
        "schema": SCHEMA,
        "status": "stale" if age_hours > 3 else "historical",
        "source": "Kraken public OHLC (imported, not independently authenticated)",
        "market": market_label,
        "interval_minutes": 60,
        "complete_candles": dataset["bars"],
        "last_candle_utc": candle.isoformat(),
        "fetched_at_utc": fetched.isoformat(),
        "candle_age_hours": round(age_hours, 2),
        "csv_sha256": csv_hash,
        "configuration_sha256": report["configuration_sha256"],
        "model": "Historical EMA long-only hypothesis screening",
        "periods": results,
        "note": "Historical snapshot, not streaming prices, validated alpha, paper P&L or live trades.",
        "trading_enabled": False,
    }


class ResearchHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, research_root: Path = ROOT, **kwargs):
        self.research_root = Path(research_root)
        super().__init__(*args, directory=str(self.research_root / "apps/sites"), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        super().end_headers()

    def _send_json(self, status: int, value: dict):
        data = json.dumps(value, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path in {f"/api/v1/research/{slug}" for slug in MARKET_CONFIG}:
            if url.query:
                self._send_json(400, {"status": "invalid_request"})
                return
            try:
                self._send_json(200, load_snapshot(self.research_root, market=url.path.rsplit("/", 1)[-1]))
            except (FileNotFoundError, KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
                # Do not expose local paths or potentially untrusted file contents.
                print("Read-only research unavailable:", type(exc).__name__)
                self._send_json(503, {"schema": SCHEMA, "status": "offline", "note": "Research missing or validation failed"})
            return
        if url.path.startswith("/api/"):
            self._send_json(404, {"status": "not_found"})
            return
        super().do_GET()

    def do_POST(self):
        self._send_json(405, {"status": "read_only"})


def create_server(root: Path = ROOT, port: int = 8000):
    return ThreadingHTTPServer(("127.0.0.1", port), partial(ResearchHandler, research_root=Path(root)))


def main():
    parser = argparse.ArgumentParser(description="Alpha Labs local-only historical research dashboard")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with create_server(port=args.port) as server:
        print(f"Alpha Labs read-only console: http://127.0.0.1:{server.server_port}/", flush=True)
        print("Historical Kraken snapshot only; no live market feed or execution.", flush=True)
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

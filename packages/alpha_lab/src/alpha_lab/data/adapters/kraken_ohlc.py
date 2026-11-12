"""Read-only public Kraken candle import: no account keys, signing, or order endpoints."""

import argparse
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from alpha_lab.data.csv_import import load_csv

ALLOWED_PAIRS = {"XBTUSD", "ETHUSD", "SOLUSD"}
ALLOWED_INTERVALS = {1, 5, 15, 30, 60, 240, 1440, 10080, 21600}
BASE_URL = "https://api.kraken.com/0/public/OHLC"


def parse_ohlc_payload(payload, *, pair, minutes):
    if pair not in ALLOWED_PAIRS or minutes not in ALLOWED_INTERVALS:
        raise ValueError("Unsupported pair or interval")
    if (
        not isinstance(payload, dict)
        or payload.get("error")
        or not isinstance(payload.get("result"), dict)
    ):
        raise ValueError(
            f"Exchange returned error or malformed response: {str(payload.get('error') if isinstance(payload, dict) else 'not an object')[:200]}"
        )
    result = payload["result"]
    candle_keys = [k for k in result if k != "last" and isinstance(result[k], list)]
    if len(candle_keys) != 1:
        raise ValueError("Expected exactly one market data series")
    series = result[candle_keys[0]]
    if len(series) < 81:
        raise ValueError("Insufficient completed candles for research: require >= 80")
    if len(series) > 721:
        raise ValueError("Unexpected series length exceeds documented limit")
    # Last entry is explicitly described by Kraken as the currently-forming candle.
    complete = series[:-1]
    rows = []
    for candle in complete:
        if not isinstance(candle, list) or len(candle) < 8:
            raise ValueError("Malformed candle")
        t = int(candle[0])
        ts = datetime.fromtimestamp(t, tz=timezone.utc).isoformat()
        rows.append([ts, candle[1], candle[2], candle[3], candle[4], candle[6]])
    return rows, candle_keys[0]


def fetch_public_ohlc(pair="SOLUSD", minutes=60, *, timeout=15):
    if pair not in ALLOWED_PAIRS or minutes not in ALLOWED_INTERVALS:
        raise ValueError("Unsupported pair or interval")
    req = Request(
        BASE_URL + "?" + urlencode({"pair": pair, "interval": minutes}),
        headers={"User-Agent": "AlphaLabsResearch/0.5 (read-only)"},
    )
    with urlopen(req, timeout=timeout) as response:
        raw = response.read(3_000_000)
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError("Invalid JSON market response") from e
    return payload, hashlib.sha256(raw).hexdigest()


def write_csv_and_manifest(payload, raw_sha256, *, pair, minutes, output):
    rows, exchange_market_key = parse_ohlc_payload(payload, pair=pair, minutes=minutes)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO(newline="")
    wr = csv.writer(buffer)
    wr.writerow(["timestamp", "open", "high", "low", "close", "volume"])
    wr.writerows(rows)
    csv_text = buffer.getvalue()
    # Validate *before* writing an accepted dataset; irregular periods fail closed.
    tmp = output.with_suffix(output.suffix + ".pending")
    try:
        tmp.write_text(csv_text, encoding="utf-8")
        dataset = load_csv(
            tmp,
            quote_currency="USD",
            interval_minutes=minutes,
            provenance=f"kraken-public-ohlc:{exchange_market_key}",
        )
        tmp.replace(output)
    finally:
        if tmp.exists():
            tmp.unlink()
    manifest = {
        "source": "Kraken public OHLC (unverified until live request)",
        "api_endpoint": BASE_URL,
        "requested_pair": pair,
        "returned_pair_key": exchange_market_key,
        "quote_currency": "USD",
        "interval_minutes": minutes,
        "record_count": len(rows),
        "first_complete_candle_utc": rows[0][0],
        "last_complete_candle_utc": rows[-1][0],
        "unfinished_final_candle_removed": True,
        "kraken_720_candle_limit": True,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_response_sha256": raw_sha256,
        "written_csv_sha256": dataset.sha256,
        "known_limitations": [
            "Historical coverage limited to 720 most recent entries",
            "Does not include executable spreads, latency, order book or actual fills",
            "Source is a centralised exchange, not Solana DEX",
        ],
    }
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main():
    ap = argparse.ArgumentParser(
        description="Fetch read-only recent Kraken OHLC candles; NO trading or credentials"
    )
    ap.add_argument("--pair", choices=sorted(ALLOWED_PAIRS), default="SOLUSD")
    ap.add_argument(
        "--minutes", choices=sorted(ALLOWED_INTERVALS), type=int, default=60
    )
    ap.add_argument("--output", default="kraken-sample.csv")
    args = ap.parse_args()
    payload, raw_hash = fetch_public_ohlc(args.pair, args.minutes)
    m = write_csv_and_manifest(
        payload, raw_hash, pair=args.pair, minutes=args.minutes, output=args.output
    )
    print(
        f"Downloaded {m['record_count']} complete candles -> {args.output}; last partial candle excluded. No account required."
    )
    print(
        "Warning: 720-candle maximum is insufficient to establish a durable trading advantage."
    )


if __name__ == "__main__":
    main()

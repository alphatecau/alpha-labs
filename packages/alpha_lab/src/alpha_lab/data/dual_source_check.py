"""Read-only, fail-closed Binance/CoinGecko market-price cross-check.

No orders, exchange account, or trading credentials are supported.
"""
from __future__ import annotations

import json
import os
import time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BINANCE = "https://data-api.binance.vision"
COINGECKO = "https://api.coingecko.com/api/v3"
ASSETS = {
    "BTC": ("BTCUSDT", "bitcoin"),
    "ETH": ("ETHUSDT", "ethereum"),
    "SOL": ("SOLUSDT", "solana"),
}


class MarketDataHalt(Exception):
    """Market data cannot be trusted; do not generate an actionable signal."""


def _json_get(url: str, headers: dict[str, str] | None = None) -> object:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "alpha-labs-research/1", **(headers or {})})
    try:
        with urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise MarketDataHalt("market data HTTP failure")
            payload = response.read(65537)
            if len(payload) > 65536:
                raise MarketDataHalt("market data response too large")
            return json.loads(payload)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        raise MarketDataHalt("market data request failed") from exc


def _price(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise MarketDataHalt("invalid price") from exc
    if not result.is_finite() or result <= 0:
        raise MarketDataHalt("nonpositive or nonfinite price")
    return result


def _timestamp(value: object, now: int, *, milliseconds: bool = False, max_age: int = 300) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MarketDataHalt("invalid source timestamp")
    stamp = value // 1000 if milliseconds else value
    if stamp < now - max_age or stamp > now + 30:
        raise MarketDataHalt("stale or future market data")
    return stamp


def crosscheck(asset: str, *, now: int | None = None, max_age: int = 300,
               max_deviation: Decimal = Decimal("0.05")) -> dict[str, object]:
    """Compare recent Binance trade with CoinGecko USD aggregate; return HALT on any failure.

    Binance USDT and CoinGecko USD are not identical quote assets. The deviation
    threshold is an operational sanity check, not a guarantee of executable prices.
    """
    asset = asset.upper()
    if asset not in ASSETS:
        raise MarketDataHalt("unsupported asset")
    if not 0 < max_age <= 3600 or not Decimal("0") < max_deviation <= Decimal("0.5"):
        raise MarketDataHalt("invalid validation policy")
    now = int(time.time()) if now is None else now
    symbol, coin = ASSETS[asset]
    trades = _json_get(f"{BINANCE}/api/v3/trades?" + urlencode({"symbol": symbol, "limit": 1}))
    if not isinstance(trades, list) or len(trades) != 1 or not isinstance(trades[0], dict):
        raise MarketDataHalt("invalid Binance trades response")
    trade = trades[0]
    binance_price = _price(trade.get("price"))
    binance_at = _timestamp(trade.get("time"), now, milliseconds=True, max_age=max_age)

    headers = {}
    key = os.environ.get("COINGECKO_DEMO_API_KEY", "")
    if key:
        headers["x-cg-demo-api-key"] = key
    gecko = _json_get(f"{COINGECKO}/simple/price?" + urlencode({
        "ids": coin, "vs_currencies": "usd", "include_last_updated_at": "true"
    }), headers)
    if not isinstance(gecko, dict) or not isinstance(gecko.get(coin), dict):
        raise MarketDataHalt("invalid CoinGecko response")
    quote = gecko[coin]
    gecko_price = _price(quote.get("usd"))
    gecko_at = _timestamp(quote.get("last_updated_at"), now, max_age=max_age)
    deviation = abs(binance_price - gecko_price) / gecko_price
    if deviation > max_deviation:
        raise MarketDataHalt("cross-provider price deviation exceeds policy")
    return {
        "status": "VERIFIED_RESEARCH_DATA",
        "asset": asset,
        "binance_symbol": symbol,
        "binance_usdt": str(binance_price),
        "binance_trade_at_utc": binance_at,
        "coingecko_usd": str(gecko_price),
        "coingecko_updated_at_utc": gecko_at,
        "relative_deviation": str(deviation),
        "observed_at_utc": now,
        "note": "USDT/USD cross-check only; not an executable quote or trading authorisation",
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Read-only dual-source market-data check")
    parser.add_argument("--asset", choices=sorted(ASSETS), required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(crosscheck(args.asset), sort_keys=True))
        return 0
    except MarketDataHalt as exc:
        print(json.dumps({"status": "HALT", "asset": args.asset, "reason": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Rebuild public dashboard economics from the reviewed November research archive."""
import argparse
import hashlib
import io
import json
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from alpha_lab.backtest.costs import CostModel
from alpha_lab.backtest.engine import replay
from alpha_lab.data.csv_import import load_csv
from alpha_lab.research.strategies.momentum import ema_signal
from deployment.staging_probe import AUDIT, AUDIT_SHA256

ROOT = AUDIT.parent
FX = ROOT / "2026-11-21_usdt_aud"
MARKS = {
    "opening": ("2025-06-15T19:00:00+00:00", "4c8c80a1b3741cc6f642e6ca09858193dbdc7aa254b86689a9f3f781d144cad9"),
    "closing": ("2026-01-01T00:00:00+00:00", "fd65e8dd1c6c1b8aecd960e1bd5283035a026e77a5bf2b8c850ee67310454317"),
}


def verified(raw, digest):
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Source digest mismatch")
    return raw


def read_mark(label):
    boundary, digest = MARKS[label]
    stamp = int(datetime.fromisoformat(boundary).timestamp())
    payload = json.loads(verified((FX / f"{label}.json").read_bytes(), digest), parse_float=Decimal)
    trades = payload["result"]["USDTAUD"]
    if payload["error"] or trades != sorted(trades, key=lambda row: (row[2], row[6])):
        raise ValueError("Invalid Kraken trade sequence")
    i = next(i for i, row in enumerate(trades) if row[2] >= stamp)
    if i == 0:
        raise ValueError("Missing observation before valuation")
    price, quantity, tick, _, _, _, trade_id = trades[i-1]
    if (trades[i][6] != trade_id + 1 or not 0 < stamp - tick <= 300
            or not Decimal(price).is_finite() or min(Decimal(price), Decimal(quantity)) <= 0):
        raise ValueError("Unverified or stale USDT/AUD valuation mark")
    return {"valuation_utc": boundary, "rate_aud_per_usdt": price, "trade_id": trade_id,
            "observed_utc": datetime.fromtimestamp(float(tick), timezone.utc).isoformat(),
            "source_sha256": digest,
            "source_url": f"https://api.kraken.com/0/public/Trades?pair=USDTAUD&since={(stamp-180)*10**9}&count=12"}


def reconcile(result, mark, costs):
    """Rebuild cash and inventory from fill quantities, prices and published cost assumptions."""
    cash, inventory, fees = Decimal(result.starting_balance), Decimal(0), Decimal(0)
    for fill in result.orders:
        amount, price = Decimal(fill["quantity"]), Decimal(fill["price"])
        notional = amount * price
        fee = notional * costs.fee_bps / 10000
        if fee != Decimal(fill["fee"]):
            raise ValueError("Fill fee mismatch")
        fees += fee
        if fill["kind"] == "BUY":
            cash -= notional + fee
            inventory += amount
        elif fill["kind"] == "SELL":
            cash += notional - fee
            inventory -= amount
        else:
            raise ValueError("Unknown fill type")
        if inventory < 0 or cash < 0:
            raise ValueError("Cash or inventory went negative")
    bid = mark * (1 - costs.adverse_slippage_bps / 10000)
    nav = cash + inventory * bid * (1 - costs.fee_bps / 10000)
    if fees != Decimal(result.total_modelled_fees) or abs(nav - Decimal(result.final_liquidatable_value)) > Decimal("1e-18"):
        raise ValueError("Ledger did not reconcile")


def market_evidence(archive, market, marks, tmp):
    symbol = market["symbol"]
    name = f"{symbol}-1h-2023-04_to_2025-12"
    csv = tmp / f"{name}.csv"
    csv.write_bytes(verified(archive.extractfile(f"datasets/curated/binance-vision/{name}.csv").read(), market["data_sha256"]))
    dataset = load_csv(csv, quote_currency="USDT", provenance="Binance Vision")
    report = json.load(archive.extractfile(f"datasets/replay/reports/{name}.report.json"))
    period = market["periods"]["test_unsealed"]
    recorded = report["periods"]["test_unsealed"]
    start, end = report["boundaries_index"]["test_unsealed"]
    if (dataset.bars[start].time.isoformat() != marks["opening"]["valuation_utc"]
            or recorded["end_exclusive_utc"] != marks["closing"]["valuation_utc"]
            or period["end_exclusive_utc"] != recorded["end_exclusive_utc"]
            or report["configuration"] != market["configuration"] or report["dataset_sha256"] != dataset.sha256):
        raise ValueError("Window, configuration or dataset mismatch")
    cfg = report["configuration"]
    signals = ema_signal([bar.close for bar in dataset.bars], cfg["fast"], cfg["slow"])
    costs = CostModel(Decimal(cfg["fee_bps_each_side"]), Decimal(cfg["slippage_bps_each_side"]))
    capital = Decimal(cfg["capital_usdt"])
    runs = []
    for model, key, pct in ((costs, "modelled_strategy", "strategy_return_pct"),
                            (costs.twice(), "strategy_double_execution_friction", "double_cost_return_pct")):
        result = replay(dataset.bars, signals, start, end, costs=model, starting_balance=capital,
                        max_allocation=Decimal(cfg["max_allocation"]))
        reference = recorded[key]
        if (result.return_pct != period[pct] or result.executed_orders != reference["executed_orders_modelled"]
                or Decimal(result.total_modelled_fees) != Decimal(reference["modelled_fees_usdt"])
                or Decimal(result.final_liquidatable_value) != Decimal(reference["final_liquidatable_usdt"])):
            raise ValueError("Replay disagrees with archived report")
        reconcile(result, dataset.bars[end-1].close, model)
        runs.append(result)
    base, stressed = runs
    opening_aud = capital * Decimal(marks["opening"]["rate_aud_per_usdt"])
    closing_aud = Decimal(base.final_liquidatable_value) * Decimal(marks["closing"]["rate_aud_per_usdt"])
    return {"symbol": symbol, "data_sha256": dataset.sha256,
            "opening_usdt": str(capital), "closing_usdt": base.final_liquidatable_value, "pnl_usdt": base.pnl,
            "fees_usdt": base.total_modelled_fees, "slippage_usdt": recorded["modelled_strategy"]["modelled_adverse_slippage_usdt"],
            "estimated_exit_fee_usdt": base.estimated_unexecuted_exit_fee_in_nav, "double_cost_pnl_usdt": stressed.pnl,
            "opening_aud": str(opening_aud), "closing_aud": str(closing_aud), "valuation_change_aud": str(closing_aud - opening_aud),
            "fill_count": base.executed_orders, "closed_trades": base.closed_trades,
            "fills": [{k: row[k] for k in ("time", "kind", "quantity", "price", "fee")} for row in base.orders]}


def build(path):
    audit = json.loads(verified(AUDIT.read_bytes(), AUDIT_SHA256))
    outer = verified(Path(path).read_bytes(), audit["outer_bundle_sha256"])
    marks = {label: read_mark(label) for label in MARKS}
    with zipfile.ZipFile(io.BytesIO(outer)) as zipped:
        inner = verified(zipped.read("AlphaLabs_Research_Evidence_COMPLETE_20261105.tar.gz"), audit["inner_bundle_sha256"])
    with tarfile.open(fileobj=io.BytesIO(inner), mode="r:gz") as archive, tempfile.TemporaryDirectory() as temp:
        markets = [market_evidence(archive, market, marks, Path(temp)) for market in audit["markets"]]
    return {"audit_sha256": AUDIT_SHA256, "source_bundle_sha256": audit["outer_bundle_sha256"],
            "trading_enabled": False, "independently_sealed": False, "quote_currency": "USDT", "fx": marks,
            "valuation_basis": "Change in whole-portfolio AUD marks including currency movement. No AUD conversion was executed. FX fees and spread excluded.",
            "markets": markets}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.archive), ensure_ascii=True, separators=(",", ":")))

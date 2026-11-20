"""Independent, read-only verification of frozen research evidence (stdlib only)."""
import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/evidence/2026-11-05_REPRODUCTION_AUDIT.json"
FROZEN_SHA = "e1f03b0caf41e86d90ba582465ab038a93ce9be09669adce3b4fac8692c3e06f"
EXPECTED = {"BTCUSDT": "-11.011939172996046", "ETHUSDT": "-0.7093147386858387", "SOLUSDT": "-7.34621242943542"}

def verify(path=AUDIT):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_SHA:
        raise ValueError("frozen audit digest mismatch")
    audit = json.loads(raw)
    if audit.get("holdout_independently_sealed") is not False:
        raise ValueError("historical holdout classification changed")
    if audit.get("baseline_promotion") != "REJECT_EMA_12_48_FOR_FORWARD_TRADING_PROMOTION":
        raise ValueError("baseline promotion status changed")
    markets = audit.get("markets", [])
    if len(markets) != 3 or {m["symbol"] for m in markets} != set(EXPECTED):
        raise ValueError("market inventory changed")
    out = {}
    for m in markets:
        symbol = m["symbol"]
        cfg = m["configuration"]
        if (cfg["fast"], cfg["slow"], cfg["strategy"]) != (12, 48, "EMA_12_48_FROZEN_LONG_FLAT"):
            raise ValueError("EMA baseline mutated")
        p = m["periods"]["test_unsealed"]
        result = Decimal(str(p["strategy_return_pct"]))
        if result != Decimal(EXPECTED[symbol]):
            raise ValueError("frozen baseline metric changed")
        initial = Decimal(str(cfg["capital_usdt"]))
        pnl = initial * result / Decimal(100)
        stressed = initial * Decimal(str(p["double_cost_return_pct"])) / Decimal(100)
        out[symbol] = {"currency": "USDT", "initial_capital": str(initial),
                       "unsealed_test_return_pct": str(result), "modelled_pnl_usdt": str(pnl),
                       "double_cost_modelled_pnl_usdt": str(stressed),
                       "independently_sealed": False, "provenance_sha256": m["data_sha256"]}
    return {"status": "FROZEN_BASELINE_REJECTED", "audit_sha256": FROZEN_SHA,
            "not_a_new_backtest": True, "markets": out}

def independent_cash_inventory_ledger(initial, fills, mark, fee_bps, exit_slippage_bps):
    """Independent reference: fills are (side, quantity, execution_price); prices include entry slippage."""
    cash, inventory, fees = Decimal(str(initial)), Decimal(0), Decimal(0)
    rate = Decimal(str(fee_bps)) / Decimal(10000)
    for side, quantity, price in fills:
        qty, px = Decimal(str(quantity)), Decimal(str(price))
        if qty <= 0 or px <= 0 or side not in ("buy", "sell"):
            raise ValueError("invalid fill")
        notional, fee = qty * px, qty * px * rate
        if side == "buy":
            cash -= notional + fee
            inventory += qty
        else:
            if qty > inventory:
                raise ValueError("short inventory prohibited")
            cash += notional - fee
            inventory -= qty
        fees += fee
        if cash < 0:
            raise ValueError("negative cash / leverage prohibited")
    conservative_mark = Decimal(str(mark)) * (1 - Decimal(str(exit_slippage_bps)) / Decimal(10000))
    if conservative_mark <= 0:
        raise ValueError("invalid mark")
    liquidation = cash + inventory * conservative_mark * (1 - rate)
    return {"cash": cash, "inventory": inventory, "realised_fees": fees,
            "estimated_liquidation_nav": liquidation,
            "economic_pnl": liquidation - Decimal(str(initial))}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="-")
    args = parser.parse_args()
    report = json.dumps(verify(), indent=2, sort_keys=True) + "\n"
    if args.output == "-":
        print(report, end="")
    else:
        Path(args.output).write_text(report)

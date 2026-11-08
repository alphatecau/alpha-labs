"""Independent reconciliation of chronological evidence against legacy replay.

Uses a separate accounting path from the evidence exporter, and checks each
period rather than relying only on the final aggregate balance.
"""
from __future__ import annotations
from decimal import Decimal
from alpha_lab.backtest.costs import CostModel
from alpha_lab.research.strategies.momentum import ema_signal

def reconcile_evidence(dataset, evidence: dict) -> dict:
    if evidence.get("dataset_sha256") != dataset.sha256:
        raise ValueError("Dataset checksum mismatch")
    if evidence.get("trading_enabled") is not False:
        raise ValueError("Trading-enabled evidence is not supported")
    start, end = evidence["start_index"], evidence["end_exclusive_index"]
    if not (49 <= start < end <= len(dataset.bars)):
        raise ValueError("Invalid evidence window")
    rows = evidence["periods"]
    if len(rows) != end - start:
        raise ValueError("Missing NAV observations")
    costs = CostModel(Decimal(evidence["modelled_costs"]["fee_bps_each_side"]),
                      Decimal(evidence["modelled_costs"]["slippage_bps_each_side"]))
    capital = Decimal(evidence["capital"])
    allocation = Decimal(evidence["max_allocation"])
    signals = ema_signal([b.close for b in dataset.bars[:end]], 12, 48)
    cash, qty = capital, Decimal(0)
    prior = capital
    fees = Decimal(0)
    trades = 0
    entry_open = False
    for offset, i in enumerate(range(start, end)):
        bar = dataset.bars[i]
        should_hold = signals[i - 1]
        if should_hold and qty == 0:
            budget = min(cash, capital * allocation)
            q = costs.buy_quantity(budget, bar.open)
            outlay = costs.buy_outlay(q, bar.open)
            fee = q * costs.buy_price(bar.open) * costs.fee_bps / 10000
            cash -= outlay
            qty += q
            fees += fee
            entry_open = True
        elif not should_hold and qty > 0:
            proceeds = costs.sell_proceeds(qty, bar.open)
            fee = qty * costs.sell_price(bar.open) * costs.fee_bps / 10000
            cash += proceeds
            fees += fee
            qty = Decimal(0)
            if entry_open:
                trades += 1
                entry_open = False
        nav = cash + costs.sell_proceeds(qty, bar.close)
        row = rows[offset]
        if row["timestamp_utc"] != bar.time.isoformat():
            raise ValueError("Timestamp mismatch")
        if abs(nav - Decimal(row["net_modelled_nav"])) > Decimal("1e-8"):
            raise ValueError("Period NAV mismatch")
        if abs(float(nav / prior - 1) - float(row["net_period_return"])) > 1e-10:
            raise ValueError("Period return mismatch")
        prior = nav
    if abs(prior - Decimal(evidence["final_liquidatable_value"])) > Decimal("1e-8"):
        raise ValueError("Final NAV mismatch")
    if trades != evidence["closed_trades"]:
        raise ValueError("Closed trade count mismatch")
    return {"status": "MODELLED_ACCOUNTING_RECONCILED",
            "trading_enabled": False, "periods_reconciled": len(rows),
            "closed_trades": trades, "modelled_fees": str(fees),
            "independent_price_authentication": False,
            "holdout_independently_sealed": False}

"""Reconstruct a timestamped, modelled NAV evidence series from replay orders.

Research only. Independent calculation from the order ledger, not independent
price authentication or a real execution record.
"""
from __future__ import annotations
from decimal import Decimal
from hashlib import sha256
import json
from alpha_lab.backtest.engine import replay
from alpha_lab.backtest.costs import CostModel
from alpha_lab.research.strategies.momentum import ema_signal

SCHEMA = "alpha-labs.chronological-replay-evidence.v1"

def export_replay_evidence(dataset, *, start: int, end: int,
                           fold_id: str, costs: CostModel | None = None,
                           capital: Decimal = Decimal("10000"),
                           allocation: Decimal = Decimal("0.20"),
                           code_revision: str | None = None) -> dict:
    bars = dataset.bars
    if not (isinstance(start, int) and isinstance(end, int) and
            49 <= start < end <= len(bars)):
        raise ValueError("Invalid chronological window")
    if not isinstance(fold_id, str) or not fold_id.strip():
        raise ValueError("Explicit fold identifier required")
    if not dataset.sha256 or not dataset.provenance:
        raise ValueError("Missing source data provenance")
    if code_revision is not None and (not isinstance(code_revision, str) or not code_revision.strip()):
        raise ValueError("Invalid code revision")
    costs = costs if costs is not None else CostModel(Decimal("10"), Decimal("10"))
    signals = ema_signal([bar.close for bar in bars[:end]], 12, 48)
    result = replay(bars[:end], signals, start, end,
                    starting_balance=capital, max_allocation=allocation, costs=costs)
    cash, qty = Decimal(capital), Decimal(0)
    orders_by_time = {}
    for order in result.orders:
        orders_by_time.setdefault(order["time"], []).append(order)
    rows = []
    prior = Decimal(capital)
    for i in range(start, end):
        bar = bars[i]
        for order in orders_by_time.get(bar.time.isoformat(), []):
            if order["kind"] == "BUY":
                cash -= Decimal(order["quote_outlay"])
                qty += Decimal(order["quantity"])
            elif order["kind"] == "SELL":
                cash += Decimal(order["quote_received"])
                qty -= Decimal(order["quantity"])
            else:
                raise ValueError("Unexpected order type")
        nav = cash + costs.sell_proceeds(qty, bar.close)
        if nav <= 0 or cash < -Decimal("1e-10") or qty < 0:
            raise ValueError("Invalid reconstructed ledger")
        period_return = nav / prior - 1
        rows.append({"timestamp_utc": bar.time.isoformat(),
                     "fold_id": fold_id,
                     "net_modelled_nav": str(nav),
                     "net_period_return": float(period_return)})
        prior = nav
    if abs(prior - Decimal(result.final_liquidatable_value)) > Decimal("1e-8"):
        raise ValueError("Replay NAV parity mismatch")
    body = {"schema": SCHEMA, "trading_enabled": False,
            "status": "HISTORICAL_MODELLED_ONLY_NOT_VALIDATED_ALPHA",
            "dataset_sha256": dataset.sha256, "data_provenance_declared": dataset.provenance,
            "quote_currency": dataset.quote_currency, "interval_minutes": dataset.interval_minutes,
            "code_revision_declared": code_revision,
            "fold_id": fold_id, "start_index": start, "end_exclusive_index": end,
            "modelled_costs": {"fee_bps_each_side": str(costs.fee_bps),
                               "slippage_bps_each_side": str(costs.slippage_bps)},
            "capital": str(capital), "max_allocation": str(allocation),
            "orders": result.orders, "closed_trades": result.closed_trades,
            "modelled_order_count": result.executed_orders,
            "final_liquidatable_value": result.final_liquidatable_value,
            "periods": rows,
            "point_in_time_provenance_verified": False,
            "holdout_independently_sealed": False,
            "executable_fills_verified": False}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    body["evidence_sha256"] = sha256(canonical.encode()).hexdigest()
    return body

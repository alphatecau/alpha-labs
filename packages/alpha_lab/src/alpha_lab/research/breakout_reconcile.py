"""Independent offline order/cash/NAV reconciliation for risk replay reports."""
from __future__ import annotations
from decimal import Decimal
from alpha_lab.backtest.costs import CostModel
from alpha_lab.data.csv_import import Bar

def reconcile_risk_replay(bars: tuple[Bar, ...], start: int, end: int,
                          report: dict, costs: CostModel) -> dict:
    if not (1 <= start < end <= len(bars)):
        raise ValueError("Invalid reconciliation window")
    if report.get("trading_enabled") is not False:
        raise ValueError("Research-only report required")
    orders = report["orders"]
    cash = Decimal(report["starting_balance"])
    qty = Decimal(0)
    reconciled = []
    order_index = 0
    for i in range(start, end):
        stamp = bars[i].time.isoformat()
        # Orders are already chronologically appended within the hour.
        while order_index < len(orders) and orders[order_index]["time"] == stamp:
            order = orders[order_index]
            amount = Decimal(order["quantity"])
            px = Decimal(order["price"])
            fee = Decimal(order["fee"])
            if amount <= 0 or px <= 0 or fee < 0:
                raise ValueError("Invalid order accounting")
            expected_fee = amount*px*costs.fee_bps/10000
            if abs(fee-expected_fee) > Decimal("1e-12"):
                raise ValueError("Fee reconciliation failed")
            if order["kind"] == "BUY":
                if qty != 0: raise ValueError("Overlapping position")
                outlay = amount*px+fee
                if abs(outlay-Decimal(order["quote_outlay"])) > Decimal("1e-12"):
                    raise ValueError("Entry outlay mismatch")
                cash -= outlay
                qty += amount
            elif order["kind"] == "SELL":
                if amount != qty: raise ValueError("Unmatched exit quantity")
                proceeds = amount*px-fee
                if abs(proceeds-Decimal(order["quote_received"])) > Decimal("1e-12"):
                    raise ValueError("Exit proceeds mismatch")
                cash += proceeds
                qty = Decimal(0)
            else:
                raise ValueError("Unknown order type")
            if cash < -Decimal("1e-12"):raise ValueError("Negative cash")
            order_index += 1
        nav = cash+costs.sell_proceeds(qty,bars[i].close)
        expected = Decimal(report["nav_curve"][i-start])
        if abs(nav-expected) > Decimal("1e-10"):
            raise ValueError(f"NAV reconciliation failed at {stamp}")
        reconciled.append(nav)
    if order_index != len(orders):
        raise ValueError("Out-of-window or unordered orders")
    if len(reconciled) != len(report["nav_curve"]):
        raise ValueError("NAV observation count mismatch")
    if abs(reconciled[-1]-Decimal(report["final_liquidatable_value"])) > Decimal("1e-10"):
        raise ValueError("Final equity reconciliation failed")
    return {"status":"PASS","orders_reconciled":len(orders),
            "hourly_nav_observations":len(reconciled),
            "final_liquidatable_value":str(reconciled[-1]),
            "independent_of_replay_state_machine":True,
            "real_execution_prices_verified":False}

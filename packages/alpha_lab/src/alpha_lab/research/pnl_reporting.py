"""Research-only average-cost P&L report for long-only, single-currency fills.

This report is independent of execution, and does not infer spread or impact.
Gross realised P&L excludes fees; net realised P&L allocates buy fees by
quantity sold and subtracts sell fees. Remaining buy fees stay in cost basis.
"""
from decimal import Decimal
from alpha_lab.research.phase1_accounting import D, reconstruct


def report_pnl(orders, closing_prices, *, starting_cash="10000", liquidation_bps="0"):
    audit = reconstruct(orders, closing_prices, starting_cash=starting_cash,
                        liquidation_bps=liquidation_bps)
    inventory = {symbol: {"qty": Decimal(0), "gross_basis": Decimal(0),
                          "fee_basis": Decimal(0)} for symbol in closing_prices}
    realised_gross = Decimal(0)
    realised_net = Decimal(0)
    for order in orders:
        symbol = order["symbol"]
        qty, price, fee = D(order["quantity"]), D(order["price"]), D(order["fee"])
        position = inventory[symbol]
        if order["side"] == "BUY":
            position["qty"] += qty
            position["gross_basis"] += qty * price
            position["fee_basis"] += fee
        else:
            held = position["qty"]
            if held <= 0 or qty > held:
                raise ValueError("Position underflow")
            fraction = qty / held
            gross_alloc = position["gross_basis"] * fraction
            fee_alloc = position["fee_basis"] * fraction
            proceeds = qty * price
            realised_gross += proceeds - gross_alloc
            realised_net += proceeds - gross_alloc - fee_alloc - fee
            position["qty"] -= qty
            position["gross_basis"] -= gross_alloc
            position["fee_basis"] -= fee_alloc
            if position["qty"] == 0:
                position["gross_basis"] = Decimal(0)
                position["fee_basis"] = Decimal(0)
    unrealised_gross = sum(
        (p["qty"] * D(closing_prices[s]) - p["gross_basis"]
         for s, p in inventory.items()), Decimal(0))
    unrealised_net = unrealised_gross - sum(
        (p["fee_basis"] for p in inventory.values()), Decimal(0))
    gross_mark_nav = D(audit["cash"]) + sum(
        (p["qty"] * D(closing_prices[s]) for s, p in inventory.items()), Decimal(0))
    liquidation_haircut = gross_mark_nav - D(audit["final_liquidation_nav"])
    net_pnl = realised_net + unrealised_net - liquidation_haircut
    if abs(D(starting_cash) + net_pnl - D(audit["final_liquidation_nav"])) > Decimal("1e-12"):
        raise ValueError("P&L/NAV identity mismatch")
    if any(inventory[s]["qty"] != D(q) for s, q in audit["positions"].items()):
        raise ValueError("Position reconciliation mismatch")
    return {
        "mode": "RESEARCH_ONLY", "cost_basis_method": "WEIGHTED_AVERAGE",
        "realised_gross_pnl": str(realised_gross),
        "realised_net_pnl": str(realised_net),
        "unrealised_gross_pnl": str(unrealised_gross),
        "unrealised_net_pnl": str(unrealised_net),
        "liquidation_haircut": str(liquidation_haircut),
        "net_total_pnl_after_liquidation": str(net_pnl),
        "final_liquidation_nav": audit["final_liquidation_nav"],
        "fees": audit["fees"], "reconciled": True,
        "spread_vs_impact_separately_identifiable": False,
        "trading_enabled": False,
    }

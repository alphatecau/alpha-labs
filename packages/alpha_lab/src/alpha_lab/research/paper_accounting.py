"""Independent offline long-only realised/unrealised paper P&L reconciliation.

Uses FIFO cost basis and allocates entry fees pro rata to units sold. This is
research accounting, not a tax determination or broker reconciliation.
"""
from collections import deque
from decimal import Decimal
from alpha_lab.research.paper_simulator import number


def reconcile_paper_pnl(fills, marks, *, starting_cash):
    cash = number(starting_cash)
    lots = {}
    realised = Decimal("0")
    total_fees = Decimal("0")
    for fill in fills:
        symbol = fill["symbol"]
        side = fill["side"]
        qty = number(fill["quantity"])
        price = number(fill["price"])
        fee = number(fill["fee"])
        if qty <= 0 or price <= 0 or fee < 0:
            raise ValueError("invalid paper fill")
        queue = lots.setdefault(symbol, deque())
        total_fees += fee
        if side == "BUY":
            cash -= qty * price + fee
            if cash < 0:
                raise ValueError("negative paper cash")
            queue.append([qty, price + fee / qty])
        elif side == "SELL":
            if sum((lot[0] for lot in queue), Decimal("0")) < qty:
                raise ValueError("naked paper sale")
            cash += qty * price - fee
            remaining = qty
            basis = Decimal("0")
            while remaining:
                lot = queue[0]
                used = min(remaining, lot[0])
                basis += used * lot[1]
                lot[0] -= used
                remaining -= used
                if not lot[0]:
                    queue.popleft()
            realised += qty * price - fee - basis
        else:
            raise ValueError("unsupported paper side")
    market_value = Decimal("0")
    open_basis = Decimal("0")
    quantities = {}
    for symbol, queue in lots.items():
        qty = sum((lot[0] for lot in queue), Decimal("0"))
        quantities[symbol] = qty
        if qty:
            if symbol not in marks:
                raise ValueError("missing closing mark: HALT")
            mark = number(marks[symbol])
            if mark <= 0:
                raise ValueError("invalid closing mark: HALT")
            market_value += qty * mark
            open_basis += sum((lot[0] * lot[1] for lot in queue), Decimal("0"))
    nav = cash + market_value
    unrealised = market_value - open_basis
    if nav - number(starting_cash) != realised + unrealised:
        raise ValueError("paper P&L reconciliation failure: HALT")
    return {"cash": cash, "nav": nav, "realised": realised,
            "unrealised": unrealised, "fees": total_fees,
            "positions": quantities}

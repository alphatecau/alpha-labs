"""Independent order-ledger reconstruction for research-only long/cash portfolios.

Does not trust the simulator's cash/holdings or its final NAV. Verifies order
cash deltas, fee arithmetic, position quantities, and liquidation NAV.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation

def D(value):
    try:
        x=Decimal(str(value))
    except (InvalidOperation,TypeError,ValueError) as exc:
        raise ValueError("Invalid numeric ledger value") from exc
    if not x.is_finite():
        raise ValueError("Nonfinite ledger value")
    return x

def reconstruct(orders, closing_prices, *, starting_cash="10000", liquidation_bps="0", require_fill_ids=False):
    cash=D(starting_cash)
    if cash<=0:raise ValueError("Invalid initial cash")
    bps=D(liquidation_bps)
    if not 0<=bps<10000:raise ValueError("Invalid liquidation rate in basis points")
    positions={s:Decimal(0) for s in closing_prices}
    fee_total=Decimal(0)
    gross_notional=Decimal(0)
    seen_fill_ids=set()
    for index,order in enumerate(orders):
        if "fee_currency" in order:
            raise ValueError("Fee currency unsupported by single-currency ledger")
        if require_fill_ids and "fill_id" not in order:
            raise ValueError("Missing required fill identifier")
        if "fill_id" in order:
            fill_id=order["fill_id"]
            if not isinstance(fill_id,str) or not fill_id.strip():
                raise ValueError("Invalid fill identifier")
            if fill_id in seen_fill_ids:
                raise ValueError("Duplicate fill identifier")
            seen_fill_ids.add(fill_id)
        symbol=order["symbol"]
        if symbol not in positions:raise ValueError("Unknown symbol")
        side=order["side"]
        if side not in ("BUY","SELL"):raise ValueError("Invalid order side")
        qty=D(order["quantity"]);px=D(order["price"]);fee=D(order["fee"])
        delta=D(order["cash_delta"])
        if qty<=0 or px<=0 or fee<0:raise ValueError("Invalid execution")
        notional=qty*px
        expected=-(notional+fee) if side=="BUY" else notional-fee
        if abs(delta-expected)>Decimal("1e-12"):
            raise ValueError(f"Order {index}: cash delta does not reconcile")
        if side=="SELL" and positions[symbol]<qty:
            raise ValueError("Naked sale or position underflow")
        positions[symbol]+=qty if side=="BUY" else -qty
        cash+=delta
        fee_total+=fee
        gross_notional+=notional
        if cash<Decimal("-1e-12"):
            raise ValueError("Negative cash")
    nav=cash
    for s,qty in positions.items():
        close=D(closing_prices[s])
        if close<=0:raise ValueError("Invalid closing mark")
        nav+=qty*close*(1-bps/Decimal(10000))
    if nav<=0:raise ValueError("Invalid final NAV")
    return {"cash":str(cash),"positions":{s:str(q) for s,q in positions.items()},
            "fees":str(fee_total),"gross_executed_notional":str(gross_notional),
            "final_liquidation_nav":str(nav),"order_count":len(orders),
            "reconciled":True}

def reconcile_simulation(simulation,closing_prices,*,liquidation_bps):
    audit=reconstruct(simulation["orders"],closing_prices,liquidation_bps=liquidation_bps)
    if abs(D(audit["cash"])-D(simulation["final_cash"]))>Decimal("1e-8"):
        raise ValueError("Final cash mismatch")
    if abs(D(audit["final_liquidation_nav"])-D(simulation["final_nav"]))>Decimal("1e-8"):
        raise ValueError("Final NAV mismatch")
    if abs(D(audit["fees"])-D(simulation["total_fees"]))>Decimal("1e-8"):
        raise ValueError("Fee mismatch")
    return audit

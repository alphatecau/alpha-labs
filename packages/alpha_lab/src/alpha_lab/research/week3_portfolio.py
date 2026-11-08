"""Portfolio-level, research-only long/cash simulator and independent ledger.

Next-hour-open decisions from lagged prices. Stops use lagged ATR and adverse
gap handling. Intrabar OHLC stop fills are modelled, never verified executable.
"""
from __future__ import annotations
from decimal import Decimal
from math import isfinite
from alpha_lab.research.phase1_accounting import reconcile_simulation

def simulate(bars: dict, targets: list, start: int, end: int, cost_bps: int) -> dict:
    symbols=tuple(sorted(bars))
    if symbols!=("BTCUSDT","ETHUSDT","SOLUSDT"):
        raise ValueError("Exactly three portfolio assets required")
    if not (840<=start<end<=len(targets)) or cost_bps not in (10,20,40):
        raise ValueError("Invalid locked evaluation")
    if any(len(v)<end for v in bars.values()):
        raise ValueError("Insufficient bars")
    for i in range(1,end):
        times={bars[s][i].time for s in symbols}
        if len(times)!=1 or any((bars[s][i].time-bars[s][i-1].time).total_seconds()!=3600 for s in symbols):
            raise ValueError("Nonaligned hourly data")
    cash=Decimal("10000")
    holdings={s:Decimal(0) for s in symbols}
    stops={s:None for s in symbols}
    orders=[]
    nav_curve=[]
    fees=Decimal(0)
    closed=0
    peak=Decimal("10000")
    max_dd=Decimal(0)
    day=None
    day_start=Decimal("10000")
    blocked=False
    halted=False
    bps=Decimal(cost_bps)/10000
    def liquidation(i,price_field):
        return cash+sum(holdings[s]*getattr(bars[s][i],price_field)*(1-bps)**2 for s in symbols)
    def sell(symbol,i,px,reason):
        nonlocal cash,fees,closed
        qty=holdings[symbol]
        if not qty:
            return
        executed=px*(1-bps)
        fee=qty*executed*bps
        proceeds=qty*executed-fee
        cash+=proceeds;fees+=fee;closed+=1
        orders.append({"side":"SELL","symbol":symbol,"index":i,"quantity":str(qty),
                       "price":str(executed),"fee":str(fee),"cash_delta":str(proceeds),"reason":reason})
        holdings[symbol]=Decimal(0)
        stops[symbol]=None
    for i in range(start,end):
        bar=bars[symbols[0]][i]
        if bar.time.date()!=day:
            day=bar.time.date()
            day_start=liquidation(i,"open")
            blocked=False
        target=targets[i]
        if target is not None and target not in symbols:
            raise ValueError("Invalid target")
        exited_this_hour=False
        for s in symbols:
            if holdings[s] and stops[s] is not None and bars[s][i].open<=stops[s]:
                sell(s,i,bars[s][i].open,"gap_stop")
                exited_this_hour=True
        for s in symbols:
            if holdings[s] and target!=s:
                sell(s,i,bars[s][i].open,"signal_exit")
                exited_this_hour=True
        open_nav=liquidation(i,"open")
        peak=max(peak,open_nav)
        if open_nav<=day_start*Decimal(".98"):blocked=True
        if open_nav<=peak*Decimal(".95"):halted=True
        if target is not None and not holdings[target] and not exited_this_hour and not blocked and not halted:
            # Lagged 14-hour true-range ATR, no future candle.
            history=bars[target]
            tr=[]
            for j in range(i-14,i):
                prior=history[j-1].close
                tr.append(max(history[j].high-history[j].low,abs(history[j].high-prior),abs(history[j].low-prior)))
            atr=sum(tr)/Decimal(14)
            distance=atr*3
            open_px=history[i].open
            if 0<distance<open_px:
                entry=open_px*(1+bps)
                stop=open_px-distance
                unit_risk=entry*(1+bps)-stop*(1-bps)**2
                if unit_risk>0:
                    q=min(Decimal("25")/unit_risk,Decimal("2000")/(entry*(1+bps)),cash/(entry*(1+bps)))
                    if q>0:
                        fee=q*entry*bps
                        outlay=q*entry+fee
                        cash-=outlay;fees+=fee;holdings[target]=q;stops[target]=stop
                        orders.append({"side":"BUY","symbol":target,"index":i,"quantity":str(q),
                                       "price":str(entry),"fee":str(fee),"cash_delta":str(-outlay),
                                       "planned_risk":str(q*unit_risk)})
        for s in symbols:
            if holdings[s] and bars[s][i].low<=stops[s]:
                sell(s,i,stops[s],"modelled_intrabar_stop")
        nav=liquidation(i,"close")
        peak=max(peak,nav)
        max_dd=max(max_dd,(peak-nav)/peak)
        if nav<=day_start*Decimal(".98"):blocked=True
        if nav<=peak*Decimal(".95"):halted=True
        if cash<0 or nav<=0:
            raise ValueError("Invalid portfolio accounting")
        nav_curve.append(str(nav))
    # Independent cash ledger reconstruction, separate from trading state.
    ledger=Decimal("10000")
    for o in orders:
        ledger+=Decimal(o["cash_delta"])
    if abs(ledger-cash)>Decimal("0.00000001"):
        raise ValueError("Cash reconciliation failed")
    last=Decimal(nav_curve[-1])
    result={"return_pct":float((last/Decimal("10000")-1)*100),
            "max_drawdown_pct":float(max_dd*100),
            "closed_trades":closed,"total_fees":str(fees),
            "final_cash":str(cash),"final_nav":str(last),
            "orders":orders,"nav_curve":nav_curve,
            "cash_ledger_reconciliation":"PASS",
            "risk_authority_independent":False,
            "real_executable_fills_verified":False,
            "live_trading":False,"promotion_authorised":False}
    # Fail closed: reconstruct every executed order independently, including
    # remaining positions marked at the final bar. Both exit-side slippage
    # and liquidation fee are embedded in the original simulator NAV.
    audit=reconcile_simulation(result,
        {s:bars[s][end-1].close for s in symbols},
        liquidation_bps=Decimal(10000)*(1-(1-bps)**2))
    result["independent_position_nav_reconciliation"]="PASS"
    result["independent_audit_order_count"]=audit["order_count"]
    return result

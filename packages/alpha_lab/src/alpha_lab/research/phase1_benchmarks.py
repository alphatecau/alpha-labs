"""Point-in-time long-only risk-matched buy-and-hold comparator.

A comparator, not a validated strategy. Initial weights use pre-entry prices
only; buy-and-hold positions are not rebalanced or optimised in hindsight.
"""
from __future__ import annotations
from math import log,sqrt,isfinite

def risk_matched_buy_hold(prices:dict[str,list[float]],*,start:int,end:int,
                          target_daily_vol:float=.10/sqrt(365),
                          max_asset_weight:float=.15,
                          max_gross:float=1.0,
                          fee_bps:float=20,
                          slippage_bps:float=20):
    if not prices or not (64<=start<end) or not (0<target_daily_vol<1):
        raise ValueError("Invalid benchmark window")
    if not (0<max_asset_weight<=1 and 0<max_gross<=1 and fee_bps>=0 and slippage_bps>=0):
        raise ValueError("Invalid benchmark constraints")
    symbols=sorted(prices)
    if any(len(prices[s])<end or any(not isfinite(float(v)) or v<=0 for v in prices[s][:end]) for s in symbols):
        raise ValueError("Invalid prices")
    # Use only observations ending at start-1 to size holdings executed at start.
    returns=[]
    for i in range(start-63,start):
        row=[log(prices[s][i]/prices[s][i-1]) for s in symbols]
        returns.append(sum(row)/len(symbols))
    mean=sum(returns)/len(returns)
    vol=sqrt(sum((r-mean)**2 for r in returns)/len(returns))
    gross=min(max_gross,target_daily_vol/max(vol,1e-9))
    weights={s:min(max_asset_weight,gross/len(symbols)) for s in symbols}
    # All prices indexed at start represent the execution observation; no
    # signal or sizing input from that observation or later.
    costs=(fee_bps+slippage_bps)/10000
    if costs>=1:raise ValueError("Excessive costs")
    cash=10000.
    quantities={}
    for s in symbols:
        spend=10000*weights[s]
        q=spend/(prices[s][start]*(1+costs))
        quantities[s]=q
        cash-=spend
    curve=[]
    for i in range(start,end):
        nav=cash+sum(quantities[s]*prices[s][i]*(1-costs) for s in symbols)
        if not isfinite(nav) or nav<=0:raise ValueError("Invalid benchmark NAV")
        curve.append(nav)
    return {"starting_cash":10000,"weights":weights,
            "cash_weight":1-sum(weights.values()),
            "nav_curve":curve,"return_pct":(curve[-1]/10000-1)*100,
            "first_execution_index":start,
            "sizing_last_observation_index":start-1,
            "rebalance_count":0,
            "risk_matched_ex_ante":True,
            "costs_included":True,
            "live_trading":False}

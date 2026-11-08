"""Causal Week 3 signal proposals. No orders, broker access or optimisation."""
from __future__ import annotations
from math import log, sqrt
from statistics import mean, pstdev

def proposals(closes: dict[str,list[float]], hypothesis: str) -> list[str | None]:
    if hypothesis not in ("H1","H2","H3"):
        raise ValueError("Unknown pre-registered hypothesis")
    symbols=tuple(sorted(closes))
    n=len(next(iter(closes.values())))
    if symbols != ("BTCUSDT","ETHUSDT","SOLUSDT") or any(len(v)!=n for v in closes.values()):
        raise ValueError("Three aligned markets required")
    if any(not (x>0 and x<float("inf")) for series in closes.values() for x in series):
        raise ValueError("Invalid market price")
    targets=[None]*n
    for i in range(169,n):
        stats={}
        for symbol in symbols:
            history=closes[symbol]
            prior=history[i-1]
            ret168=prior/history[i-169]-1
            ret48=prior/history[i-49]-1
            log_returns=[log(history[j]/history[j-1]) for j in range(i-48,i)]
            vol=sqrt(sum(x*x for x in log_returns)/48)
            sample=history[i-48:i]
            avg=mean(sample)
            deviation=pstdev(sample)
            stats[symbol]=(ret168,ret48,vol,avg,deviation,prior)
        if hypothesis=="H3":
            # Rebalance once daily; hold the previous allocation otherwise.
            if i%24:
                targets[i]=targets[i-1]
            else:
                best=max(symbols,key=lambda s:stats[s][0])
                targets[i]=best if stats[best][0]>0 else None
        elif hypothesis=="H1":
            # A separate single-market run is required for H1/H2.
            raise ValueError("Use single_market_proposals for H1/H2")
    return targets

def single_market_proposals(closes: list[float], hypothesis: str) -> list[bool]:
    if hypothesis not in ("H1","H2"):
        raise ValueError("Invalid single-market hypothesis")
    n=len(closes)
    if any(not (x>0 and x<float("inf")) for x in closes):
        raise ValueError("Invalid price")
    targets=[False]*n
    hold=0
    for i in range(169,n):
        p=closes[i-1]
        ret168=p/closes[i-169]-1
        ret48=p/closes[i-49]-1
        returns=[log(closes[j]/closes[j-1]) for j in range(i-48,i)]
        vol=sqrt(sum(x*x for x in returns)/48)
        if hypothesis=="H1":
            targets[i]=(p>mean(closes[i-168:i]) and ret48>.02 and vol<.04)
        else:
            sample=closes[i-48:i]
            avg=mean(sample)
            dev=pstdev(sample)
            enter=(dev>0 and p<=avg-1.5*dev and vol<.035 and abs(ret168)<.05)
            if targets[i-1] and p<avg and hold<24:
                targets[i]=True
                hold+=1
            elif enter:
                targets[i]=True
                hold=1
            else:
                hold=0
    return targets

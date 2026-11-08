"""Research evidence utilities: immutable experiments, causal grids, cost bridges and benchmarks."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from hashlib import sha256
import json
from math import isfinite

def canonical_hash(record):
    return sha256(json.dumps(record,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def experiment_record(hypothesis_id,protocol_sha256,code_commit,data_sha256,*,status="REGISTERED"):
    if status not in ("REGISTERED","RUNNING","FAIL","INCONCLUSIVE","PASS_ENGINEERING"):
        raise ValueError("Invalid research status")
    if not hypothesis_id or not code_commit or len(protocol_sha256)!=64 or not data_sha256:
        raise ValueError("Missing immutable research provenance")
    payload={"hypothesis_id":hypothesis_id,"protocol_sha256":protocol_sha256,
             "code_commit":code_commit,"data_sha256":data_sha256,"status":status,
             "trading_enabled":False,"promotion_authorised":False}
    return {"record":payload,"record_sha256":canonical_hash(payload)}

def verify_registry(records):
    seen=set()
    for item in records:
        record=item["record"]
        if canonical_hash(record)!=item["record_sha256"]:
            raise ValueError("Tampered experiment record")
        key=(record["hypothesis_id"],record["protocol_sha256"],record["code_commit"])
        if key in seen:raise ValueError("Duplicate experiment identity")
        seen.add(key)
    return True

def verify_hourly_utc_grid(bars):
    if len(bars)<2:raise ValueError("Insufficient bars")
    for i,b in enumerate(bars):
        if b.time.tzinfo is None or b.time.utcoffset()!=timedelta(0) or b.time.minute or b.time.second or b.time.microsecond:
            raise ValueError("Non-UTC hourly bar")
        if b.high<max(b.open,b.close) or b.low>min(b.open,b.close) or b.low<=0:
            raise ValueError("Invalid OHLC")
        if i and b.time-bars[i-1].time!=timedelta(hours=1):
            raise ValueError("Duplicate, missing or future-reordered hourly bar")
    return True

def verify_signal_availability(signal_time,execution_time):
    if signal_time.tzinfo is None or execution_time.tzinfo is None:
        raise ValueError("Timezone required")
    if signal_time>=execution_time:
        raise ValueError("Lookahead or same-time signal")
    return True

def execution_cost_bridge(fills):
    """Fills have independent reference_mid, executed_price, quantity, fee and side.
    Spread and impact are combined in execution_shortfall; they cannot be
    decomposed without separately observed bid/ask and arrival quote.
    """
    total_fee=Decimal(0);total_shortfall=Decimal(0)
    for f in fills:
        q=Decimal(str(f["quantity"]));mid=Decimal(str(f["reference_mid"]))
        px=Decimal(str(f["executed_price"]));fee=Decimal(str(f["fee"]))
        if not all(x.is_finite() for x in (q,mid,px,fee)) or q<=0 or mid<=0 or px<=0 or fee<0:
            raise ValueError("Invalid cost record")
        if f["side"] not in ("BUY","SELL"):raise ValueError("Invalid side")
        total_shortfall+=q*(px-mid)*(1 if f["side"]=="BUY" else -1)
        total_fee+=fee
    return {"explicit_fees":str(total_fee),
            "execution_shortfall_vs_mid":str(total_shortfall),
            "combined_cost":str(total_fee+total_shortfall),
            "spread_vs_impact_separately_identifiable":False}

def lagged_volatility_weights(prices,*,lookback=63,max_weight=0.15):
    """Ex-ante benchmark weights; latest close is NOT used to compute weights."""
    from math import log,sqrt
    if not 0<max_weight<=1 or lookback<2:raise ValueError("Invalid benchmark settings")
    weights={}
    for symbol,series in sorted(prices.items()):
        if len(series)<lookback+2 or any(not isfinite(float(x)) or x<=0 for x in series):
            raise ValueError("Invalid benchmark history")
        # All data up to index -2; execution at next observation.
        historical=series[-lookback-2:-1]
        r=[log(historical[j]/historical[j-1]) for j in range(1,len(historical))]
        avg=sum(r)/len(r)
        variance=sum((x-avg)**2 for x in r)/len(r)
        vol=sqrt(variance)
        weights[symbol]=min(max_weight,0.1/max(vol,1e-6))
    gross=sum(weights.values())
    if gross>1:weights={k:v/gross for k,v in weights.items()}
    return weights

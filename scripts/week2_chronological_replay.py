"""Predeclared, offline, embargoed walk-forward replay and causal regime audit.

No parameter fitting, no adaptive tuning, no broker calls. Historical partitions
are unsealed and not independently untouched. Outputs are descriptive.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from alpha_lab.data.adapters.binance_archive import verify_dataset
from alpha_lab.data.csv_import import load_csv
from alpha_lab.research.breakout_candidate import breakout_signals
from alpha_lab.research.breakout_risk_replay import replay_breakout_risk
from alpha_lab.research.breakout_reconcile import reconcile_risk_replay
from alpha_lab.research.causal_regimes import causal_regime_labels
from alpha_lab.research.selection_gate import selection_aware_gate
from alpha_lab.backtest.costs import CostModel
from decimal import Decimal

MARKETS=("BTCUSDT","ETHUSDT","SOLUSDT")
COSTS=(10,20,40)
FOLDS=5
EMBARGO_HOURS=48
WARMUP=840

def partitions(n):
    if n < 2*365*24:
        raise ValueError("Insufficient multi-year history")
    # Five nonoverlapping chronological evaluation windows; all use earlier
    # data only for indicator warmup. Embargo before each evaluation.
    usable=n-WARMUP
    windows=[]
    for k in range(FOLDS):
        lo=WARMUP+(usable*k)//FOLDS
        hi=WARMUP+(usable*(k+1))//FOLDS
        start=lo+EMBARGO_HOURS
        if hi-start < 500:
            raise ValueError("Fold too short")
        windows.append((start,hi))
    return windows

def audit_market(source,manifest,symbol):
    verified=verify_dataset(source,manifest)
    dataset=load_csv(source,quote_currency="USDT",interval_minutes=60,
                     provenance="binance-vision-spot-monthly-verified-archive-digest")
    bars=dataset.bars
    signals=breakout_signals(bars)
    labels=causal_regime_labels([float(b.close) for b in bars])
    windows=partitions(len(bars))
    output=[]
    for cost in COSTS:
        model=CostModel(fee_bps=Decimal(cost),adverse_slippage_bps=Decimal(cost))
        folds=[]
        for k,(start,end) in enumerate(windows):
            result=replay_breakout_risk(bars,signals,start,end,costs=model)
            rec=reconcile_risk_replay(bars,start,end,result,model)
            if rec["status"]!="PASS":
                raise ValueError("Independent accounting reconciliation failed")
            # Entry-time regime attribution: prior close only.
            by_regime={}
            index_by_time={bars[i].time.isoformat():i for i in range(start,end)}
            for order in result["orders"]:
                if order["kind"]!="BUY":
                    continue
                idx=index_by_time[order["time"]]
                regime=labels[idx]
                by_regime[regime]=by_regime.get(regime,0)+1
            folds.append({"fold":k+1,"start_utc":bars[start].time.isoformat(),
                          "end_exclusive_utc":(bars[end-1].time).isoformat(),
                          "embargo_hours":EMBARGO_HOURS,
                          "return_pct":result["return_pct"],
                          "max_drawdown_pct":result["max_drawdown_pct"],
                          "closed_trades":result["closed_trades"],
                          "entry_regimes":by_regime,
                          "accounting":"PASS"})
        output.append({"market":symbol,"cost_bps_fee_and_slippage_each_side":cost,
                       "folds":folds,"positive_folds":sum(f["return_pct"]>0 for f in folds),
                       "negative_folds":sum(f["return_pct"]<0 for f in folds),
                       "min_fold_return_pct":min(f["return_pct"] for f in folds),
                       "mean_fold_return_pct":sum(f["return_pct"] for f in folds)/len(folds),
                       "decision":"INCONCLUSIVE"})
    return {"market":symbol,"dataset_sha256":verified["csv_sha256"],
            "source_archive_verified":True,"evaluation":output}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data-root",type=Path,default=Path("datasets"))
    p.add_argument("--from-month",default="2023-04")
    p.add_argument("--through-month",default="2025-12")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        p.error("Refusing to overwrite existing report")
    reports=[]
    for symbol in MARKETS:
        name=f"{symbol}-1h-{args.from_month}_to_{args.through_month}"
        csv=args.data_root/"curated"/"binance-vision"/f"{name}.csv"
        reports.append(audit_market(csv,csv.with_suffix(".manifest.json"),symbol))
    comparisons=[entry for report in reports for entry in report["evaluation"]]
    inference=selection_aware_gate(comparisons)
    body={"schema":"alpha-labs.week2.chronological-replay.v1",
          "source_period":f"{args.from_month}..{args.through_month}",
          "fresh_partition_replays":True,
          "training_or_parameter_fitting_per_fold":False,
          "independently_sealed_holdout":False,
          "adaptive_selection_adjustment_complete":False,
          "statistical_significance":"UNDETERMINED",
          "live_trading":False,"promotion_authorised":False,
          "limitations":["Five contiguous partitions with 48h embargo, indicators warmed from earlier data",
                         "No refitting: fixed strategy is independently reset each fold",
                         "OHLC-based stop fills are not independently executable",
                         "Cross-asset risk authority is not implemented",
                         "Nine cost/asset comparisons and prior candidate selection invalidate naive p-values",
                         "Regime attribution counts entry events, not regime-conditioned P&L"],
          "selection_aware_inference":inference,
          "reports":reports}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(body,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("9 chronological modelled evaluations, 45 folds; no independent alpha claim")

if __name__=="__main__":
    main()

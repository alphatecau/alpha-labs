"""Week 3 development-only diagnostic; not an independent holdout."""
import argparse,json
from pathlib import Path
from alpha_lab.data.adapters.binance_archive import verify_dataset
from alpha_lab.data.csv_import import load_csv
from alpha_lab.research.week3_signals import proposals,single_market_proposals
from alpha_lab.research.week3_portfolio import simulate
from alpha_lab.research.selection_gate import exact_two_sided_sign_test

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data-root",type=Path,default=Path("datasets"))
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        p.error("Output exists: refuse overwrite")
    bars={}
    hashes={}
    for s in SYMBOLS:
        path=args.data_root/"curated"/"binance-vision"/f"{s}-1h-2023-04_to_2025-12.csv"
        doc=verify_dataset(path,path.with_suffix(".manifest.json"))
        bars[s]=load_csv(path,quote_currency="USDT",provenance="verified-binance-archive").bars
        hashes[s]=doc["csv_sha256"]
    if len({len(x) for x in bars.values()})!=1:
        raise ValueError("Unequal candle counts")
    n=len(bars["BTCUSDT"])
    closes={s:[float(x.close) for x in bars[s]] for s in SYMBOLS}
    scenarios=[]
    for h in ("H1","H2","H3"):
        markets=SYMBOLS if h!="H3" else ("PORTFOLIO",)
        for market in markets:
            if h=="H3":
                target=proposals(closes,h)
            else:
                signal=single_market_proposals(closes[market],h)
                target=[market if active else None for active in signal]
            # Five contiguous development folds, embargo 48h, no refitting.
            for cost in (10,20,40):
                folds=[]
                for k in range(5):
                    lo=840+(n-840)*k//5+48
                    hi=840+(n-840)*(k+1)//5
                    r=simulate(bars,target,lo,hi,cost)
                    folds.append({"fold":k+1,"return_pct":r["return_pct"],
                                  "max_drawdown_pct":r["max_drawdown_pct"],
                                  "closed_trades":r["closed_trades"],
                                  "cash_ledger_reconciliation":r["cash_ledger_reconciliation"]})
                positive=sum(f["return_pct"]>0 for f in folds)
                negative=sum(f["return_pct"]<0 for f in folds)
                pvalue=exact_two_sided_sign_test(positive,negative)
                scenarios.append({"hypothesis":h,"market":market,"cost_bps_each_side":cost,
                                  "folds":folds,"positive_folds":positive,
                                  "mean_fold_return_pct":sum(f["return_pct"] for f in folds)/5,
                                  "unadjusted_sign_p":pvalue,
                                  "bonferroni_21_p":min(1.,pvalue*21),
                                  "statistically_significant":False,
                                  "decision":"INCONCLUSIVE"})
    if len(scenarios)!=21:
        raise ValueError("Expected 21 registered comparisons")
    output={"schema":"alpha-labs.week3.development-diagnostic.v1",
            "protocol":"docs/research/WEEK3_PREREGISTRATION_20261108.md",
            "period":"2023-04..2025-12","dataset_sha256":hashes,
            "prior_history_inspected":True,"independent_holdout":False,
            "selection_bias_fully_corrected":False,"risk_authority_independent":False,
            "significance":"NOT_ESTABLISHED",
            "comparison_count":21,"fold_count":105,
            "cash_benchmark_return_pct":0,
            "risk_matched_passive_benchmark":"NOT_IMPLEMENTED",
            "market_regime_pnl_attribution":"NOT_IMPLEMENTED",
            "limitations":["Development history previously examined; no independently sealed holdout",
                           "Exact sign tests are not valid evidence of independent folds",
                           "Prior adaptive selection and overlapping comparisons remain",
                           "OHLC stop fills not verified executable",
                           "Independent portfolio risk authority and passive benchmark not implemented"],
            "trading_enabled":False,"promotion_authorised":False,
            "decision":"INCONCLUSIVE","scenarios":scenarios}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x") as f:
        json.dump(output,f,indent=2,sort_keys=True,allow_nan=False)
        f.write("\n")
    print("21 development diagnostics complete; 105 folds; no strategy promotion")
if __name__=="__main__":
    main()

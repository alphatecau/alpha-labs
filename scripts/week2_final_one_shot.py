"""ONE-SHOT frozen 2026 later-period evaluation. Research only; no trading.

Do not rerun after outcome inspection, optimise, or overwrite the result.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from alpha_lab.research.breakout_evaluation import evaluate_breakout_csv

LOCKS={
 "BTCUSDT":("c11dd11b0d2c7fb0b962a43efdf64c23f68197043ef8c72e36c9ce82c880b3c0",
            "af94bb66ee1df10fb80b7c84135ddc8404364fa004e3f4fb7ce1c5c235c5a4cc"),
 "ETHUSDT":("e43a249dfef1604a696856365899d405ecbf52ff9efe9f1e97f11cdfadf1fd8b",
            "fc52ad44de07668280cd651ca0fe0fb8f9875973dc2f9144f058be7017417b0e"),
 "SOLUSDT":("10878933a0cb8737a7879d7827b9cda440e7a38a36a73d9a13747b2e37c49180",
            "6807be2076e75cbf5deb854813c7dd50adafd83ca96691204364a49147a5548d")
}
SOURCE_LOCKS={
 "packages/alpha_lab/src/alpha_lab/research/breakout_candidate.py":"08f3e347e7b03fcd41a1e14a4c91c53ca207183a",
 "packages/alpha_lab/src/alpha_lab/research/breakout_risk_replay.py":"4494ce502355bee304442cde3d5c80acd166b950",
 "packages/alpha_lab/src/alpha_lab/research/selection_gate.py":"1717cdfa8b8ee5571dbed4e06b4c1a7ccd44bfc4",
}
COSTS=(10,20,40)

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def verify_code_locks():
    for path,expected in SOURCE_LOCKS.items():
        observed=subprocess.check_output(["git","hash-object",path],text=True).strip()
        if observed!=expected:
            raise ValueError(f"FROZEN CODE CHANGED: {path}")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data-root",type=Path,default=Path("datasets"))
    p.add_argument("--output-root",type=Path,required=True)
    args=p.parse_args()
    if args.output_root.exists():
        p.error("Refusing repeat evaluation: output directory already exists")
    verify_code_locks()
    verified=[]
    for symbol,(csv_digest,manifest_digest) in LOCKS.items():
        path=args.data_root/"curated"/"binance-vision"/f"{symbol}-1h-2026-01_to_2026-10.csv"
        manifest=path.with_suffix(".manifest.json")
        if sha256(path)!=csv_digest or sha256(manifest)!=manifest_digest:
            raise ValueError(f"FROZEN DATA CHANGED: {symbol}")
        verified.append((symbol,path,manifest))
    # All source and dataset hashes verified BEFORE first evaluation.
    args.output_root.mkdir(parents=True,exist_ok=False)
    results=[]
    for symbol,path,manifest in verified:
        for cost in COSTS:
            name=f"{symbol}-{cost}bps-each-side.json"
            report=evaluate_breakout_csv(
                path,args.output_root/name,
                provenance="binance-vision-spot-monthly-verified-archive-digest",
                start=840,end=7296,fee_bps=str(cost),slippage_bps=str(cost),
                manifest_path=manifest)
            rec=report["risk_constrained_reconciliation"]
            if rec["status"]!="PASS":
                raise ValueError(f"Accounting FAIL: {symbol} {cost}")
            if report["trading_enabled"] or report["promotion_authorised"] or report["profitability_verified"]:
                raise ValueError("Unsafe promotion/trading status")
            candidate=report["risk_constrained_candidate"]
            results.append({"market":symbol,"fee_and_slippage_bps_each_side":cost,
                            "return_pct":candidate["return_pct"],
                            "max_drawdown_pct":candidate["max_drawdown_pct"],
                            "closed_trades":candidate["closed_trades"],
                            "total_modelled_fees":candidate["total_modelled_fees"],
                            "reconciliation":"PASS",
                            "report_sha256":sha256(args.output_root/name)})
    decision={
      "schema":"alpha-labs.week2.final-one-shot.v1",
      "frozen_protocol":"docs/research/WEEK2_FINAL_PRE_EVALUATION_FREEZE_20261108.md",
      "data_period":"2026-01..2026-10",
      "dataset_hashes":{k:{"csv_sha256":v[0],"manifest_sha256":v[1]} for k,v in LOCKS.items()},
      "strategy_selected_before_this_evaluation":True,
      "independently_sealed_holdout":False,
      "selection_bias_fully_corrected":False,
      "statistical_significance":"NOT_ESTABLISHED",
      "evaluation_attempts_per_market_cost":1,
      "engineering_result":"PASS" if len(results)==9 else "FAIL",
      "strategy_result":"INCONCLUSIVE",
      "live_trading":False,"promotion_authorised":False,"deployment_authorised":False,
      "limitations":["Retrospectively selected strategy; not prospectively sealed",
                     "No valid adjusted p-value from a single later historical period",
                     "Nine market/cost comparisons and earlier adaptive selection",
                     "Modelled OHLC stops are not executable quote evidence",
                     "No portfolio-wide risk authority or live execution"],
      "results":results
    }
    (args.output_root/"FINAL_DECISION.json").write_text(
        json.dumps(decision,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print("One-shot historical evaluation completed: engineering PASS; strategy INCONCLUSIVE; no trading")

if __name__=="__main__":
    main()

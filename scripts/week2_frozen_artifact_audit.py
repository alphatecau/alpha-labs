"""Audit immutable GitHub Actions historical research reports; never trades.

Historical NAV fold slicing is NOT a fresh walk-forward backtest.
Bootstrap is descriptive and NOT adjusted for adaptive strategy selection.
"""
import argparse
import hashlib
import json
import math
import random
import zipfile
from decimal import Decimal
from pathlib import Path

ASSETS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
COSTS = (10, 20, 40)
SEED = 20261108
FROZEN_ARTIFACT_SHA256 = "5f6007bd36125e047879b8cc7c4d162938a53b2ce120b95199cee92b0b165986"

def _folds(nav):
    n = len(nav)
    result = []
    for k in range(5):
        start, end = k*n//5, (k+1)*n//5
        prior = nav[start-1] if start else 10000.0
        result.append({"fold": k+1, "hours": end-start,
                       "return_pct": 100*(nav[end-1]/prior-1)})
    return result

def _block_interval(nav, seed, repetitions=2000, block=14):
    # 24h blocks aligned to evaluation start, not UTC calendar boundaries.
    returns = [math.log(nav[i]/(nav[i-24] if i >= 24 else 10000.0))
               for i in range(23, len(nav), 24)]
    n = len(returns)
    if n < 2*block:
        raise ValueError("Insufficient observations for bootstrap")
    rng = random.Random(seed)
    samples = []
    for _ in range(repetitions):
        drawn = []
        while len(drawn) < n:
            k = rng.randrange(n)
            drawn.extend(returns[(k+j)%n] for j in range(block))
        samples.append(100*math.expm1(sum(drawn[:n])))
    samples.sort()
    # Bonferroni familywise 95% across three assets for a single cost tier.
    # Does NOT account for selection of strategies or parameters.
    tail = .05/(2*len(ASSETS))
    return {"familywise_95_lower_pct": samples[int(tail*repetitions)],
            "familywise_95_upper_pct": samples[min(repetitions-1,int((1-tail)*repetitions))],
            "block_days": block, "replications": repetitions,
            "adjustment": "Bonferroni across 3 assets only; NOT strategy-selection adjusted"}

def audit(archive):
    payload = Path(archive).read_bytes()
    if hashlib.sha256(payload).hexdigest() != FROZEN_ARTIFACT_SHA256:
        raise ValueError("Frozen artifact digest mismatch")
    out = {"schema": "alpha-labs.week2.frozen-artifact-audit.v1",
           "artifact_sha256": hashlib.sha256(payload).hexdigest(),
           "source": "historical-breakout-research workflow run 42471018274",
           "independent_holdout": False, "fresh_walk_forward_replay": False,
           "real_executable_quotes": False, "trading_enabled": False,
           "promotion_authorised": False, "decision": "INCONCLUSIVE",
           "regime_analysis": "UNAVAILABLE_NO_MARKET_OHLC_IN_ARTIFACT",
           "limitations": ["Existing historical run only; NAV fold slices are not fresh walk-forward simulations",
                           "Bootstrap not adjusted for adaptive strategy selection",
                           "24h NAV return blocks are not UTC market-day boundaries",
                           "No original market OHLC, so trend/volatility regime attribution unavailable",
                           "No independently sealed forward holdout or real executable fills"],
           "reports": []}
    with zipfile.ZipFile(archive) as z:
        for asset in ASSETS:
            for cost in COSTS:
                name = f"{asset}-breakout-{cost}bps-fee-{cost}bps-slip.json"
                raw = z.read(name)
                report = json.loads(raw)
                if (report.get("trading_enabled") is not False or
                    report.get("profitability_verified") is not False or
                    report.get("source_archive_manifest_verified") is not True or
                    report["risk_constrained_reconciliation"]["status"] != "PASS" or
                    report["window_start"] != 840 or report["window_end_exclusive"] != 24000):
                    raise ValueError(f"Invalid source evidence: {name}")
                candidate = report["risk_constrained_candidate"]
                nav = [float(Decimal(x)) for x in candidate["nav_curve"]]
                if (len(nav) != 23160 or not all(math.isfinite(x) and x>0 for x in nav)
                    or abs(100*(nav[-1]/10000-1)-candidate["return_pct"])>1e-7):
                    raise ValueError(f"NAV verification failed: {name}")
                folds = _folds(nav)
                out["reports"].append({
                    "name": name, "sha256": hashlib.sha256(raw).hexdigest(),
                    "asset": asset, "fee_and_slippage_bps_each_side": cost,
                    "net_return_pct": candidate["return_pct"],
                    "max_drawdown_pct": candidate["max_drawdown_pct"],
                    "closed_trades": candidate["closed_trades"],
                    "historical_nav_folds": folds,
                    "positive_folds": sum(x["return_pct"]>0 for x in folds),
                    "bootstrap_descriptive_interval": _block_interval(nav,SEED+cost+len(asset)),
                    "accounting_reconciliation": "PASS",
                    "decision": "INCONCLUSIVE_NOT_PROMOTABLE"})
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("artifact_zip", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args=p.parse_args()
    result=audit(args.artifact_zip)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,sort_keys=True)
        f.write("\n")
    print("Frozen audit complete; 9 reports; decision INCONCLUSIVE; no trading")

if __name__=="__main__":
    main()

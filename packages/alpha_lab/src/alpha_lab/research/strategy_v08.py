"""Registered, archive-bound historical research. This runner cannot issue a PASS."""
from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Context, Decimal, localcontext
from hashlib import sha256
import json
from pathlib import Path

from alpha_lab.backtest.costs import CostModel
from alpha_lab.backtest.engine import replay
from alpha_lab.data.adapters.binance_archive import verify_dataset
from alpha_lab.data.csv_import import load_csv
from alpha_lab.research.long_history import HOURS_YEAR
from alpha_lab.research.multiple_testing import moving_block_lower_bound, paired_daily_excess_bps
from alpha_lab.research.strategies.momentum import ema_signal
from alpha_lab.research.strategies.regime_trend import MomentumParameters, momentum_signals
from alpha_lab.research.strategy_v08_replay import RiskLimits, replay_window

REGISTRY_SHA256 = "50b1475aadf7f9290fa435e7632dbde56199a94744758b0b554ee0d24c0c2811"
# Exact datasets reproduced in docs/25_MULTYEAR_EVIDENCE_REVIEW_20261105.md.
DATASET_SHA256 = {
    "BTCUSDT": "64b0a9e8f264965249d4c2afaa58946d4eb7fa6e5b285355818e911f5b6daa09",
    "ETHUSDT": "abe096f50f67ead3cb75114ba0592593c9754f771b14e803a1653264f774269f",
    "SOLUSDT": "de365e95e1624d0768b0bd7c37544956ad864b5aa367ef84a5adb1a3d11fb563",
}
COMPARATORS = ("ema_12_48_frozen", "passive_hold", "flat")


@dataclass(frozen=True)
class Study:
    registry: dict
    parameters: MomentumParameters
    capital: Decimal
    allocation: Decimal
    costs: CostModel
    risk: RiskLimits
    half_risk: RiskLimits


def load_study(registry_path: Path) -> Study:
    raw = registry_path.read_bytes()
    if sha256(raw).hexdigest() != REGISTRY_SHA256:
        raise ValueError("Registry differs from the single preregistered v0.8 experiment")
    registry = json.loads(raw)
    (candidate,) = registry["candidates"]
    params = {key: Decimal(value) if key.endswith("_fraction") else value
              for key, value in candidate.items() if key != "id"}
    settings = registry["costs"]
    limits = registry["risk"]
    risk = RiskLimits(
        Decimal(limits["stop_distance_fraction"]), Decimal(limits["max_position_stop_risk_fraction"]),
        Decimal(limits["max_aggregate_stop_risk_fraction"]),
        Decimal(limits["daily_loss_suspension_fraction"]), Decimal(limits["drawdown_suspension_fraction"]),
    )
    return Study(
        registry, MomentumParameters(**params), Decimal(settings["capital_usdt"]),
        Decimal(settings["comparator_allocation_fraction"]),
        CostModel(Decimal(settings["fee_bps_each_side"]), Decimal(settings["adverse_slippage_bps_each_side"])),
        risk, replace(risk, position_stop_risk=Decimal(limits["half_risk_sensitivity_fraction"])),
    )


def load_market(data_root: Path, study: Study, symbol: str):
    scope = study.registry["data"]
    first, last = scope["first_month"], scope["last_month"]
    path = data_root / "curated" / "binance-vision" / f"{symbol}-1h-{first}_to_{last}.csv"
    manifest_path = path.with_suffix(".manifest.json")
    manifest = verify_dataset(path, manifest_path)
    if (manifest["symbol"] != symbol or manifest["first_month"] != first
            or manifest["last_month"] != last or manifest["source_close_timestamp_anomaly_count"]
            or manifest["csv_sha256"] != DATASET_SHA256[symbol]):
        raise ValueError(f"{symbol} inputs differ from the audited, complete historical scope")
    dataset = load_csv(path, quote_currency="USDT", provenance="binance-vision-spot-audited-20261105")
    if dataset.sha256 != manifest["csv_sha256"]:
        raise ValueError(f"{symbol} curated file changed during verification")
    return dataset, len(manifest["source_archives"])


def _windows(n: int, study: Study):
    protocol = study.registry["protocol"]
    development = n * protocol["development_pct"] // 100
    validation = n * (protocol["development_pct"] + protocol["validation_pct"]) // 100
    embargo = protocol["embargo_hours"]
    partitions = {
        "development": (study.parameters.warmup_hours + 1, development),
        "validation": (development + embargo, validation),
        "test_unsealed": (validation + embargo, n),
    }
    minimum = protocol["minimum_final_fold_hours"]
    if any(hi - lo < minimum for lo, hi in partitions.values()):
        raise ValueError("Insufficient contiguous history after warm-up and embargo")
    step = protocol["walk_forward_step_hours"]
    folds = [(edge + embargo, min(edge + step, n)) for edge in range(development, n, step)]
    return partitions, [(lo, hi) for lo, hi in folds if hi - lo >= minimum]


def _times(bars, start: int, end: int) -> dict:
    return {"start_utc": bars[start].time.isoformat(),
            "end_exclusive_utc": (bars[end - 1].time + timedelta(hours=1)).isoformat(),
            "hours": end - start}


def _verify_benchmark(bars, targets, start, end, kwargs, result, name):
    original = replay(bars, targets, start, end, passive=name == "passive_hold",
                      starting_balance=kwargs["capital"], max_allocation=kwargs["allocation"],
                      costs=kwargs["costs"])
    got = result.metrics
    if (result.nav[-1] != Decimal(original.final_liquidatable_value)
            or Decimal(got["modelled_fees_usdt"]) != Decimal(original.total_modelled_fees)
            or got["modelled_fills"] != original.executed_orders
            or got["closed_trades"] != original.closed_trades):
        raise ValueError(f"Replay differs from the frozen {name} comparator")


def _scenario(bars, targets, start, end, study, costs):
    kwargs = {"capital": study.capital, "allocation": study.allocation, "costs": costs}
    results = {"candidate": replay_window(bars, targets["candidate"], start, end, risk=study.risk, **kwargs)}
    for name in COMPARATORS:
        result = replay_window(bars, targets[name], start, end, **kwargs)
        if name != "flat":
            _verify_benchmark(bars, targets[name], start, end, kwargs, result, name)
        results[name] = result
    return results


def _after_overhead(nav, capital, annual, hours):
    expense = Decimal(annual) * hours / HOURS_YEAR
    return {
        "modelled_overhead_usdt": str(expense),
        "net_pnl_usdt": str(nav - capital - expense),
        "net_return_pct": float((nav - capital - expense) / capital * 100),
    }


def _sensitivity(results, study, hours):
    annual = study.registry["costs"]["annual_candidate_overhead_usdt"]
    return {cost: _after_overhead(results.nav[-1], study.capital, cost, hours) for cost in annual}


def _compare(results, after_expenses):
    return {name: after_expenses - results[name].metrics["net_execution_return_pct"]
            for name in COMPARATORS}


def _screen(test, folds, study):
    rule = study.registry["rejection"]
    main = test["base_friction"]["candidate"]
    stress = test["double_friction"]["candidate"]
    failures = []
    if test["base_friction"]["candidate_after_primary_overhead_pct"] <= 0:
        failures.append("NON_POSITIVE_AFTER_BASE_COSTS_AND_OVERHEAD")
    if test["double_friction"]["candidate_after_primary_overhead_pct"] <= 0:
        failures.append("NON_POSITIVE_AFTER_DOUBLE_COSTS_AND_OVERHEAD")
    for name, excess in test["base_friction"]["excess_vs_benchmarks_pp"].items():
        if excess <= 0:
            failures.append(f"DID_NOT_BEAT_{name.upper()}")
    if max(main["max_drawdown_pct"], stress["max_drawdown_pct"]) >= float(study.risk.drawdown * 100):
        failures.append("DRAWDOWN_LIMIT_REACHED")
    positives = sum(fold["candidate_after_primary_overhead_pct"] > 0 for fold in folds)
    if Decimal(positives) / len(folds) < Decimal(rule["minimum_positive_walk_forward_fraction"]):
        failures.append("TOO_FEW_POSITIVE_WALK_FORWARD_FOLDS")
    return {
        "decision": "FAIL" if failures else "INSUFFICIENT EVIDENCE",
        "historical_rejections": failures,
        "closed_trade_minimum_met": main["closed_trades"] >= rule["minimum_closed_trades_per_market"],
        "positive_walk_forward_folds": positives,
        "walk_forward_folds": len(folds),
        "prospective_validation_complete": False,
    }


def evaluate_market(dataset, study: Study) -> dict:
    """Replay already checked hourly data. The public runner also binds source digests."""
    if dataset.interval_minutes != 60 or dataset.quote_currency != "USDT":
        raise ValueError("Hourly USDT candles required")
    bars = dataset.bars
    partitions, folds = _windows(len(bars), study)
    hour = timedelta(hours=1)
    if (any(bar.time.utcoffset() != timedelta(0)
            or bar.time.minute or bar.time.second or bar.time.microsecond for bar in bars)
            or any(current.time - prior.time != hour for prior, current in zip(bars, bars[1:]))):
        raise ValueError("Candles must form a complete, ordered UTC hourly grid")
    closes = [bar.close for bar in bars]
    signals = momentum_signals(closes, study.parameters)
    targets = {
        "candidate": [signal.target_long for signal in signals],
        "ema_12_48_frozen": ema_signal(closes, 12, 48),
        "passive_hold": [True] * len(bars),
        "flat": [False] * len(bars),
    }
    primary = study.registry["costs"]["primary_annual_candidate_overhead_usdt"]
    stress_costs = study.costs.twice()
    periods = {}
    uncertainty = {}
    for label, (start, end) in partitions.items():
        period = _times(bars, start, end)
        for name, costs in (("base_friction", study.costs), ("double_friction", stress_costs)):
            results = _scenario(bars, targets, start, end, study, costs)
            sensitivity = _sensitivity(results["candidate"], study, end - start)
            after = sensitivity[primary]["net_return_pct"]
            period[name] = {
                **{strategy: result.metrics for strategy, result in results.items()},
                "candidate_operating_cost_sensitivity": sensitivity,
                "candidate_after_primary_overhead_pct": after,
                "excess_vs_benchmarks_pp": _compare(results, after),
            }
            if label == "test_unsealed" and name == "base_friction":
                conf = study.registry["uncertainty"]
                for benchmark in COMPARATORS:
                    daily = paired_daily_excess_bps(bars[start:end], results["candidate"].nav,
                                                   results[benchmark].nav, study.capital, Decimal(primary))
                    uncertainty[benchmark] = moving_block_lower_bound(
                        daily, block_days=conf["block_days"], minimum_blocks=conf["minimum_blocks"],
                        replicates=conf["replicates"], seed=conf["seed"],
                        family_alpha=float(conf["family_alpha"]), comparisons=conf["primary_comparisons"],
                    )
        half = replay_window(bars, targets["candidate"], start, end, capital=study.capital,
                             allocation=study.allocation, costs=study.costs, risk=study.half_risk)
        period["half_stop_risk_base_friction"] = {
            **half.metrics,
            "candidate_after_primary_overhead_pct": _after_overhead(
                half.nav[-1], study.capital, primary, end - start,
            )["net_return_pct"],
        }
        periods[label] = period

    forward = []
    for start, end in folds:
        results = _scenario(bars, targets, start, end, study, study.costs)
        candidate = results["candidate"]
        after = _after_overhead(candidate.nav[-1], study.capital, primary, end - start)["net_return_pct"]
        stressed = replay_window(bars, targets["candidate"], start, end, capital=study.capital,
                                 allocation=study.allocation, costs=stress_costs, risk=study.risk)
        forward.append({
            **_times(bars, start, end),
            "candidate_after_primary_overhead_pct": after,
            "candidate_double_friction_after_primary_overhead_pct": _after_overhead(
                stressed.nav[-1], study.capital, primary, end - start,
            )["net_return_pct"],
            "candidate_max_drawdown_pct": candidate.metrics["max_drawdown_pct"],
            "candidate_closed_trades": candidate.metrics["closed_trades"],
            "excess_vs_benchmarks_pp": _compare(results, after),
        })

    return {
        "periods": periods, "walk_forward": forward, "test_unsealed_descriptive_bootstrap": uncertainty,
        "candidate_targets_sha256": sha256(bytes(targets["candidate"])).hexdigest(),
        "screen": _screen(periods["test_unsealed"], forward, study),
        "frozen_benchmark_parity_verified": True,
    }


def run_study(data_root: Path, output_dir: Path, registry_path: Path) -> str:
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {output_dir}")
    with localcontext(Context(prec=28)):
        study = load_study(registry_path)
        symbols = study.registry["data"]["symbols"]
        datasets = {symbol: load_market(data_root, study, symbol) for symbol in symbols}
        reports = {}
        for symbol, (dataset, archive_months) in datasets.items():
            reports[symbol] = {
                "instrument": symbol,
                "quote_currency": "USDT",
                "registry_sha256": REGISTRY_SHA256,
                "candidate_id": study.registry["candidates"][0]["id"],
                "dataset_sha256": dataset.sha256,
                "source_archive_months": archive_months,
                "candles": len(dataset.bars),
                "evidence_class": study.registry["data"]["evidence_class"],
                "independently_sealed_holdout": False,
                "trading_enabled": False,
                **evaluate_market(dataset, study),
            }
    failed = any(report["screen"]["decision"] == "FAIL" for report in reports.values())
    decision = "FAIL" if failed else "INSUFFICIENT EVIDENCE"
    contents = {
        symbol: json.dumps({**report, "overall_research_decision": decision},
                           sort_keys=True, indent=2, allow_nan=False) + "\n"
        for symbol, report in reports.items()
    }
    # Verify and serialise all results before creating a fresh output directory.
    output_dir.mkdir(parents=True, exist_ok=False)
    created = []
    try:
        for symbol, content in contents.items():
            target = output_dir / f"{symbol}.json"
            with target.open("x", encoding="utf-8") as handle:
                created.append(target)
                handle.write(content)
    except (OSError, KeyboardInterrupt):
        for target in created:
            target.unlink()
        output_dir.rmdir()
        raise
    return decision

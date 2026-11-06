"""Bounded v0.9 research on the pinned historical data. No promotion path."""
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Context, Decimal, localcontext
from hashlib import sha256
import json
from pathlib import Path

from alpha_lab.backtest.costs import CostModel
from alpha_lab.research.multiple_testing import moving_block_lower_bound, paired_daily_excess_bps
from alpha_lab.research.spot_evidence import ledger_hash, nav_risk, overhead_net, performance
from alpha_lab.research.spot_portfolio import ReplayRules, replay_portfolio
from alpha_lab.research.strategies.momentum import ema_signal
from alpha_lab.research.strategies.regime_trend import momentum_signals
from alpha_lab.research.strategies.registered_spot import Decision, strategy_signals, timeframes
from alpha_lab.research.strategy_v08 import _times, load_market, load_study
from alpha_lab.research.strategy_v08_replay import ZERO, replay_window

REGISTRATION_COMMIT = "2d082f2500bf29a31b76e3598735e02464637881"
REGISTRY_SHA256 = "f93bbc00d9bedf7880bc2b51820a71820c18ee879e5d7d1263a7e6f71c6568c5"
HOUR = timedelta(hours=1)
MATCHES = ("exposure_matched_passive", "risk_matched_passive")


def load_registry(path):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != REGISTRY_SHA256:
        raise ValueError("Registry differs from the frozen v0.9 experiment")
    return json.loads(raw)


def evaluation_windows(bars, protocol):
    first = datetime.fromisoformat(protocol["first_open_utc"])
    last = datetime.fromisoformat(protocol["end_exclusive_utc"])
    if bars[0].time != first or bars[-1].time + HOUR != last or (last - first) // HOUR != len(bars):
        raise ValueError("Hour grid does not match the registered history")

    def index(key):
        return (datetime.fromisoformat(protocol[key]) - first) // HOUR

    start = index("development_start_utc")
    dev_end = index("development_end_utc")
    val_end = index("validation_end_utc")
    end = len(bars)
    gap = protocol["embargo_hours"]
    step = protocol["forward_step_hours"]
    periods = {"development": (start, dev_end), "validation": (dev_end + gap, val_end),
               "test_unsealed": (val_end + gap, end)}
    folds = [(edge + gap, min(edge + step, end)) for edge in range(dev_end, end, step)
             if min(edge + step, end) - edge - gap >= protocol["minimum_forward_hours"]]
    return periods, folds


def targeted(wants, distance=ZERO):
    yes, no = Decision(True, False, distance), Decision(False, True, ZERO)
    return tuple(yes if want else no for want in wants)


def make_benchmark_signals(markets, regimes, legacy):
    return {
        "flat": {s: (None,) * len(bars) for s, bars in markets.items()},
        "buy_and_hold": {s: (Decision(True, False, ZERO),) * len(bars) for s, bars in markets.items()},
        "ema_12_48_frozen": {s: targeted(ema_signal([bar.close for bar in bars], 12, 48))
                             for s, bars in markets.items()},
        "rejected_v08": {s: targeted([signal.target_long for signal in regimes[s]], legacy.risk.stop_distance)
                         for s in markets},
    }


def make_benchmarks(markets, regimes, start, end, rules, costs, legacy, signals, audit):
    reports = {}
    baseline_rules = ReplayRules(rules.capital, legacy.allocation / len(markets))
    flat = replay_portfolio(markets, signals["flat"], start, end, baseline_rules, costs)
    reports["flat"] = performance(markets, flat, end)
    for name in ("buy_and_hold", "ema_12_48_frozen"):
        state = replay_portfolio(markets, signals[name], start, end, baseline_rules, costs)
        if len(markets) == 1:
            symbol, = markets
            legacy_state = replay_window(markets[symbol], [signal.enter for signal in signals[name][symbol]],
                                         start, end, capital=rules.capital, allocation=legacy.allocation, costs=costs)
            if (abs(state.nav[-1] - legacy_state.nav[-1]) > Decimal("1e-18")
                    or len(state.fills) != len(legacy_state.orders)):
                raise ValueError(f"Changed frozen standalone comparator: {symbol}/{name}")
        reports[name] = performance(markets, state, end)
    if len(markets) == 1:
        symbol, = markets
        old = replay_window(markets[symbol], [signal.target_long for signal in regimes[symbol]], start, end,
                            capital=rules.capital, allocation=legacy.allocation, costs=costs, risk=legacy.risk)
        old_nav, reports["rejected_v08"] = old.nav, old.metrics
    else:
        old_rules = ReplayRules(rules.capital, legacy.allocation, legacy.risk, close_triggered_stop=True)
        old = replay_portfolio(markets, signals["rejected_v08"], start, end, old_rules, costs)
        if audit:
            audit.replay(markets, signals["rejected_v08"], start, end, old_rules, costs, old)
        old_nav, reports["rejected_v08"] = old.nav, performance(markets, old, end, regimes)
    full = replay_portfolio(markets, signals["buy_and_hold"], start, end,
                            replace(baseline_rules, allocation_per_market=Decimal(1) / len(markets)), costs)
    return reports, flat, full, old_nav


def match_passives(markets, candidate, start, end, costs, full, flat, signal):
    capital = candidate.rules.capital
    target_exposure = sum(candidate.notional) / len(candidate.notional) / capital
    full_exposure = sum(full.notional) / len(full.notional) / capital
    target_risk, full_risk = nav_risk(candidate.nav, capital), nav_risk(full.nav, capital)
    matches = {}
    for name, target, reference in zip(MATCHES, (target_exposure, target_risk), (full_exposure, full_risk), strict=True):
        weight = target / reference if reference else (ZERO if not target else None)
        if weight is None or weight > 1:
            matches[name] = (None, {"status": "CASH_MATCH_UNAVAILABLE", "target": float(target)})
            continue
        state = (replay_portfolio(markets, signal, start, end, ReplayRules(capital, weight / len(markets)), costs)
                 if weight else flat)
        achieved = (sum(state.notional) / len(state.notional) / capital if name == MATCHES[0]
                    else nav_risk(state.nav, capital))
        if abs(achieved - target) > Decimal("1e-18"):
            raise ValueError(f"Passive benchmark did not match {name}")
        matches[name] = (state, {"status": "MATCHED_RETROSPECTIVE", "target": float(target),
                                 "achieved": float(achieved), "initial_total_weight": float(weight),
                                 **performance(markets, state, end)})
    return matches


def cost_case(markets, signals, regimes, start, end, rules, costs, annuals, audit, with_metrics=True):
    state = replay_portfolio(markets, signals, start, end, rules, costs)
    if audit:
        audit.replay(markets, signals, start, end, rules, costs, state)
    capital = rules.capital
    result = {"overhead_sensitivity": {annual: overhead_net(state.nav[-1], capital, annual, end - start)
                                       for annual in annuals}}
    if with_metrics:
        result.update(performance(markets, state, end, regimes))
    else:
        result.update(closed_trades=len(state.closed), max_drawdown_pct=float(state.max_drawdown * 100),
                      nav_ledger_sha256=ledger_hash(state.nav))
    return result, state


def reject(final, forward, cfg, primary, portfolio, limit):
    gate = cfg["rejection"]
    base, stress = final["base"], final["double"]
    returns = [case["overhead_sensitivity"][primary]["net_return_pct"] for case in (base, stress)]
    failures = [f"NON_POSITIVE_{name}_NET" for name, score in zip(("BASE", "DOUBLE"), returns, strict=True) if score <= 0]
    for comparator, excess in base["excess_vs_benchmarks_pp"].items():
        if comparator in ("flat", "rejected_v08", *MATCHES) and excess is not None and excess <= 0:
            failures.append(f"DID_NOT_BEAT_{comparator.upper()}")
    if base["profit_factor"] is not None and base["profit_factor"] <= float(gate["minimum_profit_factor_exclusive"]):
        failures.append("PROFIT_FACTOR_AT_OR_BELOW_THRESHOLD")
    if base["expectancy_usdt_per_closed_trade"] is not None and base["expectancy_usdt_per_closed_trade"] <= 0:
        failures.append("NON_POSITIVE_CLOSED_TRADE_EXPECTANCY")
    if max(base["max_drawdown_pct"], stress["max_drawdown_pct"]) >= float(limit * 100):
        failures.append("PORTFOLIO_DRAWDOWN_THRESHOLD")
    positives = sum(fold["base"]["overhead_sensitivity"][primary]["net_return_pct"] > 0 for fold in forward)
    if Decimal(positives) / len(forward) <= Decimal(gate["minimum_positive_fold_fraction_exclusive"]):
        failures.append("TOO_FEW_POSITIVE_FOLDS")
    min_trades = gate["minimum_closed_trades_portfolio" if portfolio else "minimum_closed_trades_single"]
    return {
        "decision": "FAIL" if failures else "INSUFFICIENT EVIDENCE", "failed_gates": failures,
        "trade_count_minimum": min_trades, "trade_count_met": base["closed_trades"] >= min_trades,
        "positive_forward_folds": positives, "forward_folds": len(forward),
        "unavailable_matched_comparisons": [name for name in MATCHES if base["excess_vs_benchmarks_pp"][name] is None],
    }


def evaluate_scope(markets, signals, regimes, bars, params, rules, cfg, periods, folds, models, benchmarks,
                   passive_signal, audit):
    annuals = cfg["costs"]["annual_candidate_overhead_usdt"]
    primary = cfg["costs"]["primary_annual_overhead_usdt"]
    uncertainty = cfg["uncertainty"]
    bounds, partition_results = {}, {}
    for name, (start, end) in periods.items():
        result = _times(bars, start, end)
        for case, costs in models.items():
            case_rules = (replace(rules, signal_delay_hours=cfg["costs"]["extra_signal_latency_hours"])
                          if case == "lagged_signal" else rules)
            metrics, state = cost_case(markets, signals, regimes, start, end, case_rules, costs, annuals, audit)
            result[case] = metrics
            if case == "lagged_signal":
                continue
            reports, flat, full, old_nav = benchmarks[name, case]
            matches = match_passives(markets, state, start, end, costs, full, flat, passive_signal)
            metrics["matched_passives"] = {label: matched for label, (_, matched) in matches.items()}
            net = metrics["overhead_sensitivity"][primary]["net_return_pct"]
            benchmark_returns = {label: report["net_execution_return_pct"] for label, report in reports.items()}
            benchmark_returns["rejected_v08"] = overhead_net(old_nav[-1], rules.capital, primary, end - start)["net_return_pct"]
            benchmark_returns.update({label: matched.get("net_execution_return_pct") for label, (_, matched) in matches.items()})
            metrics["excess_vs_benchmarks_pp"] = {label: net - value if value is not None else None
                                                   for label, value in benchmark_returns.items()}
            if name == "test_unsealed" and case == "base":
                for label, bench in (("flat", flat), (MATCHES[0], matches[MATCHES[0]][0])):
                    if bench is None:
                        bounds[label] = None
                        continue
                    daily = paired_daily_excess_bps(bars[start:end], state.nav, bench.nav, rules.capital, Decimal(primary))
                    bounds[label] = moving_block_lower_bound(
                        daily, block_days=uncertainty["block_days"], minimum_blocks=uncertainty["minimum_blocks"],
                        replicates=uncertainty["replicates"], seed=uncertainty["seed"],
                        family_alpha=float(uncertainty["family_alpha"]), comparisons=uncertainty["comparisons"],
                    )
        partition_results[name] = result
    forward = []
    for start, end in folds:
        results = _times(bars, start, end)
        for case in ("base", "double"):
            results[case], _ = cost_case(markets, signals, regimes, start, end, rules, models[case], [primary], audit,
                                         with_metrics=False)
        forward.append(results)
    return {
        "variant": params["id"], "role": params["role"], "periods": partition_results, "forward": forward,
        "descriptive_final_bootstrap": bounds,
        "historical_screen": reject(partition_results["test_unsealed"], forward, cfg, primary,
                                    len(markets) > 1, rules.limits.drawdown),
    }


def _encode(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def evaluate(data_root, root, audit):
    cfg = load_registry(root / "configs/strategy-v0.9.json")
    legacy = load_study(root / "configs/strategy-v0.8.json")
    all_markets, manifests, regimes = {}, {}, {}
    for symbol, digest in cfg["data"]["sha256_by_symbol"].items():
        dataset, archive_count = load_market(data_root, legacy, symbol)
        if dataset.sha256 != digest or len(dataset.bars) != cfg["data"]["bars_per_market"]:
            raise ValueError(f"Unregistered history for {symbol}")
        manifest = data_root / "curated" / "binance-vision" / f"{symbol}-1h-2023-04_to_2025-12.manifest.json"
        manifests[symbol] = {"csv_sha256": digest, "manifest_sha256": sha256(manifest.read_bytes()).hexdigest(),
                             "verified_source_archives": archive_count, "hourly_bars": len(dataset.bars)}
        all_markets[symbol] = dataset.bars
        regimes[symbol] = momentum_signals([bar.close for bar in dataset.bars], legacy.parameters)
    bars = next(iter(all_markets.values()))
    if any(any(row.time != reference.time for row, reference in zip(series, bars, strict=True))
           for series in all_markets.values()):
        raise ValueError("Different market hour grids")
    periods, folds = evaluation_windows(bars, cfg["protocol"])
    frames = {symbol: timeframes(series) for symbol, series in all_markets.items()}
    settings = cfg["costs"]
    base = CostModel(Decimal(settings["fee_bps_each_side"]), Decimal(settings["price_concession_bps_each_side"]))
    if settings["friction_stress_multiplier"] != 2:
        raise ValueError("Unexpected friction stress")
    models = {"base": base, "double": base.twice(), "lagged_signal": base}
    base_rules = ReplayRules(Decimal(settings["capital_usdt_per_scope"]), Decimal(cfg["risk"]["max_new_position_fraction"]),
                             legacy.risk)
    for key, val in (("max_position_stop_risk_fraction", legacy.risk.position_stop_risk),
                     ("max_aggregate_stop_risk_fraction", legacy.risk.aggregate_stop_risk),
                     ("daily_loss_suspension_fraction", legacy.risk.daily_loss),
                     ("drawdown_suspension_fraction", legacy.risk.drawdown)):
        if Decimal(cfg["risk"][key]) != val:
            raise ValueError(f"Legacy safety limit differs from registration: {key}")
    if Decimal(cfg["benchmarks"]["initial_risky_allocation"]) != legacy.allocation:
        raise ValueError("Legacy comparator allocation differs from registration")
    all_signals = {}
    prefix_length = len(bars) // 2 + 17
    prefixes = {symbol: timeframes(series[:prefix_length]) for symbol, series in all_markets.items()}
    for params in cfg["candidates"]:
        trial = params["id"]
        all_signals[trial] = {symbol: strategy_signals(tf, len(bars), params, cfg["signals"])
                              for symbol, tf in frames.items()}
        for symbol, stream in all_signals[trial].items():
            if stream[:prefix_length] != strategy_signals(prefixes[symbol], prefix_length, params, cfg["signals"]):
                raise ValueError(f"Future bars changed a prior decision: {symbol}/{trial}")
            if audit:
                audit.signals(all_markets[symbol], params, cfg["signals"], stream)
    if len(all_signals) != cfg["candidate_budget"] or cfg["uncertainty"]["comparisons"] != len(all_signals) * 8:
        raise ValueError("Unregistered trial or multiplicity budget")

    records, decisions = {}, {}
    scopes = {s: {s: series} for s, series in all_markets.items()}
    scopes["portfolio"] = all_markets
    for scope, markets in scopes.items():
        benchmark_signals = make_benchmark_signals(markets, regimes, legacy)
        benchmarks = {(period, case): make_benchmarks(markets, regimes, start, end, base_rules, models[case], legacy,
                                                       benchmark_signals, audit)
                      for period, (start, end) in periods.items() for case in ("base", "double")}
        records[f"{scope}-benchmarks.json"] = {
            period: {**_times(bars, *bounds), **{case: benchmarks[period, case][0] for case in ("base", "double")}}
            for period, bounds in periods.items()
        }
        for params in cfg["candidates"]:
            trial = params["id"]
            rules = replace(base_rules, cooldown_hours=params["signal_hours"],
                            maximum_holding_hours=params.get("maximum_holding_hours"))
            signals = {symbol: all_signals[trial][symbol] for symbol in markets}
            record = evaluate_scope(markets, signals, regimes, bars, params, rules, cfg, periods, folds, models,
                                    benchmarks, benchmark_signals["buy_and_hold"], audit)
            record.update(scope=scope, registry_sha256=REGISTRY_SHA256,
                          dataset_sha256={symbol: manifests[symbol]["csv_sha256"] for symbol in markets})
            records[f"{scope}-{trial}.json"] = record
            decisions.setdefault(trial, {})[scope] = record["historical_screen"]["decision"]
    for params in cfg["candidates"]:
        outcome = decisions[params["id"]]
        outcome["programme_decision"] = "FAIL" if "FAIL" in outcome.values() else "INSUFFICIENT EVIDENCE"
        outcome["role"] = params["role"]
    return records, manifests, decisions


def run_study(data_root: Path, output: Path, root: Path, audit=None):
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    with localcontext(Context(prec=28)):
        records, manifests, decisions = evaluate(data_root, root, audit)
    files = {name: _encode(report) for name, report in records.items()}
    package = root / "packages/alpha_lab/src/alpha_lab"
    code_paths = [root / "scripts/strategy_v09.py"] + [package / name for name in (
        "research/strategy_v09.py", "research/spot_evidence.py", "research/spot_portfolio.py",
        "research/spot_reference.py", "research/strategies/registered_spot.py", "research/strategy_v08.py",
        "research/strategy_v08_replay.py", "research/multiple_testing.py", "research/strategies/regime_trend.py",
        "research/strategies/momentum.py", "research/long_history.py", "backtest/costs.py",
        "data/adapters/binance_archive.py", "data/csv_import.py", "risk/policy.py",
    )]
    index = {
        "schema": "alpha-labs.strategy-research.v0.9.evidence", "registration_commit": REGISTRATION_COMMIT,
        "registry_sha256": REGISTRY_SHA256, "v08_dependency_commit": load_registry(root / "configs/strategy-v0.9.json")["v08_dependency_commit"],
        "evidence_class": "previously_examined_historical_research", "markets": manifests, "decisions": decisions,
        "prospective_evaluation": "NOT_STARTED", "trading_authorised": False,
        "prefix_signal_checks": len(decisions) * len(manifests),
        "independent_replay": audit.summary() if audit else None,
        "implementation_sha256": {str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest() for path in code_paths},
        "report_sha256": {name: sha256(raw).hexdigest() for name, raw in files.items()},
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        (output / name).write_bytes(raw)
    (output / "index.json").write_bytes(_encode(index))
    return decisions

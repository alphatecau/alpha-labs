"""Supplementary cost and strategy diagnostics. No promotion or execution path."""
from collections import Counter
from dataclasses import replace
from decimal import Context, Decimal, localcontext
from hashlib import sha256
from itertools import accumulate, combinations
import json
from pathlib import Path
from statistics import StatisticsError, correlation, mean

from alpha_lab.backtest.costs import CostModel
from alpha_lab.research.spot_evidence import overhead_net
from alpha_lab.research.spot_followup_signals import SIGNAL_HOURS, rotation_signals, trend_observations
from alpha_lab.research.spot_portfolio import ReplayRules
from alpha_lab.research.spot_reference import ReferenceAudit
from alpha_lab.research.strategies.regime_trend import momentum_signals
from alpha_lab.research.strategies.registered_spot import aggregate, strategy_signals, timeframes
from alpha_lab.research.strategy_v08 import _times, load_market, load_study
from alpha_lab.research.strategy_v09 import (
    MATCHES, REGISTRY_SHA256, cost_case, evaluation_windows, load_registry, make_benchmark_signals,
    make_benchmarks, match_passives,
)

ROUND_TRIP_BPS = (20, 40, 60, 80)
VARIANTS = ("trend_hysteresis", "relative_strength_rotation")


def cost_scenarios(fee_bps):
    return {bps: CostModel(fee_bps, Decimal(bps) / 2 - fee_bps) for bps in ROUND_TRIP_BPS}


def drawdown_duration(nav, capital):
    peak, length, longest = capital, 0, 0
    for value in nav:
        if value >= peak:
            peak, length = value, 0
        else:
            length += 1
            longest = max(longest, length)
    return longest


def cost_grid(markets, regimes, cfg, periods, folds, rules, models, annual, audit):
    start, end = periods["test_unsealed"]
    frames = {symbol: timeframes(bars) for symbol, bars in markets.items()}
    result = {}
    for trial in cfg["candidates"]:
        trial_rules = replace(rules, cooldown_hours=trial["signal_hours"],
                              maximum_holding_hours=trial.get("maximum_holding_hours"))
        signals = {symbol: strategy_signals(frames[symbol], len(bars), trial, cfg["signals"])
                   for symbol, bars in markets.items()}
        scopes = {symbol: {symbol: bars} for symbol, bars in markets.items()} | {"portfolio": markets}
        results = result[trial["id"]] = {}
        for scope, series in scopes.items():
            events = {symbol: signals[symbol] for symbol in series}
            scores = results[scope] = {}
            for bps, model in models.items():
                metrics, state = cost_case(series, events, regimes, start, end, trial_rules, model, [annual], audit)
                metrics["max_drawdown_duration_close_hours"] = drawdown_duration(state.nav, rules.capital)
                fold_results = [cost_case(series, events, regimes, lo, hi, trial_rules, model, [annual], audit,
                                          with_metrics=False)[0]["overhead_sensitivity"][annual]["net_return_pct"]
                                for lo, hi in folds]
                scores[bps] = {"test_unsealed": metrics, "forward_fold_net_returns_pct": fold_results,
                               "positive_forward_folds": sum(value > 0 for value in fold_results)}
    return result


def regime_diagnostics(markets, observations, start, end):
    daily_returns, results = {}, {}
    for symbol, bars in markets.items():
        closes = [bar.close for _, bar in aggregate(bars[start:end], 24)]
        daily_returns[symbol] = [float(now / prior - 1) for prior, now in zip(closes, closes[1:])]
        states, signals, all_moves, short_moves = Counter(), Counter(), [], []
        for index in range(start - 1, end - SIGNAL_HOURS - 1):
            point = observations[symbol][index]
            if point is None:
                continue
            states[point.regime.value] += 1
            direction = "LONG" if point.long.enter else "SHORT" if point.short_signal else "FLAT"
            signals[direction] += 1
            move = bars[index + SIGNAL_HOURS + 1].open / bars[index + 1].open - 1
            all_moves.append(move)
            if point.short_signal:
                short_moves.append(move)
        results[symbol] = {
            "regime_counts": dict(states), "entry_signal_counts": dict(signals),
            "mean_next_4h_open_return_bps_all": float(mean(all_moves) * 10_000) if all_moves else None,
            "mean_next_4h_open_return_bps_after_short_signal": float(mean(short_moves) * 10_000) if short_moves else None,
            "fraction_negative_after_short_signal": (sum(value < 0 for value in short_moves) / len(short_moves)
                                                     if short_moves else None),
        }
    correlations = {}
    for left, right in combinations(markets, 2):
        try:
            correlations[f"{left}/{right}"] = correlation(daily_returns[left], daily_returns[right])
        except StatisticsError:
            correlations[f"{left}/{right}"] = None
    return {"markets": results, "daily_return_correlations": correlations, "spot_short_execution": "UNSUPPORTED"}


def exploratory_study(markets, periods, folds, legacy, rules, models, annual, audit):
    # The former final partition is excluded before any exploratory feature work.
    end = periods["validation"][1]
    markets = {symbol: bars[:end] for symbol, bars in markets.items()}
    regimes, observations = {}, {}
    prefix_checks = 0
    cut = periods["validation"][0] + 17
    for symbol, bars in markets.items():
        parameters = legacy.parameters
        regimes[symbol] = momentum_signals([bar.close for bar in bars], parameters)
        observations[symbol] = trend_observations(bars, regimes[symbol], parameters, legacy.risk.stop_distance)
        prefix_regimes = momentum_signals([bar.close for bar in bars[:cut]], parameters)
        prefix = trend_observations(bars[:cut], prefix_regimes, parameters, legacy.risk.stop_distance)
        if observations[symbol][:cut] != prefix:
            raise ValueError(f"Future bars changed an exploratory signal for {symbol}")
        prefix_checks += 1
    signals = {
        VARIANTS[0]: {symbol: tuple(point.long if point else None for point in stream)
                      for symbol, stream in observations.items()},
        VARIANTS[1]: rotation_signals(observations),
    }
    rules = replace(rules, cooldown_hours=SIGNAL_HOURS)
    bars = next(iter(markets.values()))
    benchmarks = make_benchmark_signals(markets, regimes, legacy)
    results, diagnostics = {variant: {} for variant in VARIANTS}, {}
    for period in ("development", "validation"):
        start, end = periods[period]
        diagnostics[period] = {**_times(bars, start, end), **regime_diagnostics(markets, observations, start, end)}
        reports, flat, full, old = make_benchmarks(markets, regimes, start, end, rules, models[40], legacy,
                                                   benchmarks, audit)
        for variant, events in signals.items():
            scores = {"window": _times(bars, start, end), "cases": {}}
            for bps, model in models.items():
                metrics, state = cost_case(markets, events, regimes, start, end, rules, model, [annual], audit)
                metrics["max_drawdown_duration_close_hours"] = drawdown_duration(state.nav, rules.capital)
                position_count = accumulate(1 if fill.side == "BUY" else -1 for fill in state.fills)
                metrics["maximum_concurrent_positions"] = max(position_count, default=0)
                scores["cases"][bps] = metrics
                if bps == 40:
                    matches = match_passives(markets, state, start, end, model, full, flat, benchmarks["buy_and_hold"])
                    comparators = {name: reports[name]["net_execution_return_pct"]
                                   for name in ("flat", "buy_and_hold", "ema_12_48_frozen")}
                    comparators["rejected_v08"] = overhead_net(old[-1], rules.capital, annual, end - start)["net_return_pct"]
                    comparators.update({name: match.get("net_execution_return_pct") for name, (_, match) in matches.items()})
                    scores["comparators_40_bps_net_pct"] = comparators
            results[variant][period] = scores
    for variant, events in signals.items():
        scores = results[variant]
        scores["forward_folds_40_bps"] = []
        for start, end in folds:
            if end > periods["validation"][1]:
                break
            metrics, _ = cost_case(markets, events, regimes, start, end, rules, models[40], [annual], audit,
                                   with_metrics=False)
            scores["forward_folds_40_bps"].append({**_times(bars, start, end), **metrics})
        scores["screen"] = exploratory_screen(scores, annual, rules.limits.drawdown)
    return {"results": results, "regime_and_cross_asset_diagnostics": diagnostics, "signal_prefix_checks": prefix_checks}


def exploratory_screen(scores, annual, drawdown_limit):
    development, validation = (scores[period]["cases"][40] for period in ("development", "validation"))
    stress = scores["validation"]["cases"][60]
    net = validation["overhead_sensitivity"][annual]["net_return_pct"]
    matches = scores["validation"]["comparators_40_bps_net_pct"]
    failures = []
    if min(net, development["overhead_sensitivity"][annual]["net_return_pct"],
           stress["overhead_sensitivity"][annual]["net_return_pct"]) <= 0:
        failures.append("NON_POSITIVE_NET")
    if any(matches[name] is not None and net <= matches[name] for name in MATCHES):
        failures.append("TRAILS_MATCHED_PASSIVE")
    if max(validation["max_drawdown_pct"], stress["max_drawdown_pct"]) >= float(drawdown_limit * 100):
        failures.append("DRAWDOWN_LIMIT_REACHED")
    return {"outcome": "FAIL" if failures else "INCONCLUSIVE", "failed_checks": failures,
            "validation_closed_trades": validation["closed_trades"],
            "validation_trade_minimum_met": validation["closed_trades"] >= 40,
            "unavailable_matched_comparisons": [name for name in MATCHES if matches[name] is None]}


def run_followup(data_root: Path, output: Path, root: Path):
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    cfg = load_registry(root / "configs/strategy-v0.9.json")
    legacy = load_study(root / "configs/strategy-v0.8.json")
    audit = ReferenceAudit()
    markets, provenance = {}, {}
    with localcontext(Context(prec=28)):
        for symbol, digest in cfg["data"]["sha256_by_symbol"].items():
            dataset, archives = load_market(data_root, legacy, symbol)
            if dataset.sha256 != digest or len(dataset.bars) != cfg["data"]["bars_per_market"]:
                raise ValueError(f"Unregistered history for {symbol}")
            markets[symbol] = dataset.bars
            provenance[symbol] = {"csv_sha256": digest, "verified_archives": archives, "bars": len(dataset.bars)}
        bars = next(iter(markets.values()))
        periods, folds = evaluation_windows(bars, cfg["protocol"])
        regimes = {symbol: momentum_signals([bar.close for bar in rows], legacy.parameters)
                   for symbol, rows in markets.items()}
        settings = cfg["costs"]
        annual = settings["primary_annual_overhead_usdt"]
        models = cost_scenarios(Decimal(settings["fee_bps_each_side"]))
        rules = ReplayRules(Decimal(settings["capital_usdt_per_scope"]),
                            Decimal(cfg["risk"]["max_new_position_fraction"]), legacy.risk)
        grid = cost_grid(markets, regimes, cfg, periods, folds, rules, models, annual, audit)
        cost_audit = audit.summary()
        exploratory_audit = ReferenceAudit()
        exploratory = exploratory_study(markets, periods, folds, legacy, rules, models, annual, exploratory_audit)
    protocol = root / "docs/30_STRATEGY_V09_FOLLOWUP_PROTOCOL.md"
    report = {
        "schema": "alpha-labs.strategy-research.v0.9.followup", "evidence_class": cfg["data"]["evidence_class"],
        "registration_sha256": REGISTRY_SHA256, "followup_protocol_sha256": sha256(protocol.read_bytes()).hexdigest(),
        "datasets": provenance, "historical_windows": {name: _times(bars, *bounds) for name, bounds in periods.items()},
        "forward_windows": [_times(bars, *bounds) for bounds in folds], "annual_overhead_usdt": annual,
        "cost_cases_bps_per_side": {bps: {"fee": str(model.fee_bps), "concession": str(model.adverse_slippage_bps)}
                                    for bps, model in models.items()},
        "frozen_trial_cost_grid": grid, "exploratory": exploratory,
        "independent_replay": {"cost_grid": cost_audit, "exploratory": exploratory_audit.summary()},
        "prospective_evaluation": "UNVERIFIED", "trading_authorised": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as file:
        json.dump(report, file, sort_keys=True, separators=(",", ":"), allow_nan=False)
        file.write("\n")
    return report

#!/usr/bin/env python3
"""Independently recompute v0.8 signals and ledgers from the pinned curated CSVs.

This verifier imports neither the research strategy nor the Alpha Labs ledger.
It checks numerical reproduction, with market-data provenance handled by the
main runner and by the source-archive audit.
"""
import argparse
import csv
from datetime import datetime, timedelta
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
from statistics import stdev


def ema(values, hours):
    result = [values[0]]
    weight = 2 / (1 + hours)
    for price in values[1:]:
        result.append(result[-1] + weight * (price - result[-1]))
    return result


def targets(closes, params):
    fast = ema(closes, params["fast_hours"])
    slow = ema(closes, params["slow_hours"])
    slope, momentum, vol = (params[name] for name in ("slope_hours", "momentum_hours", "volatility_hours"))
    returns = [0.0] + [now / before - 1 for before, now in zip(closes, closes[1:])]
    ready = max(params["slow_hours"] + slope, momentum, vol)
    hold = [False] * ready
    for i in range(ready, len(closes)):
        hold.append(
            fast[i] / slow[i] - 1 >= float(params["min_trend_spread_fraction"])
            and slow[i] > slow[i - slope]
            and closes[i] / closes[i - momentum] - 1 >= float(params["entry_momentum_fraction"])
            and stdev(returns[i - vol + 1:i + 1]) < float(params["max_hourly_volatility_fraction"])
        )
    return hold


def ledger(candles, desired, lo, hi, capital, allocation, fee, slip, risk=None):
    debit = (1 + fee) * (1 + slip)
    credit = (1 - fee) * (1 - slip)
    cash = nav = peak = day_open = capital
    shares = fees = max_dd = 0.0
    fills = closures = exposure = 0
    day = stop = None
    suspend_day = suspend_window = exit_next = False
    if risk is not None:
        distance, per_trade, aggregate, daily, drawdown = risk
    for i in range(lo, hi):
        time, open_price, close = candles[i]
        if time.date() != day:
            day, day_open, suspend_day = time.date(), nav, False
        want = desired[i - 1]
        if shares and (exit_next or not want):
            cash += shares * open_price * credit
            fees += shares * open_price * (1 - slip) * fee
            shares = 0.0
            fills += 1
            closures += 1
        elif not shares and want and not (suspend_day or suspend_window):
            shares = min(cash, capital * allocation) / (open_price * debit)
            if risk is not None:
                stop = open_price * (1 - distance)
                loss_per_share = open_price * debit - stop * credit
                shares = min(shares, cash * allocation / (open_price * debit),
                             cash * min(per_trade, aggregate) / loss_per_share)
            cash -= shares * open_price * debit
            fees += shares * open_price * (1 + slip) * fee
            fills += 1
        nav = cash + shares * close * credit
        peak = max(peak, nav)
        max_dd = max(max_dd, 1 - nav / peak)
        exposure += bool(shares)
        if risk is not None:
            suspend_day |= 1 - nav / day_open >= daily
            suspend_window |= max_dd >= drawdown
            exit_next = bool(shares and (close <= stop or suspend_day or suspend_window))
    return {
        "final_liquidatable_usdt": nav, "modelled_fees_usdt": fees, "modelled_fills": fills,
        "closed_trades": closures, "exposure_fraction_of_hours": exposure / (hi - lo),
        "max_drawdown_pct": max_dd * 100,
        "net_execution_return_pct": 100 * (nav / capital - 1),
    }


def verify(report, candles, registry):
    n = len(candles)
    param, = registry["candidates"]
    closes = [close for _, _, close in candles]
    signals = targets(closes, param)
    if sha256(bytes(signals)).hexdigest() != report["candidate_targets_sha256"]:
        raise ValueError("Full target stream differs from the reference indicators")
    fast, slow = ema(closes, 12), ema(closes, 48)
    desired = {"candidate": signals, "ema_12_48_frozen": [i >= 48 and a > b for i, (a, b) in enumerate(zip(fast, slow))],
               "passive_hold": [True] * n, "flat": [False] * n}
    protocol = registry["protocol"]
    costs = registry["costs"]
    risk = registry["risk"]
    capital = float(costs["capital_usdt"])
    allocation = float(costs["comparator_allocation_fraction"])
    fee, slip = float(costs["fee_bps_each_side"]) / 10_000, float(costs["adverse_slippage_bps_each_side"]) / 10_000
    risk_config = tuple(float(risk[key]) for key in (
        "stop_distance_fraction", "max_position_stop_risk_fraction", "max_aggregate_stop_risk_fraction",
        "daily_loss_suspension_fraction", "drawdown_suspension_fraction",
    ))
    half = (risk_config[0], float(risk["half_risk_sensitivity_fraction"]), *risk_config[2:])
    t1 = n * protocol["development_pct"] // 100
    t2 = n * (protocol["development_pct"] + protocol["validation_pct"]) // 100
    embargo = protocol["embargo_hours"]
    start = 1 + max(param["slow_hours"] + param["slope_hours"], param["volatility_hours"], param["momentum_hours"])
    intervals = {"development": (start, t1), "validation": (t1 + embargo, t2), "test_unsealed": (t2 + embargo, n)}

    def check(published, expected, label):
        for key, value in expected.items():
            reported = published[key]
            if isinstance(value, int):
                equal = reported == value
            else:
                equal = isclose(float(reported), value, rel_tol=1e-10, abs_tol=1e-8)
            if not equal:
                raise ValueError(f"{label}/{key}: report {reported} differs from reference {value}")

    def after_overhead(metrics, lo, hi, annual):
        return metrics["net_execution_return_pct"] - 100 * float(annual) * (hi - lo) / (365 * 24 * capital)

    primary_cost = costs["primary_annual_candidate_overhead_usdt"]
    checks = 0
    for period, (lo, hi) in intervals.items():
        actual = report["periods"][period]
        if (actual["start_utc"] != candles[lo][0].isoformat()
                or actual["end_exclusive_utc"] != (candles[hi - 1][0] + timedelta(hours=1)).isoformat()
                or actual["hours"] != hi - lo):
            raise ValueError(f"Wrong dates in {period}")
        for scenario, multiple in (("base_friction", 1), ("double_friction", costs["friction_stress_multiplier"])):
            for name, signal in desired.items():
                controls = risk_config if name == "candidate" else None
                expected = ledger(candles, signal, lo, hi, capital, allocation, fee * multiple, slip * multiple, controls)
                check(actual[scenario][name], expected, f"{period}/{scenario}/{name}")
                if name == "candidate":
                    for annual in costs["annual_candidate_overhead_usdt"]:
                        check(actual[scenario]["candidate_operating_cost_sensitivity"][annual],
                              {"net_return_pct": after_overhead(expected, lo, hi, annual)},
                              f"{period}/{scenario}/overhead_{annual}")
                checks += 1
        expected = ledger(candles, signals, lo, hi, capital, allocation, fee, slip, half)
        check(actual["half_stop_risk_base_friction"], expected, f"{period}/half_risk")
        checks += 1

    step = protocol["walk_forward_step_hours"]
    fold_bounds = [(edge + embargo, min(edge + step, n)) for edge in range(t1, n, step)
                   if min(edge + step, n) - edge - embargo >= protocol["minimum_final_fold_hours"]]
    for index, ((lo, hi), fold) in enumerate(zip(fold_bounds, report["walk_forward"], strict=True)):
        if (fold["start_utc"] != candles[lo][0].isoformat()
                or fold["end_exclusive_utc"] != (candles[hi - 1][0] + timedelta(hours=1)).isoformat()
                or fold["hours"] != hi - lo):
            raise ValueError(f"Wrong dates in fold {index}")
        candidate = ledger(candles, signals, lo, hi, capital, allocation, fee, slip, risk_config)
        multiplier = costs["friction_stress_multiplier"]
        stress = ledger(candles, signals, lo, hi, capital, allocation, fee * multiplier, slip * multiplier, risk_config)
        net = after_overhead(candidate, lo, hi, primary_cost)
        check(fold, {"candidate_after_primary_overhead_pct": net,
                     "candidate_double_friction_after_primary_overhead_pct": after_overhead(stress, lo, hi, primary_cost),
                     "candidate_closed_trades": candidate["closed_trades"],
                     "candidate_max_drawdown_pct": candidate["max_drawdown_pct"]}, f"fold {index}")
        for name in ("ema_12_48_frozen", "passive_hold", "flat"):
            benchmark = ledger(candles, desired[name], lo, hi, capital, allocation, fee, slip)
            check(fold["excess_vs_benchmarks_pp"], {name: net - benchmark["net_execution_return_pct"]}, f"fold {index}")
        checks += 5
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("datasets"))
    parser.add_argument("--reports", type=Path, default=Path("datasets/replay/strategy-v0.8"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    registry_bytes = (root / "configs" / "strategy-v0.8.json").read_bytes()
    registry = json.loads(registry_bytes)
    scope = registry["data"]
    for symbol in scope["symbols"]:
        report = json.loads((args.reports / f"{symbol}.json").read_bytes())
        path = args.data_root / "curated" / "binance-vision" / f"{symbol}-1h-{scope['first_month']}_to_{scope['last_month']}.csv"
        if (report["dataset_sha256"] != sha256(path.read_bytes()).hexdigest()
                or report["registry_sha256"] != sha256(registry_bytes).hexdigest()
                or report["instrument"] != symbol):
            raise ValueError(f"{symbol} report does not match supplied registry or CSV")
        with path.open(encoding="utf-8", newline="") as handle:
            candles = [(datetime.fromisoformat(row["timestamp"]), float(row["open"]), float(row["close"]))
                       for row in csv.DictReader(handle)]
        ledgers = verify(report, candles, registry)
        print(f"{symbol}: {len(candles):,} targets, {ledgers} ledgers independently reproduced")


if __name__ == "__main__":
    main()

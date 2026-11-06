#!/usr/bin/env python3
"""Attribute the frozen v0.8 replay. All counterfactuals are retrospective."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Context, Decimal, localcontext
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean, median, stdev

from alpha_lab.backtest.costs import CostModel
from alpha_lab.research.long_history import HOURS_YEAR
from alpha_lab.research.strategies.regime_trend import momentum_signals
from alpha_lab.research.strategy_v08 import REGISTRY_SHA256, _windows, load_market, load_study
from alpha_lab.research.strategy_v08_replay import replay_window


def optional_mean(values):
    return mean(values) if values else None


def trade_rows(bars, signals, result, start, end, costs):
    by_time = {bar.time: i for i, bar in enumerate(bars)}
    entry = None
    for fill in [*result.orders, None]:
        if fill and fill["side"] == "BUY":
            entry = fill
            continue
        if entry is None:
            continue
        lo = by_time[entry["time"]]
        hi = by_time[fill["time"]] if fill else end
        price = bars[lo].open
        exit_price = bars[hi].open if fill else bars[end - 1].close
        held = bars[lo:hi]
        units = entry["quantity"]
        proceeds = fill["cash_delta"] if fill else costs.sell_proceeds(units, exit_price)
        fee = fill["fee"] if fill else units * costs.sell_price(exit_price) * costs.fee_bps / 10_000
        concession = units * (costs.buy_price(price) - price + exit_price - costs.sell_price(exit_price))
        gross = units * (exit_price - price)
        net = proceeds + entry["cash_delta"]
        if abs(gross - entry["fee"] - fee - concession - net) > Decimal("1e-18"):
            raise ValueError("Trade cost attribution does not reconcile")
        next_bar = hi + 24
        trigger = signals[hi - 1]
        reason = fill["reason"] if fill else "ESTIMATED_TERMINAL_LIQUIDATION"
        yield {
            "entry_utc": entry["time"].isoformat(),
            "exit_utc": (fill["time"] if fill else bars[end - 1].time + timedelta(hours=1)).isoformat(),
            "reason": reason, "entry_regime": signals[lo - 1].regime.value,
            "exit_signal_regime": trigger.regime.value,
            "entry_72h_momentum_pct": signals[lo - 1].momentum * 100,
            "entry_hourly_volatility_pct": signals[lo - 1].hourly_volatility * 100,
            "signal_flat_trigger": ("MOMENTUM_BELOW_ENTRY_THRESHOLD" if trigger.regime.value == "TRENDING_UP"
                                    else trigger.regime.value) if reason == "SIGNAL_FLAT" else None,
            "hours_held": hi - lo, "gross_usdt": gross, "fees_usdt": entry["fee"] + fee,
            "price_concession_usdt": concession, "net_usdt": net,
            "entry_open_vs_signal_close_bps": (price / bars[lo - 1].close - 1) * 10_000,
            "exit_open_vs_signal_close_bps": (exit_price / bars[hi - 1].close - 1) * 10_000 if fill else None,
            "mfe_pct": (max(price, exit_price, max(bar.high for bar in held)) / price - 1) * 100,
            "mae_pct": (min(price, exit_price, min(bar.low for bar in held)) / price - 1) * 100,
            "post_exit_24h_return_pct": (bars[next_bar].open / exit_price - 1) * 100
            if fill and next_bar < end else None,
            "exposure_quote_hour_sum": sum(units * bar.close for bar in held),
            "planned_risk_pct": entry["planned_stop_risk_fraction"] * 100,
        }
        entry = None


def trade_summary(rows):
    pnls = [row["net_usdt"] for row in rows]
    wins, losses = [p for p in pnls if p > 0], [-p for p in pnls if p < 0]
    return {
        "trades": len(rows), "gross_usdt": sum(row["gross_usdt"] for row in rows),
        "net_usdt": sum(pnls), "win_rate_pct": 100 * len(wins) / len(rows) if rows else None,
        "payoff_ratio": mean(wins) / mean(losses) if wins and losses else None,
        "profit_factor": sum(wins) / sum(losses) if losses else None,
        "expectancy_usdt": optional_mean(pnls),
        "mean_holding_hours": optional_mean([r["hours_held"] for r in rows]),
        "median_holding_hours": median([r["hours_held"] for r in rows]) if rows else None,
        "mean_mfe_pct": optional_mean([r["mfe_pct"] for r in rows]),
        "mean_mae_pct": optional_mean([r["mae_pct"] for r in rows]),
        "mean_entry_gap_bps": optional_mean([r["entry_open_vs_signal_close_bps"] for r in rows]),
        "mean_exit_gap_bps": optional_mean([r["exit_open_vs_signal_close_bps"] for r in rows]),
        "mean_24h_post_exit_return_pct": optional_mean([r["post_exit_24h_return_pct"] for r in rows
                                                        if r["post_exit_24h_return_pct"] is not None]),
    }


def nav_risk(curve, capital):
    return stdev((new - old) / capital for old, new in zip([capital, *curve], curve))


def matched_passive(bars, start, end, result, exposure, study):
    passive = [True] * len(bars)

    def hold(fraction):
        return replay_window(bars, passive, start, end, capital=study.capital,
                             allocation=fraction, costs=study.costs)

    unit = hold(Decimal(1))
    units = unit.orders[0]["quantity"]
    unit_exposure = mean(units * bar.close / study.capital for bar in bars[start:end])
    unit_risk = nav_risk(unit.nav, study.capital)
    risk = nav_risk(result.nav, study.capital)
    matched = {}
    for key, target, scale in (("mean_notional", exposure, unit_exposure), ("hourly_pnl_stdev", risk, unit_risk)):
        weight = target / scale if scale else Decimal(0)
        matched[key] = {
            "target": target, "passive_initial_weight": weight,
            "net_return_pct": hold(weight).metrics["net_execution_return_pct"] if 0 < weight <= 1 else
            (0.0 if not target else None),
        }
    return matched


def attribute_period(bars, signals, start, end, study):
    targets = [signal.target_long for signal in signals]
    kwargs = {"capital": study.capital, "allocation": study.allocation, "risk": study.risk}
    result = replay_window(bars, targets, start, end, costs=study.costs, **kwargs)
    rows = list(trade_rows(bars, signals, result, start, end, study.costs))
    closed = [row for row in rows if row["reason"] != "ESTIMATED_TERMINAL_LIQUIDATION"]
    grouped = defaultdict(list)
    for row in closed:
        grouped[row["reason"]].append(row)
    overhead = (Decimal(study.registry["costs"]["primary_annual_candidate_overhead_usdt"])
                * (end - start) / HOURS_YEAR)
    gross, fee, slip, net = (sum(row[key] for row in rows) for key in (
        "gross_usdt", "fees_usdt", "price_concession_usdt", "net_usdt",
    ))
    if abs(result.nav[-1] - study.capital - net) > Decimal("1e-18"):
        raise ValueError("Window cost attribution does not reconcile")
    fee_only = CostModel(study.costs.fee_bps, Decimal(0))
    price_only = CostModel(Decimal(0), study.costs.adverse_slippage_bps)
    no_cost = CostModel(Decimal(0), Decimal(0))
    reruns = {name: replay_window(bars, targets, start, end, costs=model, **kwargs).metrics
              for name, model in (("fees_only", fee_only), ("price_concession_only", price_only), ("zero", no_cost))}
    exposure = sum(row["exposure_quote_hour_sum"] for row in rows) / study.capital / (end - start)
    return {
        "gross_fixed_fills_usdt": gross, "fees_including_terminal_usdt": fee,
        "price_concession_including_terminal_usdt": slip, "scenario_overhead_usdt": overhead,
        "net_after_overhead_usdt": net - overhead, "frozen_base_execution_metrics": result.metrics,
        "full_replay_cost_ablations": reruns, "closed_trade_summary": trade_summary(closed),
        "by_exit_reason": {name: trade_summary(group) for name, group in sorted(grouped.items())},
        "by_entry_regime": {name: trade_summary([row for row in closed if row["entry_regime"] == name])
                            for name in sorted({row["entry_regime"] for row in closed})},
        "by_exit_signal_regime": {name: trade_summary([row for row in closed if row["exit_signal_regime"] == name])
                                  for name in sorted({row["exit_signal_regime"] for row in closed})},
        "signal_exit_triggers": dict(Counter(row["signal_flat_trigger"] for row in grouped.get("SIGNAL_FLAT", ()))),
        "signal_exits_reentered_within_24h": sum(
            a["reason"] == "SIGNAL_FLAT" and timedelta(0) <
            datetime.fromisoformat(b["entry_utc"]) - datetime.fromisoformat(a["exit_utc"]) <= timedelta(hours=24)
            for a, b in zip(rows, rows[1:])
        ),
        "mean_open_notional_fraction_initial_equity": exposure,
        "mean_entry_momentum_pct": optional_mean([r["entry_72h_momentum_pct"] for r in rows]),
        "mean_entry_hourly_volatility_pct": optional_mean([r["entry_hourly_volatility_pct"] for r in rows]),
        "matched_passive_diagnostics": matched_passive(bars, start, end, result, exposure, study),
        "trade_ledger_sha256": sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest(),
        "trade_ledger": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-trade-ledgers", action="store_true")
    args = parser.parse_args()
    registry_path = Path(__file__).resolve().parents[1] / "configs" / "strategy-v0.8.json"
    with localcontext(Context(prec=28)):
        study = load_study(registry_path)
        markets = {}
        for symbol in study.registry["data"]["symbols"]:
            dataset, _ = load_market(args.data_root, study, symbol)
            signals = momentum_signals([bar.close for bar in dataset.bars], study.parameters)
            windows, _ = _windows(len(dataset.bars), study)
            periods = {}
            for name, (start, end) in windows.items():
                periods[name] = attribute_period(dataset.bars, signals, start, end, study)
                if not args.include_trade_ledgers:
                    del periods[name]["trade_ledger"]
            markets[symbol] = {"dataset_sha256": dataset.sha256, "periods": periods}
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump({"evidence_class": "retrospective_attribution", "registry_sha256": REGISTRY_SHA256,
                   "markets": markets}, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")


if __name__ == "__main__":
    main()

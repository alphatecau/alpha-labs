"""Metrics and trade accounting for the offline shared-cash replay."""
from collections import Counter, defaultdict
from dataclasses import astuple
from decimal import Decimal
from hashlib import sha256
import json
from math import ceil
from statistics import mean, median, stdev

from alpha_lab.research.long_history import HOURS_YEAR, _risk_stats
from alpha_lab.research.strategy_v08_replay import BPS, ZERO


def ledger_hash(rows):
    return sha256(json.dumps(rows, default=str, separators=(",", ":")).encode()).hexdigest()


def nav_risk(nav, capital):
    return stdev((now - prev) / capital for prev, now in zip([capital, *nav], nav))


def overhead_net(nav, capital, annual, hours):
    expense = Decimal(annual) * hours / HOURS_YEAR
    return {"modelled_overhead_usdt": float(expense), "net_pnl_usdt": float(nav - capital - expense),
            "net_return_pct": float((nav - capital - expense) / capital * 100)}


def performance(markets, state, end, regimes=None):
    capital = state.rules.capital
    costs = state.costs
    gross = fees = slip = turnover = terminal_pnl = ZERO
    volume_share = ZERO
    pnl_by_market = defaultdict(Decimal)
    exit_reasons = Counter()
    for row in state.fills:
        gross += row.quantity * row.reference_price * (1 if row.side == "SELL" else -1)
        fees += row.fee
        slip += row.price_concession
        turnover += abs(row.cash_delta) + (row.fee if row.side == "SELL" else -row.fee)
        volume = markets[row.symbol][row.index].volume
        if volume:
            volume_share = max(volume_share, row.quantity / volume)
        pnl_by_market[row.symbol] += row.cash_delta
        if row.side == "SELL":
            exit_reasons[row.reason] += 1
    for symbol, lot in state.positions.items():
        close = markets[symbol][end - 1].close
        proceeds = costs.sell_proceeds(lot.quantity, close)
        gross += lot.quantity * close
        fees += lot.quantity * costs.sell_price(close) * costs.fee_bps / BPS
        slip += lot.quantity * (close - costs.sell_price(close))
        pnl_by_market[symbol] += proceeds
        terminal_pnl += proceeds - lot.outlay
    net = state.nav[-1] - capital
    pnl = [trade.net_pnl for trade in state.closed]
    if (abs(gross - fees - slip - net) > Decimal("1e-17")
            or abs(sum(pnl, terminal_pnl) - net) > Decimal("1e-17")
            or abs(sum(pnl_by_market.values()) - net) > Decimal("1e-17")):
        raise ValueError("Gross, friction, cash and closed/terminal P&L differ")
    wins = [value for value in pnl if value > 0]
    losses = [-value for value in pnl if value < 0]
    grouped = defaultdict(list)
    if regimes:
        for trade in state.closed:
            grouped[regimes[trade.symbol][trade.entry_index - 1].regime.value].append(trade.net_pnl)
    nav = [float(value) for value in state.nav]
    hours_held = [trade.hours_held for trade in state.closed]
    returns = [now / prev - 1 for prev, now in zip([float(capital), *nav], nav)]
    tail = sorted(returns)[:ceil(len(returns) * 0.05)]
    ratios = _risk_stats(nav, float(capital))
    drawdown = float(state.max_drawdown)
    return {
        **ratios,
        "calmar": ratios["annualised_return_pct"] / 100 / drawdown if drawdown else None,
        "close_only_drawdown_pct": ratios["max_drawdown_pct"],
        "max_drawdown_pct": drawdown * 100,
        "hourly_95_expected_shortfall_loss_pct": max(0.0, -mean(tail) * 100),
        "max_daily_loss_pct": float(state.max_daily_loss * 100),
        "final_liquidatable_usdt": str(state.nav[-1]),
        "gross_fixed_fills_usdt": float(gross), "gross_fixed_fills_return_pct": float(gross / capital * 100),
        "modelled_fees_including_terminal_usdt": float(fees),
        "modelled_price_concession_including_terminal_usdt": float(slip),
        "net_execution_return_pct": float(net / capital * 100),
        "turnover_over_starting_capital": float(turnover / capital),
        "max_fill_share_of_reported_hourly_volume_bps": float(volume_share * BPS),
        "fraction_of_hourly_marks_with_exposure": sum(x > 0 for x in state.notional) / len(nav),
        "mean_open_notional_fraction_initial_equity": float(mean(state.notional) / capital),
        "modelled_fills": len(state.fills), "closed_trades": len(pnl), "wins": len(wins), "losses": len(losses),
        "terminal_open_positions": len(state.positions), "terminal_estimated_pnl_usdt": float(terminal_pnl),
        "expectancy_usdt_per_closed_trade": float(mean(pnl)) if pnl else None,
        "profit_factor": float(sum(wins) / sum(losses)) if losses else None,
        "median_holding_hours": median(hours_held) if hours_held else None,
        "mean_holding_hours": mean(hours_held) if hours_held else None,
        "exit_reasons": dict(exit_reasons), "daily_suspensions": state.daily_suspensions,
        "drawdown_suspension": state.window_suspended,
        "max_aggregate_planned_risk_at_entry_pct": float(state.max_planned_risk * 100),
        "net_execution_pnl_usdt_by_market": {symbol: float(pnl_by_market[symbol]) for symbol in markets},
        "closed_trade_entry_regime": {name: {"closed_trades": len(values), "net_usdt": float(sum(values))}
                                      for name, values in grouped.items()},
        "fill_ledger_sha256": ledger_hash([astuple(row) for row in state.fills]),
        "nav_ledger_sha256": ledger_hash(state.nav),
    }

"""Separate float implementation to verify v0.9 decisions, fills and equity.

Uses the same registered assumptions and bars. Imports neither signal code nor
accounting code and does not verify executable prices or prospective results.
"""
from collections import defaultdict
from datetime import timedelta
from math import fsum, isclose


def float_bars(bars):
    return [(row.time, float(row.open), float(row.high), float(row.low), float(row.close)) for row in bars]


def calendar_bars(rows, hours):
    windows = defaultdict(list)
    for i, (timestamp, _, high, low, close) in enumerate(rows):
        date = timestamp.date()
        if hours == 168:
            key = date - timedelta(days=date.weekday())
        elif hours == 24:
            key = date
        else:
            key = date, timestamp.hour // 4
        windows[key].append((i, high, low, close))
    return [(group[-1][0], max(x[1] for x in group), min(x[2] for x in group), group[-1][3])
            for group in windows.values() if len(group) == hours]


def reference_signals(rows, params, timing):
    channel = params["family"] == "breakout"
    series = calendar_bars(rows, params["signal_hours"])
    confirm = calendar_bars(rows, params["confirmation_hours"] if channel else 24)
    lower = float(timing["stop_floor_fraction"])
    upper = float(timing["stop_ceiling_fraction"])
    multiplier = float(params["atr_multiple"])
    length = timing["atr_bars"]
    prior_length = params["entry_bars"] if channel else params["mean_bars"]
    confirmation_length = params["confirmation_bars"] if channel else params["range_days"] + 1
    known = 0
    result = [None] * len(rows)
    for j, (i, _, _, close) in enumerate(series):
        while known < len(confirm) and confirm[known][0] <= i:
            known += 1
        if known < confirmation_length or j < max(length, prior_length):
            continue
        old = series[j - prior_length:j]
        recent = series[j - length:j + 1]
        volatility = fsum(max(new[1] - new[2], abs(new[1] - before[3]), abs(new[2] - before[3]))
                          for before, new in zip(recent, recent[1:])) / length
        if volatility <= 0:
            continue
        context = [x[3] for x in confirm[known - confirmation_length:known]]
        if channel:
            entry = close > max(x[1] for x in old) and context[-1] > fsum(context) / confirmation_length
            exit_ = close < min(x[2] for x in old[-params["exit_bars"]:])
        else:
            centre = fsum(x[3] for x in old) / len(old)
            ranged = abs(context[-1] / context[0] - 1) <= float(params["max_range_return_fraction"])
            entry = ranged and centre - close >= float(params["entry_atr"]) * volatility
            exit_ = not ranged or close >= centre
        result[i] = (entry, exit_, min(upper, max(lower, multiplier * volatility / close)))
    return result


def reference_replay(markets, decisions, start, end, rules, fee, slip):
    debit, credit = (1 + slip) * (1 + fee), (1 - slip) * (1 - fee)
    cash = high_water = daily_base = prior_nav = float(rules.capital)
    position_cap = float(rules.allocation_per_market)
    limits = rules.limits
    positions, last_exit = {}, {}
    curve, fills = [], []
    day = pending = None
    day_halt = window_halt = False
    maximum_drawdown = maximum_daily = max_planned = 0.0
    suspensions = 0
    close_stops = set()

    def check_mark(nav):
        nonlocal high_water, maximum_drawdown, maximum_daily, day_halt, window_halt, suspensions
        high_water = max(high_water, nav)
        drawdown = (high_water - nav) / high_water
        today = (daily_base - nav) / daily_base
        maximum_drawdown, maximum_daily = max(maximum_drawdown, drawdown), max(maximum_daily, today)
        if limits:
            if not day_halt and today >= float(limits.daily_loss):
                day_halt = True
                suspensions += 1
            window_halt = window_halt or drawdown >= float(limits.drawdown)
        return "PORTFOLIO_DRAWDOWN" if window_halt else "DAILY_LOSS" if day_halt else None

    def sell(i, symbol, raw, reason):
        nonlocal cash
        qty, _, stop, planned = positions.pop(symbol)
        paid = qty * raw * credit
        cash += paid
        fills.append((i, symbol, "SELL", reason, raw, qty, paid, qty * raw * (1 - slip) * fee,
                      qty * raw * slip, stop, planned))
        last_exit[symbol] = i

    for i in range(start, end):
        rows = {symbol: series[i] for symbol, series in markets.items()}
        current_day = next(iter(rows.values()))[0].date()
        if day != current_day:
            day, daily_base, day_halt = current_day, prior_nav, False
        opening_nav = cash + fsum(qty * rows[s][1] * credit for s, (qty, _, _, _) in positions.items())
        breach = check_mark(opening_nav)
        events = {s: seq[i - 1 - rules.signal_delay_hours] for s, seq in decisions.items()}
        for symbol in tuple(positions):
            _, entered, stop, _ = positions[symbol]
            opening = rows[symbol][1]
            event = events[symbol]
            if pending or breach:
                sell(i, symbol, opening, pending or breach)
            elif symbol in close_stops:
                sell(i, symbol, opening, "STOP_AT_CLOSE")
            elif not rules.close_triggered_stop and stop and opening <= stop:
                sell(i, symbol, opening, "STOP_GAP")
            elif rules.maximum_holding_hours is not None and i - entered >= rules.maximum_holding_hours:
                sell(i, symbol, opening, "TIME_LIMIT")
            elif event and event.exit:
                sell(i, symbol, opening, "SIGNAL_EXIT")

        for symbol, event in events.items():
            if event is None or not event.enter or symbol in positions or day_halt or window_halt:
                continue
            if symbol in last_exit and i - last_exit[symbol] < max(1, rules.cooldown_hours):
                continue
            price = rows[symbol][1]
            budget = min(cash, float(rules.capital) * position_cap)
            qty = budget / (price * debit)
            stop = planned = 0.0
            if limits:
                exposure = fsum(q * rows[s][1] for s, (q, _, _, _) in positions.items())
                equity = cash + exposure * credit
                # Fees and concession on earlier entries at this open reduce the next proposal's equity.
                if (high_water - equity) / high_water >= float(limits.drawdown):
                    continue
                outstanding = fsum(lot[3] for lot in positions.values())
                stop = price * (1 - float(event.stop_fraction))
                unit_loss = price * debit - stop * credit
                qty = min(qty, equity * position_cap / (price * debit), equity * float(limits.position_stop_risk) / unit_loss,
                          (equity * float(limits.aggregate_stop_risk) - outstanding) / unit_loss)
                if qty <= 0 or exposure + qty * price * debit > equity + 1e-9:
                    continue
                planned = qty * unit_loss
                max_planned = max(max_planned, (outstanding + planned) / equity)
            if qty <= 0:
                continue
            outlay = qty * price * debit
            cash -= outlay
            if cash < -1e-8:
                raise ValueError("Reference detected negative cash")
            positions[symbol] = (qty, i, stop, planned)
            fills.append((i, symbol, "BUY", "SIGNAL", price, qty, -outlay, qty * price * (1 + slip) * fee,
                          qty * price * slip, stop, planned))
            if limits:
                after_fill = cash + fsum(q * rows[s][1] * credit for s, (q, _, _, _) in positions.items())
                check_mark(after_fill)

        for symbol in tuple(positions):
            stop = positions[symbol][2]
            if not rules.close_triggered_stop and stop and rows[symbol][3] <= stop:
                sell(i, symbol, stop, "STOP_TOUCH")
        prior_nav = cash + fsum(qty * rows[s][4] * credit for s, (qty, _, _, _) in positions.items())
        curve.append(prior_nav)
        pending = check_mark(prior_nav)
        if rules.close_triggered_stop:
            close_stops = {s for s, (_, _, stop, _) in positions.items() if rows[s][4] <= stop}
    return curve, fills, (cash, maximum_drawdown, maximum_daily, max_planned, suspensions, window_halt)


def same(left, right):
    return isclose(float(left), float(right), rel_tol=1e-10, abs_tol=1e-8)


class ReferenceAudit:
    def __init__(self):
        self._bars = {}
        self.signal_slots = self.replays = self.nav_marks = self.fills = 0

    def bars(self, data):
        key = id(data)
        if key not in self._bars:
            self._bars[key] = (data, float_bars(data))
        return self._bars[key][1]

    def signals(self, bars, params, timing, generated):
        expected = reference_signals(self.bars(bars), params, timing)
        for index, (want, got) in enumerate(zip(expected, generated, strict=True)):
            if ((want is None) != (got is None) or want is not None
                    and (want[:2] != (got.enter, got.exit) or not same(want[2], got.stop_fraction))):
                raise ValueError(f"Reference signal mismatch at {params['id']} bar {index}: {want} vs {got}")
        self.signal_slots += len(expected)

    def replay(self, markets, decisions, start, end, rules, costs, state):
        curve, fills, checks = reference_replay({s: self.bars(series) for s, series in markets.items()}, decisions,
                                                start, end, rules, float(costs.fee_bps) / 10_000,
                                                float(costs.adverse_slippage_bps) / 10_000)
        for expected, row in zip(fills, state.fills):
            actual = (row.index, row.symbol, row.side, row.reason, row.reference_price, row.quantity, row.cash_delta,
                      row.fee, row.price_concession, row.stop_price, row.planned_risk)
            if expected[:4] != actual[:4] or any(not same(a, b) for a, b in zip(expected[4:], actual[4:], strict=True)):
                raise ValueError(f"Independent fill mismatch at hour {row.index}: {expected} vs {actual}")
        if len(fills) != len(state.fills):
            raise ValueError(f"Independent fill count mismatch for {tuple(markets)} hours {start}:{end}")
        for i, (left, right) in enumerate(zip(curve, state.nav, strict=True), start):
            if not same(left, right):
                raise ValueError(f"Independent NAV mismatch for {tuple(markets)} at hour {i}: {left} vs {right}")
        actual_checks = (state.cash, state.max_drawdown, state.max_daily_loss, state.max_planned_risk,
                         state.daily_suspensions, state.window_suspended)
        if checks[-2:] != actual_checks[-2:] or any(not same(a, b) for a, b in zip(checks[:4], actual_checks[:4], strict=True)):
            raise ValueError(f"Independent risk or cash mismatch in {tuple(markets)} hours {start}:{end}")
        self.replays += 1
        self.nav_marks += len(curve)
        self.fills += len(fills)

    def summary(self):
        return {"status": "REPRODUCED", "signal_slots": self.signal_slots, "replays": self.replays,
                "hourly_nav_marks": self.nav_marks, "modelled_fills": self.fills,
                "absolute_tolerance": 1e-8, "relative_tolerance": 1e-10}

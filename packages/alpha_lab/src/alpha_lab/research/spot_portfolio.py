"""Deterministic shared-cash spot replay. No broker or market orders."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, localcontext

from alpha_lab.research.strategy_v08_replay import BPS, ZERO, RiskLimits
from alpha_lab.risk.policy import ResearchProposal, RiskPolicy, assess_proposal

EPSILON = Decimal("1e-18")


@dataclass(frozen=True)
class ReplayRules:
    capital: Decimal
    allocation_per_market: Decimal
    limits: RiskLimits | None = None
    cooldown_hours: int = 0
    maximum_holding_hours: int | None = None
    signal_delay_hours: int = 0
    close_triggered_stop: bool = False

    def __post_init__(self):
        for value in (self.cooldown_hours, self.signal_delay_hours):
            if type(value) is not int or value < 0:
                raise ValueError("Replay delays must be nonnegative whole hours")
        if self.maximum_holding_hours is not None and (type(self.maximum_holding_hours) is not int
                                                       or self.maximum_holding_hours <= 0):
            raise ValueError("Holding limit must be positive whole hours")


@dataclass(frozen=True)
class Position:
    quantity: Decimal
    index: int
    entry_price: Decimal
    outlay: Decimal
    stop: Decimal
    planned_risk: Decimal


@dataclass(frozen=True)
class Fill:
    index: int
    symbol: str
    side: str
    reason: str
    reference_price: Decimal
    quantity: Decimal
    cash_delta: Decimal
    fee: Decimal
    price_concession: Decimal
    stop_price: Decimal
    planned_risk: Decimal


@dataclass(frozen=True)
class ClosedTrade:
    symbol: str
    entry_index: int
    hours_held: int
    net_pnl: Decimal


class Portfolio:
    def __init__(self, rules, costs):
        self.rules = rules
        self.costs = costs
        self.positions = {}
        self.last_exit = {}
        self.cash = self.peak = self.day_start = rules.capital
        self.max_drawdown = self.max_daily_loss = self.max_planned_risk = ZERO
        self.day_suspended = self.window_suspended = False
        self.daily_suspensions = 0
        self.nav, self.notional, self.fills, self.closed = [], [], [], []
        self.policy = None
        if rules.limits:
            self.policy = RiskPolicy(max_new_position_fraction=rules.allocation_per_market,
                                     max_total_exposure_fraction=Decimal(1),
                                     max_daily_loss_fraction=rules.limits.daily_loss,
                                     max_drawdown_fraction=rules.limits.drawdown)

    def mark(self, prices):
        raw = sum((lot.quantity * prices[symbol] for symbol, lot in self.positions.items()), ZERO)
        liquidatable = self.cash + self.costs.sell_proceeds(raw, Decimal(1))
        return liquidatable, raw

    def observe(self, equity):
        if equity <= 0 or self.cash < -EPSILON:
            raise ValueError("Invalid shared cash or equity")
        self.peak = max(self.peak, equity)
        drawdown = 1 - equity / self.peak
        daily_loss = 1 - equity / self.day_start
        self.max_drawdown = max(self.max_drawdown, drawdown)
        self.max_daily_loss = max(self.max_daily_loss, daily_loss)
        if self.rules.limits:
            self.window_suspended |= drawdown >= self.rules.limits.drawdown
            if daily_loss >= self.rules.limits.daily_loss and not self.day_suspended:
                self.daily_suspensions += 1
                self.day_suspended = True

    def forced_exit(self):
        if self.window_suspended:
            return "PORTFOLIO_DRAWDOWN"
        if self.day_suspended:
            return "DAILY_LOSS"
        return None

    def fill(self, i, symbol, side, reason, price, lot):
        is_buy = side == "BUY"
        adjusted = self.costs.buy_price(price) if is_buy else self.costs.sell_price(price)
        amount = -lot.outlay if is_buy else self.costs.sell_proceeds(lot.quantity, price)
        self.cash += amount
        self.fills.append(Fill(i, symbol, side, reason, price, lot.quantity, amount,
                               lot.quantity * adjusted * self.costs.fee_bps / BPS,
                               lot.quantity * abs(adjusted - price), lot.stop, lot.planned_risk))
        return amount

    def enter(self, i, symbol, decision, prices):
        if self.forced_exit() or symbol in self.positions:
            return
        last = self.last_exit.get(symbol)
        if last is not None and i - last < max(1, self.rules.cooldown_hours):
            return
        equity, exposure = self.mark(prices)
        price = prices[symbol]
        risk = self.rules.limits
        stop = price * (1 - decision.stop_fraction) if risk else ZERO
        budget = min(self.cash, self.rules.capital * self.rules.allocation_per_market)
        outstanding = sum((lot.planned_risk for lot in self.positions.values()), ZERO)
        with localcontext(rounding=ROUND_DOWN):
            if risk:
                if not 0 < stop < price:
                    raise ValueError("A risk-limited entry requires a positive stop below entry")
                budget = min(budget, equity * self.rules.allocation_per_market)
                unit_loss = self.costs.buy_outlay(Decimal(1), price) - self.costs.sell_proceeds(Decimal(1), stop)
                room = min(equity * risk.position_stop_risk, equity * risk.aggregate_stop_risk - outstanding)
                budget = min(budget, room / unit_loss * self.costs.buy_outlay(Decimal(1), price))
            if budget <= 0:
                return
            units = self.costs.buy_quantity(budget, price)
            outlay = self.costs.buy_outlay(units, price)
            planned = units * unit_loss if risk else ZERO
        if risk:
            assessment = assess_proposal(ResearchProposal(
                equity=equity, open_exposure=exposure, proposed_notional=outlay,
                realised_daily_pnl=ZERO, drawdown_fraction=max(ZERO, 1 - equity / self.peak),
                quote_age_seconds=0, data_integrity_ok=True, kill_switch_active=False,
            ), self.policy)
            if (not assessment.passes_research_checks or planned > equity * risk.position_stop_risk + EPSILON
                    or outstanding + planned > equity * risk.aggregate_stop_risk + EPSILON):
                return
            self.max_planned_risk = max(self.max_planned_risk, (outstanding + planned) / equity)
        lot = Position(units, i, price, outlay, stop, planned)
        self.positions[symbol] = lot
        self.fill(i, symbol, "BUY", "SIGNAL", price, lot)
        if risk:
            # A fill can consume the remaining daily or drawdown allowance
            # before another market submits at this same opening price.
            self.observe(self.mark(prices)[0])

    def exit(self, i, symbol, reason, price):
        lot = self.positions.pop(symbol)
        proceeds = self.fill(i, symbol, "SELL", reason, price, lot)
        # A stop touched inside the bar counts that hour of price exposure.
        holding = i - lot.index + (reason == "STOP_TOUCH")
        self.closed.append(ClosedTrade(symbol, lot.index, holding, proceeds - lot.outlay))
        self.last_exit[symbol] = i


def replay_portfolio(markets, signals, start, end, rules, costs):
    """Each market supplies the same pre-verified UTC hourly grid."""
    symbols = tuple(markets)
    if (not symbols or tuple(signals) != symbols or not 1 + rules.signal_delay_hours <= start < end
            or any(end > len(markets[s]) or len(markets[s]) != len(signals[s]) for s in symbols)
            or not rules.capital.is_finite() or rules.capital <= 0
            or not 0 < rules.allocation_per_market <= 1):
        raise ValueError("Invalid shared portfolio inputs")
    state = Portfolio(rules, costs)
    previous_day, pending_forced = None, None
    stops_at_close = set()
    for i in range(start, end):
        rows = {symbol: markets[symbol][i] for symbol in symbols}
        opens = {symbol: row.open for symbol, row in rows.items()}
        day = rows[symbols[0]].time.date()
        if any(row.time != rows[symbols[0]].time for row in rows.values()):
            raise ValueError("Portfolio markets have different UTC grids")
        if day != previous_day:
            state.day_start = state.nav[-1] if state.nav else rules.capital
            state.day_suspended = False
            previous_day = day
        state.observe(state.mark(opens)[0])
        forced = pending_forced or state.forced_exit()
        decisions = {symbol: signals[symbol][i - 1 - rules.signal_delay_hours] for symbol in symbols}
        for symbol, lot in list(state.positions.items()):
            decision = decisions[symbol]
            reason = forced
            if not reason and symbol in stops_at_close:
                reason = "STOP_AT_CLOSE"
            if not reason and not rules.close_triggered_stop and lot.stop and opens[symbol] <= lot.stop:
                reason = "STOP_GAP"
            if not reason and rules.maximum_holding_hours and i - lot.index >= rules.maximum_holding_hours:
                reason = "TIME_LIMIT"
            if not reason and decision and decision.exit:
                reason = "SIGNAL_EXIT"
            if reason:
                state.exit(i, symbol, reason, opens[symbol])

        for symbol, decision in decisions.items():
            if decision and decision.enter:
                state.enter(i, symbol, decision, opens)

        if not rules.close_triggered_stop:
            for symbol, lot in list(state.positions.items()):
                if lot.stop and rows[symbol].low <= lot.stop:
                    state.exit(i, symbol, "STOP_TOUCH", lot.stop)

        closes = {symbol: row.close for symbol, row in rows.items()}
        equity, notional = state.mark(closes)
        state.observe(equity)
        state.nav.append(equity)
        state.notional.append(notional)
        pending_forced = state.forced_exit()
        if rules.close_triggered_stop:
            stops_at_close = {s for s, lot in state.positions.items() if closes[s] <= lot.stop}
    return state

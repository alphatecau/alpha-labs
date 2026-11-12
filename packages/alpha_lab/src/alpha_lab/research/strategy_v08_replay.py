"""Offline spot accounting with explicit position risk and loss suspensions."""
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, localcontext
from statistics import mean

from alpha_lab.backtest.costs import CostModel
from alpha_lab.research.long_history import _risk_stats
from alpha_lab.risk.policy import ResearchProposal, RiskPolicy, assess_proposal

ZERO = Decimal(0)
BPS = Decimal(10_000)


@dataclass(frozen=True)
class RiskLimits:
    stop_distance: Decimal
    position_stop_risk: Decimal
    aggregate_stop_risk: Decimal
    daily_loss: Decimal
    drawdown: Decimal

    def __post_init__(self):
        ceilings = {
            "stop_distance": Decimal("0.20"),
            "position_stop_risk": Decimal("0.0025"),
            "aggregate_stop_risk": Decimal("0.01"),
            "daily_loss": Decimal("0.02"),
            "drawdown": Decimal("0.05"),
        }
        for name, ceiling in ceilings.items():
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or not 0 < value <= ceiling:
                raise ValueError(f"Invalid research risk limit: {name}")


@dataclass(frozen=True)
class Replay:
    nav: list[Decimal]
    metrics: dict
    orders: list[dict]


def _size(cash: Decimal, start_cap: Decimal, allocation: Decimal, price: Decimal,
          costs: CostModel, risk: RiskLimits | None) -> tuple[Decimal, Decimal, Decimal]:
    quantity = costs.buy_quantity(min(cash, start_cap * allocation), price)
    if risk is None:
        return quantity, ZERO, ZERO
    quantity = min(quantity, costs.buy_quantity(cash * allocation, price))
    stop = price * (1 - risk.stop_distance)
    unit_loss = costs.buy_outlay(Decimal(1), price) - costs.sell_proceeds(Decimal(1), stop)
    limit = min(risk.position_stop_risk, risk.aggregate_stop_risk)
    # Round towards zero so quantity cannot push planned loss over the budget.
    with localcontext(rounding=ROUND_DOWN):
        quantity = min(quantity, cash * limit / unit_loss)
        planned_fraction = quantity * unit_loss / cash
    return quantity, stop, planned_fraction


def replay_window(bars, targets, start: int, end: int, *, capital: Decimal,
                  allocation: Decimal, costs: CostModel, risk: RiskLimits | None = None) -> Replay:
    """Replay verified candles. Targets use the previous close and fills use the next open.

    Benchmarks use the original starting-capital allocation rule.
    The optional risk overlay can only veto new long positions or request exits.
    """
    if not 1 <= start < end <= len(bars) or len(targets) != len(bars):
        raise ValueError("Invalid replay window or target count")
    if not capital.is_finite() or capital <= 0 or not 0 < allocation <= 1:
        raise ValueError("Invalid replay capital or allocation")
    policy = None
    if risk is not None:
        policy = RiskPolicy(
            max_new_position_fraction=allocation, max_total_exposure_fraction=allocation,
            max_daily_loss_fraction=risk.daily_loss, max_drawdown_fraction=risk.drawdown,
        )
    cash = peak = nav = day_start_nav = capital
    quantity = entry_outlay = stop = ZERO
    fees = slippage = volume = max_planned_risk = max_daily_loss = drawdown = ZERO
    day = pending_exit = None
    daily_suspended = drawdown_suspended = False
    suspended_days = exposure_hours = 0
    rejections, exits = Counter(), Counter()
    curve, orders, closed_pnl = [], [], []

    for i in range(start, end):
        bar = bars[i]
        if bar.time.date() != day:
            day, day_start_nav = bar.time.date(), nav
            daily_suspended = False
        target_long = targets[i - 1]
        price = bar.open
        if quantity > 0 and (pending_exit is not None or not target_long):
            reason = pending_exit or "SIGNAL_FLAT"
            nominal = quantity * costs.sell_price(price)
            fee = nominal * costs.fee_bps / BPS
            proceeds = costs.sell_proceeds(quantity, price)
            fees += fee
            slippage += quantity * (price - costs.sell_price(price))
            volume += nominal
            cash += proceeds
            closed_pnl.append(proceeds - entry_outlay)
            orders.append({"side": "SELL", "time": bar.time, "quantity": quantity,
                           "cash_delta": proceeds, "fee": fee, "reason": reason})
            exits[reason] += 1
            quantity = ZERO
        elif quantity == 0 and target_long:
            if drawdown_suspended or daily_suspended:
                rejections["DRAWDOWN_LIMIT" if drawdown_suspended else "DAILY_LOSS_LIMIT"] += 1
            else:
                units, stop_ref, planned = _size(cash, capital, allocation, price, costs, risk)
                nominal = units * costs.buy_price(price)
                fee = nominal * costs.fee_bps / BPS
                outlay = costs.buy_outlay(units, price)
                if units <= 0 or outlay > cash + Decimal("1e-15"):
                    raise ValueError("Invalid modelled entry size")
                reasons = ()
                if policy is not None:
                    # Mark-to-market daily loss is handled by the suspension above.
                    # Age zero refers only to the modelled historical open.
                    assessment = assess_proposal(ResearchProposal(
                        equity=cash, open_exposure=ZERO, proposed_notional=nominal,
                        realised_daily_pnl=ZERO, drawdown_fraction=drawdown,
                        quote_age_seconds=0, data_integrity_ok=True, kill_switch_active=False,
                    ), policy)
                    reasons = assessment.reasons
                    if planned > min(risk.position_stop_risk, risk.aggregate_stop_risk):
                        reasons += ("STOP_RISK_LIMIT",)
                if reasons:
                    rejections.update(reasons)
                else:
                    quantity, stop, entry_outlay = units, stop_ref, outlay
                    max_planned_risk = max(max_planned_risk, planned)
                    fees += fee
                    slippage += units * (costs.buy_price(price) - price)
                    volume += nominal
                    cash -= outlay
                    orders.append({"side": "BUY", "time": bar.time, "quantity": units,
                                   "cash_delta": -outlay, "fee": fee,
                                   "stop_reference": stop_ref, "planned_stop_risk_fraction": planned})

        nav = cash + costs.sell_proceeds(quantity, bar.close)
        if nav <= 0 or cash < -Decimal("1e-12"):
            raise ValueError("Invalid modelled portfolio state")
        curve.append(nav)
        peak = max(peak, nav)
        drawdown = (peak - nav) / peak
        daily_loss = (day_start_nav - nav) / day_start_nav
        max_daily_loss = max(max_daily_loss, daily_loss)
        exposure_hours += quantity > 0
        pending_exit = None
        if risk is not None:
            if daily_loss >= risk.daily_loss and not daily_suspended:
                daily_suspended = True
                suspended_days += 1
            drawdown_suspended |= drawdown >= risk.drawdown
            if quantity > 0:
                if drawdown_suspended:
                    pending_exit = "DRAWDOWN_LIMIT"
                elif daily_suspended:
                    pending_exit = "DAILY_LOSS_LIMIT"
                elif bar.close <= stop:
                    pending_exit = "STOP_AT_CLOSE"

    open_pnl = costs.sell_proceeds(quantity, bars[end - 1].close) - entry_outlay if quantity else ZERO
    if abs(sum(closed_pnl, open_pnl) - (nav - capital)) > Decimal("1e-18"):
        raise ValueError("Closed and estimated open P&L do not reconcile")
    wins = sum(pnl for pnl in closed_pnl if pnl > 0)
    losses = -sum(pnl for pnl in closed_pnl if pnl < 0)
    metrics = {
        "net_execution_return_pct": float((nav / capital - 1) * 100),
        "final_liquidatable_usdt": str(nav),
        "modelled_fees_usdt": str(fees),
        "modelled_slippage_usdt": str(slippage),
        "turnover_to_starting_capital": float(volume / capital),
        "exposure_fraction_of_hours": exposure_hours / len(curve),
        "modelled_fills": len(orders),
        "closed_trades": len(closed_pnl),
        "profit_factor": float(wins / losses) if losses else None,
        "expectancy_usdt_per_closed_trade": float(mean(closed_pnl)) if closed_pnl else None,
        "open_position_at_end": quantity > 0,
        "max_daily_mark_to_market_loss_pct": float(max_daily_loss * 100),
        **_risk_stats([float(value) for value in curve], float(capital)),
    }
    if risk is not None:
        metrics["risk"] = {
            "max_planned_stop_risk_pct": float(max_planned_risk * 100),
            "daily_suspensions": suspended_days,
            "drawdown_suspension": drawdown_suspended,
            "entry_rejections": dict(rejections),
            "exit_reasons": dict(exits),
        }
    return Replay(curve, metrics, orders)

"""Independent, read-only sizing for a proposed USD spot research trade."""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from alpha_lab.data.adapters.coinbase_candles import ProductRules
from alpha_lab.research.coinbase_paper_book import executable
from alpha_lab.research.paper_market import DEFAULT_COSTS
from alpha_lab.research.paper_risk import PaperRiskLimits, authorise_simulated_order
from alpha_lab.research.trade_signals import ENTRY_BAND_ATR, HOLD_BARS, STOP_ATR, TARGET_ATR

LIMITS = PaperRiskLimits()
ASSET_CAP = Decimal("0.35")
CRYPTO_GROUP_CAP = Decimal("0.70")
MAX_BOOK_FRACTION = Decimal("0.10")
MIN_REWARD_TO_RISK = Decimal("1.5")
ZERO = Decimal(0)


@dataclass(frozen=True)
class ResearchRisk:
    cash: Decimal
    nav: Decimal
    initial_nav: Decimal
    peak_nav: Decimal
    day_start_nav: Decimal
    open_stop_risk: Decimal
    exposure: tuple[tuple[str, Decimal], ...]
    halt_reason: str | None = None

    @property
    def gross(self):
        return sum((notional for _, notional in self.exposure), ZERO)


def _round_to(value, step, rounding=ROUND_FLOOR):
    return (value / step).to_integral_value(rounding=rounding) * step


def estimate_round_trip_bps(quote, costs):
    # Full quoted spread plus fee and impact assumptions on both legs.
    return ((quote.ask - quote.bid) / quote.mid + 2 * (costs.fee + costs.slippage)) * 10000


def size_long(*, quote, rules, regime, risk, now, signal_at, interval_seconds, costs=DEFAULT_COSTS):
    """Calculate a research proposal and independently check post-entry NAV."""
    if risk is None:
        return None, ("Protected portfolio state is unavailable",)
    if risk.halt_reason:
        return None, (risk.halt_reason,)
    if not executable(quote, now) or quote.exchange_at > now:
        return None, ("Source book is unavailable, stale or ahead of the decision clock",)
    if (not isinstance(rules, ProductRules) or rules.product != quote.symbol
            or not all(isinstance(value, Decimal) and value.is_finite() and value > 0
                       for value in (rules.price_step, rules.quantity_step, rules.min_notional))):
        return None, ("Verified product increments and minimum are unavailable",)
    if not signal_at <= now < signal_at + timedelta(seconds=interval_seconds):
        return None, ("Entry signal expired",)
    amounts = (risk.cash, risk.nav, risk.initial_nav, risk.peak_nav, risk.day_start_nav,
               risk.open_stop_risk, *(value for _, value in risk.exposure))
    if (not all(isinstance(value, Decimal) and value.is_finite() and value >= 0 for value in amounts)
            or min(risk.nav, risk.initial_nav, risk.peak_nav, risk.day_start_nav) <= 0
            or risk.cash + risk.gross != risk.nav):
        return None, ("Invalid or unreconciled risk inputs",)
    step = rules.price_step
    entry = _round_to(quote.ask, step, ROUND_CEILING)
    zone_min = _round_to(regime.close - ENTRY_BAND_ATR * regime.atr, step, ROUND_CEILING)
    zone_max = _round_to(regime.close + ENTRY_BAND_ATR * regime.atr, step)
    stop = _round_to(entry - STOP_ATR * regime.atr, step)
    target = _round_to(entry + TARGET_ATR * regime.atr, step)
    if not (0 < zone_min <= entry <= zone_max and 0 < stop < quote.bid <= entry < target):
        return None, ("Entry is outside its candle-based zone or stop/target geometry is invalid",)

    buy_px = entry * (1 + costs.slippage)
    stop_px = stop * (1 - costs.slippage)
    target_px = target * (1 - costs.slippage)
    buy_cash = buy_px * (1 + costs.fee)
    unit_loss = buy_cash - stop_px * (1 - costs.fee)
    unit_reward = target_px * (1 - costs.fee) - buy_cash
    if unit_loss <= 0 or unit_reward < MIN_REWARD_TO_RISK * unit_loss:
        return None, ("Net reward-to-risk is below the research threshold",)

    equity_cost = buy_cash - quote.bid
    held = dict(risk.exposure).get(quote.symbol, ZERO)
    hard_floor = max(risk.day_start_nav * (1 - LIMITS.daily_loss_halt_pct),
                     risk.peak_nav * (1 - LIMITS.drawdown_halt_pct))
    ceilings = {
        "Trade stop-risk limit": LIMITS.max_position_risk_pct * risk.nav /
            (unit_loss + LIMITS.max_position_risk_pct * equity_cost),
        "Aggregate stop-risk limit": (LIMITS.max_aggregate_risk_pct * risk.nav - risk.open_stop_risk) /
            (unit_loss + LIMITS.max_aggregate_risk_pct * equity_cost),
        "Gross notional limit": (LIMITS.max_notional_multiple * risk.nav - risk.gross) /
            (quote.bid + LIMITS.max_notional_multiple * equity_cost),
        "Asset concentration limit": (ASSET_CAP * risk.nav - held) / (quote.bid + ASSET_CAP * equity_cost),
        "Correlated crypto exposure limit": (CRYPTO_GROUP_CAP * risk.nav - risk.gross) /
            (quote.bid + CRYPTO_GROUP_CAP * equity_cost),
        "Available virtual cash": risk.cash / buy_cash,
        "Displayed ask depth limit": quote.ask_size * MAX_BOOK_FRACTION,
    }
    if risk.nav <= hard_floor:
        return None, ("Daily loss or drawdown HALT",)
    if equity_cost:
        ceilings["Daily loss or drawdown limit"] = (risk.nav - hard_floor) / equity_cost
    limiting = min(ceilings, key=ceilings.get)
    quantity = _round_to(ceilings[limiting], rules.quantity_step)
    if quantity > 0 and risk.nav - quantity * equity_cost <= hard_floor:
        quantity -= rules.quantity_step
    if quantity <= 0 or quantity * entry < rules.min_notional:
        return None, (limiting, "No permitted quantity meets the exchange minimum")

    nav_after = risk.nav - quantity * equity_cost
    loss = quantity * unit_loss
    gate = authorise_simulated_order(
        nav=nav_after, initial_nav=risk.initial_nav, peak_nav=risk.peak_nav, day_start_nav=risk.day_start_nav,
        proposed_loss=loss, aggregate_open_risk=risk.open_stop_risk, gross_notional=risk.gross,
        proposed_notional=quantity * quote.bid, data_fresh=True, ledger_reconciled=True,
        operator_enabled=True,
    )
    if not gate["approved"]:
        return None, tuple(gate["reasons"])

    return {
        "currency": "USD",
        "entry": str(entry), "entry_zone": [str(zone_min), str(zone_max)],
        "entry_trigger": "Fresh ask inside the zone while the completed-candle signal remains valid",
        "stop": str(stop), "target": str(target), "reward_to_risk_net": str(unit_reward / unit_loss),
        "max_quantity": str(quantity), "max_planned_loss": str(loss),
        "planned_loss_fraction_post_entry": str(loss / nav_after),
        "estimated_round_trip_fees_at_target": str(quantity * costs.fee * (buy_px + target_px)),
        "estimated_round_trip_slippage_at_target": str(quantity * costs.slippage * (entry + target)),
        "observed_spread_bps": str((quote.ask - quote.bid) / quote.mid * 10000),
        "estimated_round_trip_bps": str(estimate_round_trip_bps(quote, costs)),
        "size_limit": limiting,
        "entry_expires_utc": (signal_at + timedelta(seconds=interval_seconds)).isoformat(),
        "max_holding_seconds": HOLD_BARS * interval_seconds,
        "time_exit": "Close any simulated position at the first observation after the holding deadline",
        "risk_scope": "Research plan only. A new independent check is required for any simulated order.",
    }, ()

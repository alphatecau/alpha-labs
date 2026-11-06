"""Deterministic, assumed US equity trading costs for offline research only.

The square-root participation impact term is a heuristic, NOT calibrated
market impact. Requires user-provided midpoint and average daily dollar
volume (ADV); it does not retrieve executable quotes or broker fee schedules.
No order routing, short sale execution, AUD FX, or tax accounting.
"""
from dataclasses import dataclass
from decimal import Decimal

BPS = Decimal('10000')
YEAR_DAYS = Decimal('365')


def _decimal(value, label, *, strictly_positive=False):
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError(f'{label} must be finite Decimal')
    if value < 0 or (strictly_positive and value == 0):
        raise ValueError(f'{label} must be nonnegative' if not strictly_positive
                         else f'{label} must be positive')
    return value


@dataclass(frozen=True)
class EquityCostScenario:
    commission_per_order_usd: Decimal
    commission_per_share_usd: Decimal
    half_spread_bps: Decimal
    slippage_bps: Decimal
    impact_coefficient_bps: Decimal
    max_participation_bps: Decimal

    def __post_init__(self):
        for name in (
            'commission_per_order_usd', 'commission_per_share_usd',
            'half_spread_bps', 'slippage_bps', 'impact_coefficient_bps',
        ):
            _decimal(getattr(self, name), name)
        _decimal(self.max_participation_bps, 'max_participation_bps',
                 strictly_positive=True)
        if self.max_participation_bps > BPS:
            raise ValueError('Participation cannot exceed 100% ADV')
        if self.half_spread_bps + self.slippage_bps >= BPS:
            raise ValueError('Non-executable adverse price concession')


@dataclass(frozen=True)
class EquityFillEstimate:
    side: str
    shares: Decimal
    reference_notional_usd: Decimal
    participation_bps: Decimal
    impact_bps: Decimal
    execution_price_usd: Decimal
    commission_usd: Decimal
    price_concession_usd: Decimal
    total_cost_usd: Decimal
    cash_delta_usd: Decimal
    assumptions_verified: bool = False
    trading_enabled: bool = False


def estimate_equity_fill(scenario, *, side, shares, mid_price_usd,
                         average_daily_dollar_volume_usd):
    """Return a modelled cash delta, negative for BUY, positive for SELL.

    SELL represents a disposal of existing long holdings; borrowing and short
    permission are NOT modelled or implied. One share is the minimum unit.
    """
    if not isinstance(scenario, EquityCostScenario):
        raise ValueError('EquityCostScenario required')
    if side not in ('BUY', 'SELL'):
        raise ValueError('Only BUY/SELL long-equity research sides supported')
    shares = _decimal(shares, 'shares', strictly_positive=True)
    if shares != shares.to_integral_value():
        raise ValueError('Fractional-share execution unsupported')
    mid_price_usd = _decimal(mid_price_usd, 'mid_price_usd',
                             strictly_positive=True)
    adv = _decimal(average_daily_dollar_volume_usd,
                   'average_daily_dollar_volume_usd', strictly_positive=True)
    notional = shares * mid_price_usd
    participation = notional / adv
    participation_bps = participation * BPS
    if participation_bps > scenario.max_participation_bps:
        raise ValueError('Trade exceeds ADV participation cap')
    impact_bps = scenario.impact_coefficient_bps * participation.sqrt()
    concession_bps = (scenario.half_spread_bps + scenario.slippage_bps
                      + impact_bps)
    if concession_bps >= BPS:
        raise ValueError('Non-executable price concession')
    sign = Decimal('1') if side == 'BUY' else Decimal('-1')
    executable = mid_price_usd * (Decimal('1') + sign * concession_bps / BPS)
    commission = (scenario.commission_per_order_usd
                  + scenario.commission_per_share_usd * shares)
    price_concession = shares * mid_price_usd * concession_bps / BPS
    total_cost = commission + price_concession
    cash_delta = (-notional - total_cost if side == 'BUY'
                  else notional - total_cost)
    if side == 'SELL' and cash_delta <= 0:
        raise ValueError('Modelled commissions and concession exhaust proceeds')
    return EquityFillEstimate(
        side=side, shares=shares, reference_notional_usd=notional,
        participation_bps=participation_bps, impact_bps=impact_bps,
        execution_price_usd=executable, commission_usd=commission,
        price_concession_usd=price_concession, total_cost_usd=total_cost,
        cash_delta_usd=cash_delta,
    )


@dataclass(frozen=True)
class ShortBorrowEstimate:
    cost_usd: Decimal
    assumptions_verified: bool = False
    short_execution_supported: bool = False
    trading_enabled: bool = False


def estimate_short_borrow_cost(*, short_notional_usd, annual_borrow_bps,
                               holding_days):
    """A simple hypothetical borrow accrual; no borrow locate or recall risk."""
    notional = _decimal(short_notional_usd, 'short_notional_usd',
                        strictly_positive=True)
    rate = _decimal(annual_borrow_bps, 'annual_borrow_bps')
    days = _decimal(holding_days, 'holding_days')
    return ShortBorrowEstimate(notional * rate / BPS * days / YEAR_DAYS)

"""Conservative, offline stock corporate-action book; not an execution ledger.

Input positions represent holdings established before ex-date market open.
Only declared raw prices are supported; their authenticity is NOT verified.
Payment settlement, taxes, borrowing and cash-in-lieu are unsupported.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from alpha_lab.data.corporate_actions import ActionType, CorporateAction
from alpha_lab.data.exchange_calendar_2026 import sessions_2026
from alpha_lab.domain.assets import AssetClass, Instrument


@dataclass(frozen=True)
class CorporateActionBook:
    symbol: str
    shares: Decimal
    total_cost_usd: Decimal
    cash_usd: Decimal
    dividend_receivable_usd: Decimal = Decimal('0')
    applied_ex_dates: tuple[str, ...] = ()

    def __post_init__(self):
        for amount in (self.shares, self.total_cost_usd,
                       self.cash_usd, self.dividend_receivable_usd):
            if (type(amount) is not Decimal or not amount.is_finite()
                    or amount < 0):
                raise ValueError('Finite nonnegative Decimal amounts required')
        if self.shares != self.shares.to_integral_value():
            raise ValueError('Fractional holdings require settlement model')
        if self.shares == 0 and self.total_cost_usd != 0:
            raise ValueError('No cost basis without shares')
        if type(self.applied_ex_dates) is not tuple or len(set(self.applied_ex_dates)) != len(self.applied_ex_dates):
            raise ValueError('Invalid action history')


def apply_at_ex_open(book, instrument, action, *, at_utc, price_basis):
    """Apply exactly at documented 2026 session open, once per ex-date."""
    if not isinstance(book, CorporateActionBook):
        raise ValueError('Research holding book required')
    if (not isinstance(instrument, Instrument)
            or instrument.asset_class not in (AssetClass.US_EQUITY, AssetClass.US_ETF)
            or instrument.symbol != book.symbol):
        raise ValueError('Equity/ETF instrument mismatch')
    if (not isinstance(action, CorporateAction)
            or action.symbol != book.symbol or action.currency != 'USD'):
        raise ValueError('Corporate action mismatch')
    if price_basis != 'raw':
        raise ValueError('Only raw unadjusted price basis permitted')
    if type(at_utc) is not datetime or at_utc.utcoffset() != timedelta(0):
        raise ValueError('UTC event timestamp required')
    sessions = sessions_2026(instrument.calendar, action.ex_date, action.ex_date)
    if len(sessions) != 1 or at_utc != sessions[0].opens_utc:
        raise ValueError('Action must occur at scheduled ex-date market open')
    if action.announced_at_utc > at_utc or action.recorded_at_utc > at_utc:
        raise ValueError('Corporate action was not yet known')
    key = action.ex_date.isoformat()
    if key in book.applied_ex_dates:
        raise ValueError('Duplicate or multiple same-day actions require adjudication')
    history = book.applied_ex_dates + (key,)
    if action.action_type is ActionType.SPLIT:
        new_shares = book.shares * action.value
        if new_shares != new_shares.to_integral_value():
            raise ValueError('Fractional post-split shares need cash-in-lieu evidence')
        return replace(book, shares=new_shares, applied_ex_dates=history)
    if action.action_type is ActionType.CASH_DIVIDEND:
        return replace(book,
                       dividend_receivable_usd=book.dividend_receivable_usd + book.shares * action.value,
                       applied_ex_dates=history)
    raise ValueError('Unsupported corporate action')

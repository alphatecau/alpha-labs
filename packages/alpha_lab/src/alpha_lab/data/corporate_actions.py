"""Point-in-time corporate-action declarations; research only."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
import re

from alpha_lab.domain.assets import AssetClass, Instrument

SCHEMA = 'alpha-labs.corporate-actions.v1'


class ActionType(str, Enum):
    SPLIT = 'split'
    CASH_DIVIDEND = 'cash_dividend'


def _utc(value):
    if type(value) is not datetime or value.utcoffset() != timedelta(0):
        raise ValueError('UTC-aware datetime required')
    return value.isoformat()


@dataclass(frozen=True)
class CorporateAction:
    symbol: str
    ex_date: date
    action_type: ActionType
    value: Decimal
    announced_at_utc: datetime
    recorded_at_utc: datetime
    source_reference: str
    currency: str = 'USD'

    def __post_init__(self):
        if not isinstance(self.symbol, str) or not re.fullmatch(
            r'[A-Z0-9][A-Z0-9._/-]{0,31}', self.symbol
        ):
            raise ValueError('Invalid symbol')

        if type(self.ex_date) is not date or not isinstance(
            self.action_type, ActionType
        ):
            raise ValueError('Invalid corporate-action type or date')

        if (
            type(self.value) is not Decimal
            or not self.value.is_finite()
            or self.value <= 0
        ):
            raise ValueError('Positive finite Decimal required')

        if self.action_type == ActionType.SPLIT and self.value == 1:
            raise ValueError('No-op split ratio')

        if self.currency != 'USD':
            raise ValueError('Only USD action records supported')

        _utc(self.announced_at_utc)
        _utc(self.recorded_at_utc)

        if self.recorded_at_utc < self.announced_at_utc:
            raise ValueError('Recorded before announcement')

        if not isinstance(self.source_reference, str) or not (
            0 < len(self.source_reference.strip()) <= 500
        ):
            raise ValueError('Source reference required')


def action_snapshot(instrument, actions, *, as_of_utc):
    """Reject future knowledge and duplicates; no source authentication."""
    if (
        not isinstance(instrument, Instrument)
        or instrument.asset_class not in (
            AssetClass.US_EQUITY, AssetClass.US_ETF
        )
    ):
        raise ValueError('US equity or ETF required')

    _utc(as_of_utc)
    records, seen = [], set()

    for action in actions:
        if not isinstance(action, CorporateAction) or (
            action.symbol != instrument.symbol
        ):
            raise ValueError('Action/instrument mismatch')

        if (
            action.announced_at_utc > as_of_utc
            or action.recorded_at_utc > as_of_utc
        ):
            raise ValueError('Look-ahead: action not yet known')

        key = (action.ex_date, action.action_type)
        if key in seen:
            raise ValueError('Duplicate action or unresolved correction')
        seen.add(key)

        records.append({
            'ex_date': action.ex_date.isoformat(),
            'action_type': action.action_type.value,
            'value': str(action.value),
            'currency': action.currency,
            'announced_at_utc': _utc(action.announced_at_utc),
            'recorded_at_utc': _utc(action.recorded_at_utc),
            'source_reference': action.source_reference.strip(),
        })

    records.sort(key=lambda x: (x['ex_date'], x['action_type']))
    snapshot = {
        'schema': SCHEMA,
        'symbol': instrument.symbol,
        'as_of_utc': _utc(as_of_utc),
        'events': records,
        'coverage_verified': False,
        'source_authenticity_verified': False,
        'corporate_actions_verified': False,
        'price_adjustments_verified': False,
        'trading_enabled': False,
    }

    canonical = json.dumps(
        snapshot, sort_keys=True, separators=(',', ':')
    ).encode()

    snapshot['metadata_sha256'] = sha256(canonical).hexdigest()
    return snapshot

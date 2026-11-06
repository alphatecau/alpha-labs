"""Multi-asset instrument metadata. Research only; no trading execution."""
from dataclasses import dataclass
from enum import Enum
import re

class AssetClass(str, Enum):
    CRYPTO_SPOT = 'crypto_spot'
    US_EQUITY = 'us_equity'
    US_ETF = 'us_etf'

@dataclass(frozen=True)
class Instrument:
    symbol: str
    asset_class: AssetClass
    venue: str
    quote_currency: str
    calendar: str

    def __post_init__(self):
        if not isinstance(self.asset_class, AssetClass):
            raise ValueError('Unsupported asset class')
        for value in (self.symbol, self.venue):
            if not isinstance(value, str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9._/-]{0,31}', value):
                raise ValueError('Invalid instrument identifier')
        if self.asset_class == AssetClass.CRYPTO_SPOT:
            if self.calendar != '24/7' or self.quote_currency not in {'USD', 'USDT', 'USDC', 'AUD'}:
                raise ValueError('Invalid crypto market configuration')
        elif self.calendar not in {'XNYS', 'XNAS'} or self.quote_currency != 'USD':
            raise ValueError('Invalid US equity market configuration')

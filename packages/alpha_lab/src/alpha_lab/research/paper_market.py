"""Explicit instrument and simulated-cost policy for a single USD paper journal."""
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
import re

from alpha_lab.research.coinbase_paper_book import PRODUCTS, executable


@dataclass(frozen=True)
class PaperMarket:
    name: str
    symbols: tuple[str, ...]
    accepts: Callable
    quantity_step: Decimal = Decimal("0.00000001")

    def __post_init__(self):
        if (not isinstance(self.name, str) or not re.fullmatch(r"[a-z0-9-]{1,60}", self.name)
                or not isinstance(self.symbols, tuple) or not 1 <= len(self.symbols) <= 30
                or not all(isinstance(s, str) and re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,19}", s) for s in self.symbols)
                or len(set(self.symbols)) != len(self.symbols) or not callable(self.accepts)
                or not isinstance(self.quantity_step, Decimal)
                or self.quantity_step not in (Decimal("0.00000001"), Decimal("1"))):
            raise ValueError("invalid paper market policy")


@dataclass(frozen=True)
class PaperCosts:
    fee: Decimal = Decimal("0.001")
    slippage: Decimal = Decimal("0.0005")

    def __post_init__(self):
        if not all(isinstance(value, Decimal) and value.is_finite() and Decimal("0") <= value <= Decimal("0.05")
                   for value in (self.fee, self.slippage)):
            raise ValueError("simulated cost rates must be finite fractions from 0 to 0.05")


COINBASE_MARKET = PaperMarket("coinbase-spot-usd-v1", PRODUCTS, executable)
DEFAULT_COSTS = PaperCosts()

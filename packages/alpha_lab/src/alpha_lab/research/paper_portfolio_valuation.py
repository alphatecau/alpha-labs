"""Read-only derived portfolio valuation; never trusts caller-provided exposure.

Research calculation only. A verified feed and persisted session risk baseline
are required before this may authorise any simulated fill.
"""
from dataclasses import dataclass
from decimal import Decimal
from alpha_lab.research.paper_simulator import number

@dataclass(frozen=True)
class DerivedPortfolio:
    nav: Decimal
    gross_notional: Decimal
    cash: Decimal
    position_values: dict

def derive_portfolio(ledger, observations):
    if not isinstance(observations, dict):
        raise ValueError("HALT: market observations required")
    cash=number(ledger.cash)
    gross=Decimal("0")
    values={}
    for symbol, quantity in ledger.positions.items():
        q=number(quantity)
        if q==0:
            continue
        if symbol not in observations:
            raise ValueError("HALT: missing independent mark")
        mark=number(observations[symbol])
        if mark<=0:
            raise ValueError("HALT: invalid independent mark")
        value=q*mark
        values[symbol]=value
        gross+=abs(value)
    nav=cash+sum(values.values(),Decimal("0"))
    if nav<=0 or cash<0:
        raise ValueError("HALT: invalid portfolio equity")
    return DerivedPortfolio(nav=nav,gross_notional=gross,cash=cash,position_values=values)

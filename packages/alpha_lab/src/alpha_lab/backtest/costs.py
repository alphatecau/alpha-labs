"""Modelled cost assumptions, never observed market execution costs."""
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class CostModel:
    fee_bps: Decimal = Decimal('10')
    adverse_slippage_bps: Decimal = Decimal('10')
    def __post_init__(self):
        if self.fee_bps<0 or self.adverse_slippage_bps<0 or self.fee_bps>=10000 or self.adverse_slippage_bps>=10000:
            raise ValueError('invalid bps cost')
    def buy_price(self, price): return price*(1+self.adverse_slippage_bps/10000)
    def sell_price(self, price): return price*(1-self.adverse_slippage_bps/10000)
    def buy_quantity(self, quote_budget, price):
        execution_price=self.buy_price(price)
        return quote_budget/(execution_price*(1+self.fee_bps/10000))
    def buy_outlay(self, qty, price):
        notional=qty*self.buy_price(price)
        return notional*(1+self.fee_bps/10000)
    def sell_proceeds(self, qty, price):
        return qty*self.sell_price(price)*(1-self.fee_bps/10000)
    def twice(self): return CostModel(self.fee_bps*2, self.adverse_slippage_bps*2)

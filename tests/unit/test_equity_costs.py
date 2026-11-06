import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal as D

from alpha_lab.research.equity_costs import (
    EquityCostScenario, estimate_equity_fill, estimate_short_borrow_cost
)


def scenario(**kwargs):
    values = dict(
        commission_per_order_usd=D('0'),
        commission_per_share_usd=D('0'),
        half_spread_bps=D('0'), slippage_bps=D('0'),
        impact_coefficient_bps=D('0'),
        max_participation_bps=D('500'),
    )
    values.update(kwargs)
    return EquityCostScenario(**values)


def fill(s=None, **kwargs):
    values = dict(side='BUY', shares=D('10'), mid_price_usd=D('100'),
                  average_daily_dollar_volume_usd=D('100000'))
    values.update(kwargs)
    return estimate_equity_fill(s if s is not None else scenario(), **values)


class EquityCostsTests(unittest.TestCase):
    def test_zero_cost_buy_and_sale(self):
        buy = fill()
        sell = fill(side='SELL')
        self.assertEqual(buy.cash_delta_usd, D('-1000'))
        self.assertEqual(sell.cash_delta_usd, D('1000'))
        self.assertEqual(buy.total_cost_usd, D('0'))
        self.assertFalse(buy.trading_enabled)
        self.assertFalse(buy.assumptions_verified)

    def test_commissions_are_dollars(self):
        s = scenario(commission_per_order_usd=D('2'),
                     commission_per_share_usd=D('0.05'))
        result = fill(s)
        self.assertEqual(result.commission_usd, D('2.50'))
        self.assertEqual(result.cash_delta_usd, D('-1002.50'))

    def test_bid_ask_and_slippage_symmetric(self):
        s = scenario(half_spread_bps=D('5'), slippage_bps=D('10'))
        buy, sell = fill(s), fill(s, side='SELL')
        self.assertEqual(buy.execution_price_usd, D('100.15'))
        self.assertEqual(sell.execution_price_usd, D('99.85'))
        self.assertEqual(buy.total_cost_usd, D('1.5'))
        self.assertEqual(sell.total_cost_usd, D('1.5'))

    def test_market_impact_monotonic(self):
        s = scenario(impact_coefficient_bps=D('100'))
        low = fill(s, average_daily_dollar_volume_usd=D('1000000'))
        high = fill(s, average_daily_dollar_volume_usd=D('20000'))
        self.assertGreater(high.impact_bps, low.impact_bps)
        self.assertGreater(high.total_cost_usd, low.total_cost_usd)

    def test_participation_limit(self):
        with self.assertRaises(ValueError):
            fill(average_daily_dollar_volume_usd=D('1000'))

    def test_invalid_input_rejected(self):
        for value in (D('-1'), D('NaN'), D('Infinity'), D('0')):
            with self.subTest(value=str(value)), self.assertRaises(ValueError):
                fill(mid_price_usd=value)
        with self.assertRaises(ValueError):
            fill(mid_price_usd=100)
        with self.assertRaises(ValueError):
            fill(average_daily_dollar_volume_usd=D('0'))
        with self.assertRaises(ValueError):
            scenario(slippage_bps=D('-1'))
        with self.assertRaises(ValueError):
            scenario(half_spread_bps=D('10000'))

    def test_side_and_fractional_shares_rejected(self):
        with self.assertRaises(ValueError):
            fill(side='SHORT')
        with self.assertRaises(ValueError):
            fill(shares=D('0.5'))
        with self.assertRaises(ValueError):
            fill(shares=D('0'))

    def test_excessive_commission_rejected_on_sell(self):
        with self.assertRaises(ValueError):
            fill(scenario(commission_per_order_usd=D('2000')), side='SELL')

    def test_cost_stress_degrades_buy_and_sell(self):
        low = scenario(half_spread_bps=D('3'), slippage_bps=D('2'))
        high = scenario(half_spread_bps=D('10'), slippage_bps=D('20'))
        self.assertLess(fill(high).cash_delta_usd, fill(low).cash_delta_usd)
        self.assertLess(fill(high, side='SELL').cash_delta_usd,
                        fill(low, side='SELL').cash_delta_usd)

    def test_hypothetical_short_borrow(self):
        estimate = estimate_short_borrow_cost(
            short_notional_usd=D('10000'), annual_borrow_bps=D('365'),
            holding_days=D('10'))
        self.assertEqual(estimate.cost_usd, D('10'))
        self.assertFalse(estimate.short_execution_supported)
        self.assertFalse(estimate.trading_enabled)
        with self.assertRaises(ValueError):
            estimate_short_borrow_cost(short_notional_usd=D('10000'),
                                       annual_borrow_bps=D('-5'),
                                       holding_days=D('10'))

    def test_immutable_results(self):
        estimate = fill()
        with self.assertRaises(FrozenInstanceError):
            estimate.cash_delta_usd = D('0')


if __name__ == '__main__':
    unittest.main()

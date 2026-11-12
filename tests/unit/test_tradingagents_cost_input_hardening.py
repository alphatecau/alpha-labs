import unittest
from decimal import Decimal
from alpha_lab.backtest.costs import CostModel


class CostInputHardeningTests(unittest.TestCase):
    def test_exact_string_and_integer_inputs_normalised(self):
        for raw in ('12.5', 12, Decimal('12.5')):
            with self.subTest(raw=raw):
                model = CostModel(raw, '2.5')
                self.assertIsInstance(model.fee_bps, Decimal)
                self.assertIsInstance(model.adverse_slippage_bps, Decimal)
                self.assertEqual(model.buy_price(Decimal('100')), Decimal('100.025'))

    def test_reject_binary_float_bool_nonfinite_and_out_of_range(self):
        for raw in (True, 0.1, float('nan'), 'NaN', 'Infinity', '-1', '10000'):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    CostModel(raw, Decimal('1'))
                with self.assertRaises(ValueError):
                    CostModel(Decimal('1'), raw)

    def test_twice_preserves_exact_decimal(self):
        doubled = CostModel('12.5', '3.25').twice()
        self.assertEqual(doubled.fee_bps, Decimal('25'))
        self.assertEqual(doubled.adverse_slippage_bps, Decimal('6.50'))


if __name__ == '__main__':
    unittest.main()

"""Research-only regression tests for fill identity and currency guard."""
import unittest
from alpha_lab.research.phase1_accounting import reconstruct


class FillIdentityFeeGuardTests(unittest.TestCase):
    def setUp(self):
        self.fill = {"symbol":"BTC","side":"BUY","quantity":"1",
                     "price":"10","fee":"0.1","cash_delta":"-10.1"}

    def test_repeated_fill_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate fill identifier"):
            reconstruct([{**self.fill,"fill_id":"venue-123"},
                         {**self.fill,"fill_id":"venue-123"}],
                        {"BTC":"10"},starting_cash="100")

    def test_distinct_partial_fill_ids_accepted(self):
        result = reconstruct([{**self.fill,"fill_id":"venue-123"},
                              {**self.fill,"fill_id":"venue-124"}],
                             {"BTC":"10"},starting_cash="100")
        self.assertEqual(result["positions"]["BTC"],"2")

    def test_empty_or_nonstring_id_rejected(self):
        for bad in ("", "  ", None, 123):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError,"Invalid fill identifier"):
                reconstruct([{**self.fill,"fill_id":bad}],{"BTC":"10"},starting_cash="100")

    def test_foreign_fee_currency_fails_closed(self):
        for currency in ("BNB","USD",None,""):
            with self.subTest(currency=currency), self.assertRaisesRegex(ValueError,"Fee currency unsupported"):
                reconstruct([{**self.fill,"fee_currency":currency}],
                            {"BTC":"10"},starting_cash="100")

    def test_unidentified_legacy_fills_remain_supported(self):
        result = reconstruct([self.fill],{"BTC":"10"},starting_cash="100")
        self.assertEqual(result["order_count"],1)

    def test_duplicate_unidentified_fills_are_not_certified(self):
        # Legacy compatibility only: without a venue fill ID, duplicates cannot be detected.
        result = reconstruct([self.fill,self.fill],{"BTC":"10"},starting_cash="100")
        self.assertEqual(result["order_count"],2)


if __name__=="__main__":
    unittest.main()

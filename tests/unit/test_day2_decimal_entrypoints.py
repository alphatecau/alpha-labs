"""Adversarial decimal limits applied at public accounting entrypoints."""
import unittest
from alpha_lab.research.phase1_accounting import D, reconstruct
from alpha_lab.research.pnl_reporting import report_pnl


class DecimalEntryPointTests(unittest.TestCase):
    def test_rejects_boolean_excessive_precision_and_magnitude(self):
        for value, message in (
            (True, "Boolean"),
            ("1" * 29, "precision"),
            ("1e19", "magnitude"),
        ):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, message):
                D(value)

    def test_rejects_bad_fill_values_in_both_entrypoints(self):
        for bad in ("1" * 29, "1e19", True):
            order = {"fill_id": "fixture", "symbol": "BTC", "side": "BUY",
                     "quantity": bad, "price": "100", "fee": "1",
                     "cash_delta": "-101"}
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    reconstruct([order], {"BTC": "100"}, starting_cash="1000")
                with self.assertRaises(ValueError):
                    report_pnl([order], {"BTC": "100"}, starting_cash="1000")

    def test_rejects_bad_closing_marks_and_initial_cash(self):
        for bad in ("1e19", "1" * 29, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                reconstruct([], {"BTC": bad}, starting_cash="1000")
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                report_pnl([], {"BTC": "100"}, starting_cash=bad)


if __name__ == "__main__":
    unittest.main()

"""Decimal boundary and explicit settlement-rounding policy tests."""
import unittest
from decimal import Decimal
from alpha_lab.research.accounting_numeric_policy import bounded_decimal, quantise_aud


class NumericPolicyTests(unittest.TestCase):
    def test_bounded_inputs(self):
        self.assertEqual(bounded_decimal("0.00000001"), Decimal("0.00000001"))
        for value, message in [
            ("1" * 29, "precision"), ("1e19", "magnitude"),
            ("NaN", "Nonfinite"), ("Infinity", "Nonfinite"),
            (True, "Boolean"), ("-1", "Negative"),
        ]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, message):
                bounded_decimal(value)

    def test_round_half_even_aud_boundary(self):
        self.assertEqual(quantise_aud("1.005"), Decimal("1.00"))
        self.assertEqual(quantise_aud("1.015"), Decimal("1.02"))
        self.assertEqual(quantise_aud("-1.015"), Decimal("-1.02"))
        self.assertEqual(quantise_aud("0.004"), Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()

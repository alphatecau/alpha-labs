"""Offline independent statement and provenance truthfulness checks."""
import unittest
from alpha_lab.research.accounting_evidence import (
    canonical_digest, evidence_envelope, reconcile_statement,
)


class AccountingEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.orders = [
            {"fill_id": "fixture-buy", "symbol": "BTC", "side": "BUY",
             "quantity": "2", "price": "100", "fee": "1", "cash_delta": "-201"},
            {"fill_id": "fixture-sell", "symbol": "BTC", "side": "SELL",
             "quantity": "0.5", "price": "120", "fee": "0.3", "cash_delta": "59.7"},
        ]
        self.marks = {"BTC": "110"}
        self.statement = {"final_cash": "858.7",
                          "final_liquidation_nav": "1023.2875",
                          "total_fees": "1.3"}

    def test_independent_statement_matches_but_is_not_authenticated(self):
        result = reconcile_statement(self.orders, self.marks, self.statement,
                                     starting_cash="1000", liquidation_bps="25")
        self.assertTrue(result["reconciled"])
        self.assertFalse(result["authenticated"])
        self.assertFalse(result["promotion_eligible"])

    def test_mismatched_or_missing_statement_fails_closed(self):
        for field in self.statement:
            altered = dict(self.statement)
            altered[field] = "0"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "mismatch"):
                reconcile_statement(self.orders, self.marks, altered,
                                    starting_cash="1000", liquidation_bps="25")
        with self.assertRaisesRegex(ValueError, "missing"):
            reconcile_statement(self.orders, self.marks, {},
                                starting_cash="1000", liquidation_bps="25")

    def test_strict_identifier_and_untrusted_source(self):
        with self.assertRaisesRegex(ValueError, "Missing required fill"):
            reconcile_statement([{k:v for k,v in self.orders[0].items()
                                  if k != "fill_id"}], self.marks, self.statement,
                                starting_cash="1000", liquidation_bps="25")
        with self.assertRaisesRegex(ValueError, "signature"):
            evidence_envelope(self.orders, source_kind="AUTHENTICATED_EXTERNAL")
        envelope = evidence_envelope(self.orders)
        self.assertEqual(envelope["sha256"], canonical_digest(self.orders))
        self.assertFalse(envelope["authenticated"])
        self.assertFalse(envelope["promotion_eligible"])

    def test_digest_detects_mutated_evidence(self):
        changed = [dict(x) for x in self.orders]
        changed[0]["price"] = "101"
        self.assertNotEqual(canonical_digest(self.orders), canonical_digest(changed))


if __name__ == "__main__":
    unittest.main()

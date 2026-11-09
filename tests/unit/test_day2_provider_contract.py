"""Provider contract adversarial boundaries, synthetic research only."""
import unittest
from alpha_lab.research.accounting_evidence import evidence_envelope, reconcile_statement
from alpha_lab.research.phase1_accounting import reconstruct


class ProviderContractTests(unittest.TestCase):
    def test_cross_currency_fee_rejected(self):
        fill = {"fill_id": "x", "symbol": "BTC", "side": "BUY",
                "quantity": "1", "price": "100", "fee": "1",
                "fee_currency": "BTC", "cash_delta": "-101"}
        with self.assertRaisesRegex(ValueError, "Fee currency unsupported"):
            reconstruct([fill], {"BTC": "100"}, require_fill_ids=True)

    def test_unsupported_short_sale_rejected(self):
        fill = {"fill_id": "x", "symbol": "BTC", "side": "SELL",
                "quantity": "1", "price": "100", "fee": "0",
                "cash_delta": "100"}
        with self.assertRaisesRegex(ValueError, "Naked sale"):
            reconstruct([fill], {"BTC": "100"}, require_fill_ids=True)

    def test_external_evidence_never_self_certifies(self):
        evidence = evidence_envelope({"statement": "example"},
                                     source_kind="UNVERIFIED_EXTERNAL",
                                     source_reference="owner-supplied-fixture")
        self.assertFalse(evidence["authenticated"])
        self.assertFalse(evidence["promotion_eligible"])
        with self.assertRaisesRegex(ValueError, "signature"):
            evidence_envelope({"statement": "example"},
                              source_kind="AUTHENTICATED_EXTERNAL")

    def test_missing_statement_is_not_independent_evidence(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            reconcile_statement([], {"BTC": "100"}, {})


if __name__ == "__main__":
    unittest.main()

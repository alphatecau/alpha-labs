import unittest

from alpha_lab.research.local_multiasset_catalogue import (
    catalogue, eligible_for_order, lookup, Instrument,
)


class TestLocalMultiassetCatalogue(unittest.TestCase):
    def test_crypto_us_asx_etfs_present(self):
        self.assertEqual(lookup("BTC").asset_class, "crypto")
        self.assertEqual(lookup("SOL").quote_currency, "USD")
        self.assertEqual(lookup("AAPL").asset_class, "equity")
        self.assertEqual(lookup("SPY").asset_class, "etf")
        self.assertEqual(lookup("BHP").quote_currency, "AUD")
        self.assertEqual(lookup("VAS").asset_class, "etf")

    def test_no_instrument_is_paper_enabled_by_catalogue(self):
        for instrument in catalogue():
            self.assertEqual(instrument.data_status, "UNVERIFIED")
            self.assertEqual(instrument.order_status, "DISABLED")
            self.assertFalse(eligible_for_order(instrument,
                quote_verified=True, session_open=True,
                risk_approved=True, durable_journal=True))

    def test_unknown_instrument_fails_closed(self):
        with self.assertRaises(LookupError):
            lookup("FAKE")
        with self.assertRaises(ValueError):
            lookup("../../etc/passwd")

    def test_duplicate_symbols_are_disambiguated_by_venue(self):
        with self.assertRaises(LookupError):
            lookup("BHP", "NYSE")

    def test_invalid_registration_cannot_claim_verified_or_enabled(self):
        with self.assertRaises(ValueError):
            Instrument("BTC", "CRYPTO", "crypto", "USD",
                       data_status="VERIFIED")
        with self.assertRaises(ValueError):
            Instrument("BTC", "CRYPTO", "crypto", "USD",
                       order_status="PAPER_ENABLED")


if __name__ == "__main__":
    unittest.main()

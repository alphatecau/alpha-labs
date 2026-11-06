import unittest
from dataclasses import FrozenInstanceError
from alpha_lab.domain.assets import AssetClass, Instrument


class TestMultiAssetInstruments(unittest.TestCase):

    def test_supported_instruments(self):
        examples = (
            ("BTCUSDT", AssetClass.CRYPTO_SPOT, "BINANCE", "USDT", "24/7"),
            ("AAPL", AssetClass.US_EQUITY, "XNAS", "USD", "XNAS"),
            ("SPY", AssetClass.US_ETF, "ARCX", "USD", "XNYS"),
        )
        for symbol, asset, venue, currency, calendar in examples:
            with self.subTest(symbol=symbol):
                obj = Instrument(symbol, asset, venue, currency, calendar)
                self.assertEqual(obj.symbol, symbol)
                self.assertEqual(obj.asset_class, asset)

    def test_invalid_configurations(self):
        cases = (
            ("BTC", AssetClass.CRYPTO_SPOT, "BINANCE", "USDT", "XNYS"),
            ("AAPL", AssetClass.US_EQUITY, "XNAS", "USDT", "XNAS"),
            ("SPY", AssetClass.US_ETF, "ARCX", "USD", "24/7"),
            ("bad symbol", AssetClass.US_EQUITY, "XNAS", "USD", "XNAS"),
            ("AAPL", "unknown", "XNAS", "USD", "XNAS"),
        )
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    Instrument(*case)

    def test_immutable(self):
        obj = Instrument("AAPL", AssetClass.US_EQUITY, "XNAS", "USD", "XNAS")
        with self.assertRaises(FrozenInstanceError):
            obj.symbol = "MSFT"


if __name__ == "__main__":
    unittest.main()

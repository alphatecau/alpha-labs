import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from alpha_lab.research.strategies.regime_r1 import r1_signal
from tools.compare_regime_r1 import compare

class RegimeR1Tests(unittest.TestCase):
    def test_warmup_and_flat_prices(self):
        prices = [Decimal("100")] * 800
        self.assertEqual(r1_signal(prices), [False] * len(prices))

    def test_future_changes_cannot_modify_prior_signal(self):
        prices = [Decimal("100") + Decimal(i) / 100 for i in range(820)]
        a = r1_signal(prices)
        prices[-1] = Decimal("999")
        b = r1_signal(prices)
        self.assertEqual(a[:-1], b[:-1])

    def test_insufficient_history_stays_flat(self):
        self.assertEqual(r1_signal([Decimal("100")] * 768), [False] * 768)

    def test_nonpositive_rejected(self):
        with self.assertRaises(ValueError):
            r1_signal([Decimal("1"), Decimal("0")])

    def test_comparison_and_reserved_window(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "development.csv"
            def write_bars(year):
                start = datetime(year, 1, 1, tzinfo=timezone.utc)
                with path.open("w") as f:
                    f.write("timestamp,open,high,low,close,volume\n")
                    for i in range(1150):
                        price = 100 + i
                        f.write(f"{(start + timedelta(hours=i)).isoformat()},{price},{price},{price},{price},1\n")
            write_bars(2020)
            report = compare(path, "usdt", "synthetic fixture")
            self.assertEqual(report["quote"], "USDT")
            for fold in report["folds"].values():
                base = fold["reference"]["R1_PREREGISTERED"]
                stress = fold["double_cost"]["R1_PREREGISTERED"]
                self.assertGreater(base["orders"], 0)
                self.assertGreater(Decimal(base["pnl_quote"]), Decimal(stress["pnl_quote"]))
            # Calendar-boundary fixture with artificial constant-rule prices.
            write_bars(2027)
            with self.assertRaisesRegex(ValueError, "reserved"):
                compare(path, "USDT", "synthetic fixture")

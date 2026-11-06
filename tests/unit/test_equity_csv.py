import csv
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from alpha_lab.data.equity_csv import load_equity_csv
from alpha_lab.data.exchange_calendar_2026 import sessions_2026
from alpha_lab.domain.assets import AssetClass, Instrument

START, END = date(2026, 11, 25), date(2026, 11, 27)
STAMP = datetime(2026, 11, 28, tzinfo=timezone.utc)
AAPL = Instrument('AAPL', AssetClass.US_EQUITY, 'XNAS', 'USD', 'XNAS')
SPY = Instrument('SPY', AssetClass.US_ETF, 'ARCX', 'USD', 'XNYS')


class EquityCSVTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'market.csv'

    def rows(self):
        result = []
        for session in sessions_2026('XNAS', START, END):
            count = int((session.closes_utc-session.opens_utc)/timedelta(minutes=30))
            for i in range(count):
                stamp = session.opens_utc + timedelta(minutes=30*i)
                result.append([stamp.isoformat(), '100', '102', '99', '101', '1000'])
        return result

    def load(self, rows, instrument=AAPL, retrieved=STAMP):
        with self.path.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            writer.writerows(rows)
        return load_equity_csv(self.path, instrument=instrument,
                               start=START, end=END,
                               source_id='local-fixture-unverified',
                               retrieved_at_utc=retrieved)

    def test_equity_complete_sessions(self):
        result = self.load(self.rows())
        self.assertEqual(len(result.dataset.bars), 20)
        self.assertEqual(result.dataset.quote_currency, 'USD')
        self.assertFalse(result.source_authenticated)
        self.assertFalse(result.corporate_actions_verified)
        self.assertFalse(result.trading_enabled)

    def test_etf_accepted(self):
        self.assertEqual(self.load(self.rows(), SPY).instrument.symbol, 'SPY')

    def test_missing_session_bar_rejected(self):
        with self.assertRaises(ValueError):
            self.load(self.rows()[:-1])

    def test_out_of_session_timestamp_rejected(self):
        rows = self.rows()
        rows[0][0] = '2026-11-25T23:00:00+00:00'
        with self.assertRaises(ValueError):
            self.load(rows)

    def test_invalid_ohlcv_rejected(self):
        rows = self.rows()
        rows[0][5] = '-1'
        with self.assertRaises(ValueError):
            self.load(rows)

    def test_naive_timestamp_rejected(self):
        rows = self.rows()
        rows[0][0] = '2026-11-25T14:30:00'
        with self.assertRaises(ValueError):
            self.load(rows)

    def test_retrieval_before_close_rejected(self):
        with self.assertRaises(ValueError):
            self.load(self.rows(), retrieved=datetime(2026, 11, 25, tzinfo=timezone.utc))


if __name__ == '__main__':
    unittest.main()

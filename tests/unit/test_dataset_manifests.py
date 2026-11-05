"""Dataset-integrity tests; these deliberately do not certify market authenticity."""
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from alpha_lab.data.manifests import build_manifest, verify_manifest


class DatasetManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / 'candles.csv'
        self.start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with self.file.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            for i in range(100):
                t = self.start + timedelta(hours=i)
                writer.writerow([t.isoformat(), '99', '101', '98', '100', '20'])

    def make(self, **kwargs):
        args = dict(quote_currency='USD', interval_minutes=60,
                    source_class='exchange-public', source_id='kraken-public-ohlc',
                    venue='Kraken', instrument='SOL/USD',
                    retrieved_at_utc=(self.start + timedelta(hours=101)).isoformat())
        args.update(kwargs)
        return build_manifest(self.file, **args)

    def test_correct_file_verifies(self):
        m = self.make()
        self.assertEqual(m['candle_count'], 100)
        self.assertEqual(verify_manifest(self.file, m), m)
        self.assertFalse(m['price_source_authenticated'])
        self.assertFalse(m['trading_enabled'])

    def test_tampering_rejected(self):
        m = self.make()
        self.file.write_bytes(self.file.read_bytes().replace(b',100,20', b',100,21', 1))
        with self.assertRaises(ValueError):
            verify_manifest(self.file, m)

    def test_mismatched_symbol_rejected(self):
        m = self.make()
        m['instrument'] = 'BTC/USD'
        with self.assertRaises(ValueError):
            verify_manifest(self.file, m)

    def test_misleading_authentication_claims_rejected(self):
        m = self.make()
        m['independent_price_verification'] = True
        with self.assertRaises(ValueError):
            verify_manifest(self.file, m)

    def test_retrieval_before_history_rejected(self):
        with self.assertRaisesRegex(ValueError, 'predates'):
            self.make(retrieved_at_utc=self.start.isoformat())

    def test_unfinished_last_candle_rejected(self):
        with self.assertRaisesRegex(ValueError, 'complete candle'):
            self.make(retrieved_at_utc=(self.start + timedelta(hours=99, minutes=15)).isoformat())

    def test_missing_timezone_rejected(self):
        with self.assertRaisesRegex(ValueError, 'offset'):
            self.make(retrieved_at_utc='2026-01-12T10:00:00')

    def test_unknown_source_class_rejected(self):
        with self.assertRaises(ValueError):
            self.make(source_class='verified-by-guess')

    def test_injection_like_source_id_rejected(self):
        with self.assertRaises(ValueError):
            self.make(source_id='../../secrets')

    def test_missing_hour_rejected(self):
        m = self.make()
        rows = self.file.read_text().splitlines()
        self.file.write_text('\n'.join([*rows[:20], *rows[21:]]) + '\n')
        with self.assertRaises(ValueError):
            verify_manifest(self.file, m)


if __name__ == '__main__':
    unittest.main()

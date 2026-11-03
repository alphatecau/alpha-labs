"""Read-only market research bridge acceptance tests; no network required."""
import hashlib
import http.client
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread
import unittest

from tools.local_research_server import SCHEMA, create_server, load_snapshot


class LocalResearchServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'apps/sites').mkdir(parents=True)
        (self.root / 'apps/sites/index.html').write_text('TEST UI')
        csv = b'timestamp,open,high,low,close,volume\n'
        (self.root / 'solusd-recent.csv').write_bytes(csv)
        digest = hashlib.sha256(csv).hexdigest()
        stamp = datetime.now(timezone.utc) - timedelta(hours=1)
        self.manifest = {
            'requested_pair': 'SOLUSD', 'interval_minutes': 60, 'record_count': 720,
            'written_csv_sha256': digest, 'fetched_at_utc': stamp.isoformat(),
            'last_complete_candle_utc': (stamp - timedelta(hours=1)).isoformat(),
        }
        self.report = {
            'status': 'HYPOTHESIS_SCREEN_ONLY_NOT_VALIDATED_ALPHA',
            'configuration_sha256': 'c'*64,
            'dataset': {'sha256': digest, 'interval_minutes': 60, 'quote_currency': 'USD', 'bars': 720, 'provenance': 'kraken-public-ohlc'},
            'periods': {key: {
                'strategy': {'return_pct': -1.630},
                'equal_allocation_buy_hold': {'return_pct': -3.215},
                'double_cost_strategy': {'return_pct': -1.943}}
                for key in ['training', 'holdout']}
        }
        self.write()

    def write(self):
        (self.root / 'solusd-recent.csv.manifest.json').write_text(json.dumps(self.manifest))
        (self.root / 'solusd-research.json').write_text(json.dumps(self.report))

    def test_valid_snapshot_and_strict_read_only(self):
        s = load_snapshot(self.root)
        self.assertEqual(s['schema'], SCHEMA)
        self.assertFalse(s['trading_enabled'])
        self.assertEqual(s['periods']['training']['strategy_pct'], -1.630)
        self.assertEqual(s['status'], 'historical')
        server = create_server(self.root, 0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
            conn.request('GET', '/api/v1/research/solusd')
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertFalse(json.loads(response.read())['trading_enabled'])
            conn.close()
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
            conn.request('POST', '/api/v1/research/solusd')
            response = conn.getresponse()
            self.assertEqual(response.status, 405)
            response.read()
            conn.close()
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
            conn.request('GET', '/')
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b'TEST UI')
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_bad_hash_fails_closed(self):
        self.manifest['written_csv_sha256'] = '0'*64
        self.write()
        with self.assertRaisesRegex(ValueError, 'hashes'):
            load_snapshot(self.root)

    def test_stale_data_not_claimed_live(self):
        old = datetime.now(timezone.utc) - timedelta(hours=6)
        self.manifest['fetched_at_utc'] = old.isoformat()
        self.manifest['last_complete_candle_utc'] = (old - timedelta(hours=1)).isoformat()
        self.write()
        self.assertEqual(load_snapshot(self.root)['status'], 'stale')

    def test_wrong_pair_fails_closed(self):
        self.manifest['requested_pair'] = 'ETHUSD'
        self.write()
        with self.assertRaisesRegex(ValueError, 'Inconsistent'):
            load_snapshot(self.root)


if __name__ == '__main__':
    unittest.main()

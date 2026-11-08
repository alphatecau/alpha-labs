import unittest
from datetime import datetime,timedelta,timezone,date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from alpha_lab.data.csv_import import Bar
from alpha_lab.research.phase1_daily_data import aggregate_crypto_utc_daily,verify_etf_csv

class DailyDataTests(unittest.TestCase):
    def test_complete_crypto_day(self):
        t=datetime(2025,1,1,tzinfo=timezone.utc)
        bars=[Bar(t+timedelta(hours=i),Decimal("100"),Decimal("102"),
                  Decimal("99"),Decimal("101"),Decimal("1")) for i in range(24)]
        d=aggregate_crypto_utc_daily(bars)
        self.assertEqual(d[0]["volume"],"24")
        self.assertEqual(d[0]["date"],"2025-01-01")
        with self.assertRaises(ValueError):
            aggregate_crypto_utc_daily(bars[:-1])
        bars[12]=bars[11]
        with self.assertRaises(ValueError):
            aggregate_crypto_utc_daily(bars)

    def test_etf_checksum_calendar_and_corporate_actions(self):
        content="date,symbol,adjusted_close,volume,corporate_actions_verified\n2025-01-02,SPY,100,1000,true\n"
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"SPY.csv"
            p.write_text(content)
            digest=sha256(content.encode()).hexdigest()
            self.assertEqual(verify_etf_csv(p,expected_symbol="SPY",
                expected_sha256=digest,calendar_sessions={date(2025,1,2)})["rows"],1)
            with self.assertRaisesRegex(ValueError,"checksum"):
                verify_etf_csv(p,expected_symbol="SPY",expected_sha256="0"*64,
                               calendar_sessions={date(2025,1,2)})
            with self.assertRaisesRegex(ValueError,"Missing ETF sessions"):
                verify_etf_csv(p,expected_symbol="SPY",expected_sha256=digest,
                               calendar_sessions={date(2025,1,2),date(2025,1,3)})
            p.write_text(content.replace("true","false"))
            with self.assertRaisesRegex(ValueError,"corporate-action"):
                verify_etf_csv(p,expected_symbol="SPY",
                    expected_sha256=sha256(p.read_bytes()).hexdigest(),
                    calendar_sessions={date(2025,1,2)})
if __name__=="__main__":unittest.main()

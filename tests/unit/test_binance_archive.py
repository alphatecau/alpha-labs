"""No network access; every source archive in this test is synthetic."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from archive_fixture import make_archive, two_month_transport
from alpha_lab.data.adapters.binance_archive import (BASE, archive_name, month_range,
    parse_archive, verify_checksum, build_dataset, verify_dataset)

class ArchiveResearchTests(unittest.TestCase):
    def test_month_range_inclusive_and_bad_date(self):
        self.assertEqual(month_range("2024-12","2025-02"), [(2024,12),(2025,1),(2025,2)])
        for start,end in [("2024-13","2025-02"),("2025-01","2024-12"),("2025-1","2025-02")]:
            with self.subTest(start=start,end=end),self.assertRaises(ValueError): month_range(start,end)

    def test_timestamp_conversion_pre_and_post_2025(self):
        for year,month in [(2024,12),(2025,1)]:
            assets=make_archive(year=year,month=month)
            data=assets[next(u for u in assets if u.endswith(".zip"))]
            candles=parse_archive(data,"BTCUSDT",year,month)
            self.assertEqual(candles[0][0],f"{year:04d}-{month:02d}-01T00:00:00+00:00")
            self.assertEqual(len(candles),31*24)

    def test_missing_candle_rejected(self):
        assets=make_archive(omit_hour=100)
        with self.assertRaisesRegex(ValueError,"Missing|out-of-month|reordered"):
            parse_archive(assets[next(u for u in assets if u.endswith('.zip'))],"BTCUSDT",2024,12)

    def test_2025_millisecond_error_rejected(self):
        assets=make_archive(year=2025,month=1,invalid_units=True)
        with self.assertRaisesRegex(ValueError,"Invalid kline"):
            parse_archive(assets[next(u for u in assets if u.endswith('.zip'))],"BTCUSDT",2025,1)

    def test_bad_price_rejected(self):
        assets=make_archive(wrong_price=True)
        with self.assertRaisesRegex(ValueError,"OHLCV"):
            parse_archive(assets[next(u for u in assets if u.endswith('.zip'))],"BTCUSDT",2024,12)

    def test_zip_member_enforcement(self):
        for kw in ({"wrong_name":True},{"extra_member":True}):
            assets=make_archive(**kw)
            with self.assertRaisesRegex(ValueError,"Unexpected ZIP"):
                parse_archive(assets[next(u for u in assets if u.endswith('.zip'))],"BTCUSDT",2024,12)

    def test_checksum_fails_on_bad_hash_or_filename(self):
        assets=make_archive()
        name=archive_name("BTCUSDT",2024,12)
        z=assets[next(u for u in assets if u.endswith('.zip'))]
        check=assets[next(u for u in assets if u.endswith('.CHECKSUM'))]
        self.assertEqual(verify_checksum(z,check,name),hashlib.sha256(z).hexdigest())
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            verify_checksum(z+b"extra",check,name)
        with self.assertRaisesRegex(ValueError,"filename"):
            verify_checksum(z,check,"ETHUSDT-1h-2024-12.zip")

    def test_offline_assembly_and_reverification(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"datasets"
            transport,_=two_month_transport()
            result=build_dataset("BTCUSDT","2024-12","2025-01",root,transport=transport)
            manifest=verify_dataset(Path(result["csv"]),Path(result["manifest"]))
            self.assertEqual(result["bars"],1488)
            self.assertTrue(manifest["source_archive_checksums_verified"])
            self.assertFalse(manifest["independent_price_crosscheck_performed"])
            self.assertEqual(result["months"],2)
            with self.assertRaises(FileExistsError):
                build_dataset("BTCUSDT","2024-12","2025-01",root,transport=transport)

    def test_changed_csv_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            transport,_=two_month_transport()
            result=build_dataset("BTCUSDT","2024-12","2025-01",Path(temp),transport=transport)
            csv_file=Path(result["csv"])
            csv_file.write_text(csv_file.read_text().replace("100.000000","999.000000",1))
            with self.assertRaises(ValueError):verify_dataset(csv_file,Path(result["manifest"]))

    def test_changed_raw_archive_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            transport,_=two_month_transport()
            result=build_dataset("BTCUSDT","2024-12","2025-01",Path(temp),transport=transport)
            raw=Path(temp)/"raw/binance-vision/spot-monthly-1h/BTCUSDT/BTCUSDT-1h-2024-12.zip"
            raw.write_bytes(raw.read_bytes()+b"tampered")
            with self.assertRaises(ValueError):verify_dataset(Path(result["csv"]),Path(result["manifest"]))

    def test_missing_checksum_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            _,assets=two_month_transport()
            def no_checksum(url):
                if url.endswith(".CHECKSUM"): raise FileNotFoundError(url)
                return assets[url]
            with self.assertRaises(FileNotFoundError):
                build_dataset("BTCUSDT","2024-12","2025-01",Path(temp),transport=no_checksum)
            self.assertFalse(list((Path(temp)/"curated").rglob('*.csv')))

if __name__=='__main__':unittest.main()

"""Regression tests for checksum-valid archive rows with early close metadata.

All archives in these tests are synthetic. No market data is downloaded.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

from archive_fixture import make_archive
from alpha_lab.data.adapters.binance_archive import (
    archive_name, build_dataset, parse_archive, verify_dataset, fetch_month,
)


def altered_archive(*, year=2023, month=1, row=565, change="early"):
    data = make_archive(year=year, month=month)
    archive_url = next(k for k in data if k.endswith(".zip"))
    original = data[archive_url]
    with ZipFile(io.BytesIO(original)) as zip_in:
        content = zip_in.read(zip_in.namelist()[0]).decode("utf-8")
    rows = list(csv.reader(io.StringIO(content)))
    stamp = int(rows[row - 1][0])
    factor = 1_000_000 if year >= 2025 else 1000
    if change == "early":
        rows[row - 1][6] = str(stamp + 3600 * factor - 19000 * (factor // 1000))
    elif change == "outside":
        rows[row - 1][6] = str(stamp + 3700 * factor)
    elif change == "mixed_units":
        rows[row - 1][6] = str((stamp + 3600 * factor - 1) // 1000)
    else:
        raise ValueError(change)
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as zip_out:
        zip_out.writestr(archive_name("BTCUSDT", year, month).replace(".zip", ".csv"), buffer.getvalue())
    zipped = output.getvalue()
    data[archive_url] = zipped
    data[archive_url + ".CHECKSUM"] = (
        f"{hashlib.sha256(zipped).hexdigest()}  {archive_name('BTCUSDT', year, month)}\n"
    ).encode("ascii")
    return data


class BinanceCloseMetadataTests(unittest.TestCase):
    def test_early_close_is_explicitly_logged_at_row_565(self):
        data = altered_archive()
        z = data[next(u for u in data if u.endswith(".zip"))]
        log = []
        bars = parse_archive(z, "BTCUSDT", 2023, 1, anomalies=log)
        self.assertEqual(len(bars), 744)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["row"], 565)
        self.assertEqual(log[0]["timestamp_unit"], "ms")
        self.assertTrue(log[0]["requires_independent_review"])
        # Without a source ledger this anomaly must never be silently ignored.
        with self.assertRaisesRegex(ValueError, "requires an explicit anomaly ledger"):
            parse_archive(z, "BTCUSDT", 2023, 1)

    def test_early_microsecond_close_in_2025_is_recorded(self):
        data = altered_archive(year=2025, month=1)
        log = []
        rows = parse_archive(data[next(u for u in data if u.endswith(".zip"))], "BTCUSDT", 2025, 1, anomalies=log)
        self.assertEqual(len(rows), 744)
        self.assertEqual(log[0]["timestamp_unit"], "us")
        self.assertEqual(log[0]["earliness_in_source_units"], 18_999_999)

    def test_outside_interval_and_mixed_units_rejected(self):
        for change in ("outside", "mixed_units"):
            with self.subTest(change=change):
                data = altered_archive(change=change)
                with self.assertRaisesRegex(ValueError, "Incorrect close timestamp"):
                    parse_archive(data[next(u for u in data if u.endswith(".zip"))],
                                  "BTCUSDT", 2023, 1, anomalies=[])

    def test_dataset_reports_anomalies_and_verifies_source(self):
        data = altered_archive()
        def transport(url):
            return data[url]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "datasets"
            result = build_dataset("BTCUSDT", "2023-01", "2023-01", root, transport=transport)
            doc = verify_dataset(Path(result["csv"]), Path(result["manifest"]))
            self.assertEqual(doc["source_close_timestamp_anomaly_count"], 1)
            self.assertTrue(doc["source_close_timestamp_anomalies_require_review"])
            self.assertEqual(doc["source_archives"][0]["close_timestamp_anomalies"][0]["row"], 565)
            altered_doc = json.loads(Path(result["manifest"]).read_text())
            altered_doc["source_archives"][0]["close_timestamp_anomalies"] = []
            Path(result["manifest"]).write_text(json.dumps(altered_doc))
            with self.assertRaises(ValueError):
                verify_dataset(Path(result["csv"]), Path(result["manifest"]))

    def test_checksum_verified_archive_kept_when_contents_invalid(self):
        data = altered_archive(change="outside")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            with self.assertRaisesRegex(ValueError, "Incorrect close timestamp"):
                fetch_month("BTCUSDT", 2023, 1, folder, transport=lambda url: data[url])
            name = archive_name("BTCUSDT", 2023, 1)
            self.assertTrue((folder / "BTCUSDT" / name).exists())
            self.assertTrue((folder / "BTCUSDT" / (name + ".CHECKSUM")).exists())
            with self.assertRaisesRegex(ValueError, "Incorrect close timestamp"):
                fetch_month("BTCUSDT", 2023, 1, folder,
                            transport=lambda url: (_ for _ in ()).throw(AssertionError("should use cached zip")))

    def test_missing_candle_still_rejected(self):
        data = make_archive(year=2023, month=1, omit_hour=565)
        with self.assertRaisesRegex(ValueError, "Missing, duplicated"):
            parse_archive(data[next(u for u in data if u.endswith(".zip"))],
                          "BTCUSDT", 2023, 1, anomalies=[])


if __name__ == "__main__":
    unittest.main()

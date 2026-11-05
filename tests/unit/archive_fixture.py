"""Deterministic fake Binance ZIPs for offline test; not real market data."""
from calendar import monthrange
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
from zipfile import ZipFile, ZIP_DEFLATED

from alpha_lab.data.adapters.binance_archive import BASE, archive_name


def make_archive(symbol="BTCUSDT", year=2024, month=12, *, omit_hour=None,
                 invalid_units=False, wrong_price=False, extra_member=False,
                 wrong_name=False, header=False):
    factors = 1000 if (year < 2025 or invalid_units) else 1_000_000
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    rows = []
    if header:
        rows.append(["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore"])
    for i in range(monthrange(year, month)[1] * 24):
        if i == omit_hour:
            continue
        stamp = int((start + timedelta(hours=i)).timestamp()) * factors
        price = 100 + i * .003
        close = price + (.01 if i % 12 < 9 else -.03)
        high = max(price, close) + .10
        low = min(price, close) - .10
        if i == 30 and wrong_price:
            high = 2
        rows.append([stamp, f"{price:.6f}", f"{high:.6f}", f"{low:.6f}", f"{close:.6f}", "5.0", stamp+factors*3600-1, "100.0", "10", "3", "20", "0"])
    content = io.StringIO()
    writer=csv.writer(content,lineterminator="\n")
    writer.writerows(rows)
    filename = archive_name(symbol,year,month)
    filebuf = io.BytesIO()
    with ZipFile(filebuf, "w", ZIP_DEFLATED) as zf:
        zf.writestr("evil.csv" if wrong_name else filename.replace(".zip", ".csv"), content.getvalue())
        if extra_member:
            zf.writestr("second.txt", "extra")
    zipped = filebuf.getvalue()
    checksum = f"{hashlib.sha256(zipped).hexdigest()}  {filename}\n".encode("ascii")
    url = f"{BASE}/{symbol}/1h/{filename}"
    return {url:zipped, url+".CHECKSUM":checksum}


def two_month_transport():
    assets={}
    assets.update(make_archive(year=2024,month=12))
    assets.update(make_archive(year=2025,month=1,header=True))
    def transport(url):
        if url not in assets:
            raise FileNotFoundError(url)
        return assets[url]
    return transport, assets

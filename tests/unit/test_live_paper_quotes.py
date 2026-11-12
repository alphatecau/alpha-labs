"""Offline tests: no network and no broker credentials."""
from datetime import datetime, timezone, timedelta
import pytest
from alpha_lab.research.live_paper_quotes import (
    parse_book_ticker, quote_is_fresh, simulated_fill_estimate, fetch_public_quote
)

NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)
PAYLOAD = {"symbol":"BTCUSDT","bidPrice":"100","askPrice":"101"}

def test_valid_quote_and_costs():
    q = parse_book_ticker(PAYLOAD, symbol="BTCUSDT", observed_at=NOW)
    assert str(q.mid) == "100.5"
    assert quote_is_fresh(q, now=NOW + timedelta(seconds=5))
    assert not quote_is_fresh(q, now=NOW + timedelta(seconds=11))
    buy = simulated_fill_estimate(q, side="BUY", quantity="1")
    sell = simulated_fill_estimate(q, side="SELL", quantity="1")
    assert buy["live_execution_authorised"] is False
    assert float(buy["executed_price"]) > 101
    assert float(sell["executed_price"]) < 100

@pytest.mark.parametrize("payload", [
    {"symbol":"ETHUSDT","bidPrice":"100","askPrice":"101"},
    {"symbol":"BTCUSDT","bidPrice":"102","askPrice":"101"},
    {"symbol":"BTCUSDT","bidPrice":"NaN","askPrice":"101"},
    {"symbol":"BTCUSDT","bidPrice":"0","askPrice":"101"},
])
def test_reject_invalid_quotes(payload):
    with pytest.raises(ValueError):
        parse_book_ticker(payload, symbol="BTCUSDT", observed_at=NOW)

def test_no_unapproved_symbols_or_naive_timestamps():
    with pytest.raises(ValueError):
        fetch_public_quote("DOGEUSDT")
    with pytest.raises(ValueError):
        parse_book_ticker(PAYLOAD, symbol="BTCUSDT", observed_at=NOW.replace(tzinfo=None))

def test_no_live_execution_side_effect():
    q = parse_book_ticker(PAYLOAD, symbol="BTCUSDT", observed_at=NOW)
    with pytest.raises(ValueError):
        simulated_fill_estimate(q, side="SHORT", quantity="1")
    with pytest.raises(ValueError):
        simulated_fill_estimate(q, side="BUY", quantity="-1")

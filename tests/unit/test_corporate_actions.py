import unittest
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

from alpha_lab.data.corporate_actions import (
    ActionType, CorporateAction, action_snapshot
)
from alpha_lab.domain.assets import AssetClass, Instrument

AAPL = Instrument('AAPL', AssetClass.US_EQUITY, 'XNAS', 'USD', 'XNAS')
BTC = Instrument(
    'BTCUSDT', AssetClass.CRYPTO_SPOT, 'BINANCE', 'USDT', '24/7'
)
T0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 5, 2, tzinfo=timezone.utc)
T2 = datetime(2026, 5, 3, tzinfo=timezone.utc)


def action(kind=ActionType.SPLIT, value=Decimal('2'), **kwargs):
    fields = dict(
        symbol='AAPL',
        ex_date=date(2026, 5, 4),
        action_type=kind,
        value=value,
        announced_at_utc=T0,
        recorded_at_utc=T1,
        source_reference='unverified-test-source',
    )
    fields.update(kwargs)
    return CorporateAction(**fields)


class CorporateActionTests(unittest.TestCase):
    def test_valid_split_snapshot(self):
        record = action_snapshot(AAPL, [action()], as_of_utc=T2)
        self.assertEqual(record['events'][0]['value'], '2')
        self.assertEqual(record['events'][0]['action_type'], 'split')
        self.assertFalse(record['corporate_actions_verified'])
        self.assertFalse(record['coverage_verified'])
        self.assertFalse(record['trading_enabled'])
        self.assertEqual(len(record['metadata_sha256']), 64)

    def test_dividend(self):
        record = action_snapshot(
            AAPL, [action(ActionType.CASH_DIVIDEND, Decimal('0.25'))],
            as_of_utc=T2
        )
        self.assertEqual(record['events'][0]['value'], '0.25')

    def test_future_knowledge_rejected(self):
        with self.assertRaises(ValueError):
            action_snapshot(AAPL, [action()], as_of_utc=T0)

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            action_snapshot(AAPL, [action(), action()], as_of_utc=T2)

    def test_other_symbol_rejected(self):
        with self.assertRaises(ValueError):
            action_snapshot(
                AAPL, [action(symbol='MSFT')], as_of_utc=T2
            )

    def test_invalid_amounts_rejected(self):
        for amount in (
            Decimal('0'), Decimal('-1'),
            Decimal('NaN'), Decimal('Infinity')
        ):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    action(value=amount)
        with self.assertRaises(ValueError):
            action(value=Decimal('1'))

    def test_time_provenance_rejected(self):
        with self.assertRaises(ValueError):
            action(recorded_at_utc=datetime(2026, 5, 1))
        with self.assertRaises(ValueError):
            action(recorded_at_utc=T0-timedelta(hours=1))
        with self.assertRaises(ValueError):
            action_snapshot(
                AAPL, [action()], as_of_utc=datetime(2026, 5, 3)
            )

    def test_invalid_source_and_crypto_rejected(self):
        with self.assertRaises(ValueError):
            action(source_reference=' ')
        with self.assertRaises(ValueError):
            action_snapshot(BTC, [], as_of_utc=T2)


if __name__ == '__main__':
    unittest.main()

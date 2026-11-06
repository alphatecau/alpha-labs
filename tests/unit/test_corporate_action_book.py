import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from alpha_lab.accounting.corporate_action_book import CorporateActionBook, apply_at_ex_open
from alpha_lab.data.corporate_actions import CorporateAction, ActionType
from alpha_lab.data.exchange_calendar_2026 import sessions_2026
from alpha_lab.domain.assets import AssetClass, Instrument

AAPL=Instrument('AAPL',AssetClass.US_EQUITY,'XNAS','USD','XNAS')
BTC=Instrument('BTCUSDT',AssetClass.CRYPTO_SPOT,'BINANCE','USDT','24/7')
EX=date(2026,11,25)
OPEN=sessions_2026('XNAS',EX,EX)[0].opens_utc


def book(shares=Decimal('10')):
    return CorporateActionBook('AAPL',shares,shares*Decimal('100'),Decimal('500'))


def action(kind=ActionType.SPLIT,value=Decimal('2'),**overrides):
    d=dict(symbol='AAPL',ex_date=EX,action_type=kind,value=value,announced_at_utc=OPEN-timedelta(days=4),recorded_at_utc=OPEN-timedelta(days=3),source_reference='synthetic fixture')
    d.update(overrides)
    return CorporateAction(**d)


def apply(b,a,**kwargs):
    return apply_at_ex_open(b,AAPL,a,at_utc=OPEN,price_basis='raw',**kwargs)

class BookTests(unittest.TestCase):
    def test_forward_split_preserves_basis_cash(self):
        x=apply(book(),action())
        self.assertEqual((x.shares,x.total_cost_usd,x.cash_usd,x.dividend_receivable_usd),(Decimal('20'),Decimal('1000'),Decimal('500'),Decimal('0')))
    def test_reverse_split_fractional_rejected(self):
        self.assertEqual(apply(book(),action(value=Decimal('0.5'))).shares,Decimal('5'))
        with self.assertRaises(ValueError): apply(book(),action(value=Decimal('0.25')))
    def test_dividend_receivable_no_cash(self):
        x=apply(book(),action(ActionType.CASH_DIVIDEND,Decimal('0.25')))
        self.assertEqual(x.dividend_receivable_usd,Decimal('2.50'))
        self.assertEqual(x.cash_usd,Decimal('500'))
    def test_adjusted_prices_rejected(self):
        for p in ('unknown','split_adjusted','total_return_adjusted'):
            with self.subTest(p=p),self.assertRaises(ValueError):
                apply_at_ex_open(book(),AAPL,action(),at_utc=OPEN,price_basis=p)
    def test_future_record_rejected(self):
        with self.assertRaises(ValueError): apply(book(),action(recorded_at_utc=OPEN+timedelta(hours=1)))
    def test_exact_ex_open_required(self):
        for time in (OPEN-timedelta(minutes=1),OPEN+timedelta(minutes=1)):
            with self.assertRaises(ValueError):
                apply_at_ex_open(book(),AAPL,action(),at_utc=time,price_basis='raw')
    def test_duplicate_and_same_day_conflict_rejected(self):
        x=apply(book(),action())
        for a in (action(),action(ActionType.CASH_DIVIDEND,Decimal('0.25'))):
            with self.assertRaises(ValueError): apply(x,a)
    def test_instrument_mismatch_and_invalid_book(self):
        with self.assertRaises(ValueError):
            apply_at_ex_open(book(),BTC,action(),at_utc=OPEN,price_basis='raw')
        with self.assertRaises(ValueError):
            apply(CorporateActionBook('MSFT',Decimal('1'),Decimal('100'),Decimal('1')),action())
        with self.assertRaises(ValueError):
            book(Decimal('0.5'))

if __name__=='__main__':unittest.main()

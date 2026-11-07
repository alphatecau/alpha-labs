import asyncio
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal as D
import unittest

from alpha_lab.paper.api import strict_json
from alpha_lab.paper.brokers import execution_transport, UnavailableBroker
from alpha_lab.paper.contracts import ContractError, Mode, number, utc
from alpha_lab.paper.market_data import MarketDataGateway, MarketDataUnavailable, Provenance
from alpha_lab.paper.risk import Limits
from fixtures import NOW, quote


class ContractTests(unittest.TestCase):
    def test_immutable_quote(self):
        with self.assertRaises(FrozenInstanceError):
            quote().bid = D('101')

    def test_quote_fresh_and_exact_event_age_boundary(self):
        quote().check(NOW, max_event_age_ms=1000)
        with self.assertRaises(ContractError):
            quote().check(NOW, max_event_age_ms=999)

    def test_old_event_recent_receipt_rejected(self):
        with self.assertRaises(ContractError):
            quote(event_time='2026-11-06T00:00:00Z').check(NOW)

    def test_exact_transport_boundary_and_one_microsecond_beyond(self):
        quote(received_time='2026-11-07T00:00:00.100000Z').check(NOW, max_transport_ms=100)
        with self.assertRaises(ContractError):
            quote(received_time='2026-11-07T00:00:00.100001Z').check(NOW, max_transport_ms=100)

    def test_submillisecond_ordering_not_truncated(self):
        with self.assertRaises(ContractError):
            quote(event_time='2026-11-07T00:00:00.100900Z', received_time='2026-11-07T00:00:00.100100Z')
        with self.assertRaises(ContractError):
            quote(received_time='2026-11-07T00:00:01.000900Z').check('2026-11-07T00:00:01.000100Z')

    def test_timestamp_schema(self):
        for value in ('2026-11-07', '2026-11-07T00:00:00+00:00', '2026-11-07T00:00:00.1234567Z', None):
            with self.subTest(value=value), self.assertRaises(ContractError):
                utc(value)

    def test_prices_sizes_and_crossing(self):
        for key, value in [('bid','101'),('ask','NaN'),('bid_size','0'),('ask_size','Infinity'),('ask',True)]:
            with self.subTest(key=key, value=value), self.assertRaises(ContractError):
                quote(**{key: value})

    def test_nonfinite_boolean_float_and_extreme_decimals_rejected(self):
        for value in (True, 0.1, 'NaN', 'Infinity', '1e100', '0.00000000000000000001'):
            with self.subTest(value=value), self.assertRaises(ContractError):
                number(value)

    def test_policy_cannot_be_relaxed(self):
        for key in ('position_loss','aggregate_stop_risk','daily_loss','drawdown','notional',
                    'concentration','total_exposure','weekly_loss','depth_fraction','price_deviation'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                Limits(**{key: '2'})
        self.assertEqual(Limits(position_loss='0.001').position_loss, D('0.001'))
        for n in (0, 11, True, 2.5):
            with self.subTest(n=n), self.assertRaises(ValueError):
                Limits(max_orders_per_minute=n)

    def test_strict_json_and_no_unknown_proposal_authority_fields(self):
        for text in ('{"a":1,"a":2}', '{"a":NaN}'):
            with self.assertRaises(ContractError):
                strict_json(text)

    def test_every_real_transport_is_blocked(self):
        for mode in Mode:
            if mode != Mode.SIMULATION:
                with self.subTest(mode=mode), self.assertRaises(PermissionError):
                    execution_transport(mode)
        for provider in ('binance','interactive-brokers'):
            adapter = UnavailableBroker(provider)
            self.assertFalse(adapter.health())
            with self.assertRaises(PermissionError):
                adapter.submit({'order':'forged'})


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_failover_validates_both_paths(self):
        class Provider:
            provenance = Provenance('fixture','fixture-1','synthetic-only')
            async def latest(self, instrument):
                return quote(event_time='2026-11-06T00:00:00Z')
        class Good(Provider):
            async def latest(self, instrument): return quote()
        q, incidents = await MarketDataGateway((Provider(),Good())).latest('TEST/AUD',NOW)
        self.assertEqual(q.instrument,'TEST/AUD')
        self.assertEqual(len(incidents),1)

    async def test_timeout_then_fail_closed(self):
        class Slow:
            provenance = Provenance('slow','fixture','none')
            async def latest(self, instrument):
                await asyncio.sleep(0.05)
                return quote()
        with self.assertRaises(MarketDataUnavailable):
            await MarketDataGateway((Slow(),), timeout_seconds=0.001).latest('TEST/AUD',NOW)

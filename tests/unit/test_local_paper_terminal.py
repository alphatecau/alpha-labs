"""Local CLI safety regression tests; no network, broker or real-money orders."""
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from alpha_lab.research.live_paper_session import LivePaperSession, PaperRejection
from alpha_lab.research.local_etf_fixture import ETF_FIXTURE_MARKET, ETF_SYMBOLS, SyntheticEtfFeed
from alpha_lab.research.local_paper_terminal import DEFAULT_ACCOUNT, command
from alpha_lab.research.paper_market import COINBASE_MARKET, PaperCosts


class TestLocalTerminal(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.session.market = COINBASE_MARKET

    def test_catalogue_is_not_order_enabled(self):
        result = command(self.session, "markets")
        self.assertGreater(len(result["catalogue"]), 50)
        self.assertEqual(result["paper_products"], ["BTC-USD", "ETH-USD", "SOL-USD"])
        self.assertTrue(all(i["order_status"] == "DISABLED" for i in result["catalogue"]))
        self.session.order.assert_not_called()

    def test_unknown_market_rejected_before_order(self):
        with self.assertRaisesRegex(ValueError, "unsupported paper market"):
            command(self.session, "buy AAPL 1 100")
        self.session.order.assert_not_called()

    def test_buy_requires_stop(self):
        with self.assertRaises(ValueError):
            command(self.session, "buy BTC-USD 0.1")
        self.session.order.assert_not_called()

    def test_buy_routes_only_to_existing_simulator(self):
        command(self.session, "buy BTC-USD 0.01 10000")
        payload = self.session.order.call_args.args[0]
        self.assertEqual(payload["side"], "BUY")
        self.assertEqual(payload["stop_price"], "10000")
        self.assertEqual(payload["symbol"], "BTC-USD")
        self.assertEqual(len(payload["order_id"]), 32)

    def test_halt_is_explicit(self):
        command(self.session, "halt")
        self.session.control.assert_called_once_with("halt")

    def test_arm_requires_current_revision(self):
        self.session.state.return_value = {"risk": {"revision": 7}}
        command(self.session, "arm")
        self.session.control.assert_called_once_with("arm", expected_revision=7)

    def test_no_arbitrary_commands(self):
        for value in ("shell whoami", "trade-live BTC-USD", "buy BTC-USD 1 100 ; rm -rf /"):
            with self.assertRaises(ValueError):
                command(self.session, value)
        self.session.order.assert_not_called()


class SyntheticEtfLifecycle(unittest.TestCase):
    def test_all_five_etfs_execute_with_configured_costs_in_a_synthetic_session(self):
        with tempfile.TemporaryDirectory() as directory:
            feed = SyntheticEtfFeed()
            costs = PaperCosts(Decimal("0.002"), Decimal("0.001"))
            session = LivePaperSession(directory, DEFAULT_ACCOUNT, feed, clock=feed.clock,
                                       market=ETF_FIXTURE_MARKET, costs=costs)
            try:
                command(session, "advance")
                command(session, "arm")
                for symbol in ETF_SYMBOLS:
                    result = command(session, f"buy {symbol} 1 {100 + ETF_SYMBOLS.index(symbol) * 10 - 1}")
                    fill = result["fill"]
                    self.assertEqual(result["status"], "SIMULATED_FILL")
                    self.assertEqual(Decimal(fill["fee"]), Decimal(fill["price"]) * costs.fee)
                    self.assertEqual(fill["details"]["source"], "SYNTHETIC_US_ETF_V1")
                self.assertEqual(set(session.state()["portfolio"]["positions"]), set(ETF_SYMBOLS))
            finally:
                session.close()
            with self.assertRaisesRegex(ValueError, "cost policy mismatch"):
                LivePaperSession(directory, DEFAULT_ACCOUNT, feed, clock=feed.clock, market=ETF_FIXTURE_MARKET)

    def test_selected_etfs_share_runtime_and_enforce_market_hours(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as backups:
            feed = SyntheticEtfFeed()
            session = LivePaperSession(directory, DEFAULT_ACCOUNT, feed, clock=feed.clock,
                                       market=ETF_FIXTURE_MARKET)
            try:
                self.assertEqual(command(session, "markets")["paper_products"], list(ETF_SYMBOLS))
                with self.assertRaisesRegex(PaperRejection, "Fresh books"):
                    command(session, "arm")
                command(session, "advance")
                command(session, "arm")
                with self.assertRaisesRegex(ValueError, "increment"):
                    command(session, "buy SPY 0.5 90")
                terms = "limit buy SPY 2 100.50 90 --id etf_fixture_limit_0001"
                self.assertEqual(command(session, terms)["status"], "PARTIALLY_FILLED")
                self.assertEqual(command(session, terms)["order"]["remaining"], "1")
                command(session, "advance")
                self.assertEqual(command(session, terms)["status"], "FILLED")
                command(session, "advance")
                self.assertEqual(command(session, "sell SPY 2 --id etf_fixture_sale_0001")["status"], "SIMULATED_FILL")
                self.assertEqual(command(session, "advance")["risk"]["reason"], "MARKET_DATA_HALT")
                target = Path(backups) / "verified-copy.sqlite3"
                self.assertEqual(command(session, f"backup {target}")["recovery"], "LOCAL_UNANCHORED")
                with self.assertRaises(ValueError):
                    command(session, f"backup {target}")
                self.assertEqual(session.runtime.ledger.sequence, 3)
            finally:
                session.close()
            next_feed = SyntheticEtfFeed()
            recovered = LivePaperSession(directory, DEFAULT_ACCOUNT, next_feed, clock=next_feed.clock,
                                         market=ETF_FIXTURE_MARKET)
            try:
                next_feed.resume_from(recovered.runtime.events)
                self.assertFalse(recovered.state()["risk"]["armed"])
                self.assertEqual(command(recovered, terms)["status"], "FILLED")
                self.assertEqual(recovered.runtime.ledger.sequence, 3)
            finally:
                recovered.close()
            with self.assertRaisesRegex(ValueError, "policy mismatch"):
                LivePaperSession(directory, DEFAULT_ACCOUNT, next_feed)


if __name__ == "__main__":
    unittest.main()

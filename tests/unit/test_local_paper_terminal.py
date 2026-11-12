"""Local CLI safety regression tests; no network, broker or real-money orders."""
import unittest
from unittest.mock import Mock

from alpha_lab.research.local_paper_terminal import command


class TestLocalTerminal(unittest.TestCase):
    def setUp(self):
        self.session = Mock()

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


if __name__ == "__main__":
    unittest.main()

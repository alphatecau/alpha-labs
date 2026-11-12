import unittest
from alpha_lab.research.paper_first_authority import Mode, TradingAuthority
from alpha_lab.research.paper_trading_session import PaperTradingSession


class PaperTradingSessionTests(unittest.TestCase):
    def test_default_halt_and_explicit_paper_approval(self):
        session = PaperTradingSession()
        with self.assertRaises(PermissionError):
            session.start_paper(operator_approved=True)
        session.set_authority(TradingAuthority(emergency_halt=False))
        with self.assertRaises(PermissionError):
            session.start_paper()
        self.assertFalse(session.start_paper(operator_approved=True)["real_money"])
        fill = session.simulate_fill(symbol="BTC", side="BUY", quantity="1",
                                     reference_mid="100", executed_price="100",
                                     fee="1")
        self.assertTrue(fill["simulated"])
        self.assertEqual(session.status({"BTC": "100"})["paper"]["cash"], "9899")

    def test_live_copy_request_halts_existing_paper_session(self):
        session = PaperTradingSession(TradingAuthority(emergency_halt=False))
        session.start_paper(operator_approved=True)
        session.set_authority(TradingAuthority(requested_mode=Mode.LIVE_COPY,
                                              user_opt_in=True, emergency_halt=False))
        with self.assertRaises(PermissionError):
            session.start_paper(operator_approved=True)
        with self.assertRaises(PermissionError):
            session.simulate_fill(symbol="BTC", side="BUY", quantity="1",
                                  reference_mid="100", executed_price="100", fee="0")
        self.assertTrue(session.status()["paper_halted"])
        self.assertFalse(session.status()["live_copy"]["can_execute"])

    def test_managed_ledger_denies_direct_bypass(self):
        session = PaperTradingSession(TradingAuthority(emergency_halt=False))
        with self.assertRaises(PermissionError):
            session.ledger.enable_simulation(operator_approved=True)
        session.start_paper(operator_approved=True)
        with self.assertRaises(PermissionError):
            session.ledger.fill(symbol="BTC", side="BUY", quantity="1",
                                reference_mid="100", executed_price="100", fee="0")
        with self.assertRaises(PermissionError):
            session.simulate_fill(symbol="BTC", side="BUY", quantity="1",
                                  reference_mid="100", executed_price="100",
                                  fee="0", simulated_only=False)
        self.assertTrue(session.ledger.halted)

    def test_halt_change_blocks_fill(self):
        session = PaperTradingSession(TradingAuthority(emergency_halt=False))
        session.start_paper(operator_approved=True)
        session.set_authority(TradingAuthority())
        with self.assertRaises(PermissionError):
            session.simulate_fill(symbol="BTC", side="BUY", quantity="1",
                                  reference_mid="100", executed_price="100", fee="0")
        self.assertTrue(session.ledger.halted)


if __name__ == "__main__":
    unittest.main()

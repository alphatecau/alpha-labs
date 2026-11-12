import unittest
from alpha_lab.research.paper_first_authority import (
    Mode, TradingAuthority, authorise_simulation, live_copy_readiness
)

class PaperFirstAuthorityTests(unittest.TestCase):
    def test_default_halts(self):
        result = authorise_simulation(TradingAuthority())
        self.assertEqual(result["decision"], "HALT")
        self.assertFalse(result["real_money"])

    def test_paper_simulation_requires_halt_clear(self):
        result = authorise_simulation(TradingAuthority(emergency_halt=False))
        self.assertEqual(result["execution"], "SIMULATED")
        self.assertFalse(result["real_money"])

    def test_live_copy_always_blocked_even_all_flags(self):
        authority = TradingAuthority(
            requested_mode=Mode.LIVE_COPY, user_opt_in=True,
            regulatory_approved=True, strategy_independently_validated=True,
            broker_integration_approved=True, independent_risk_gate_approved=True,
            deployment_approved=True, emergency_halt=False
        )
        with self.assertRaises(PermissionError):
            authorise_simulation(authority)
        readiness = live_copy_readiness(authority)
        self.assertFalse(readiness["can_execute"])
        self.assertFalse(readiness["implemented"])

    def test_invalid_authority_fails_closed(self):
        with self.assertRaises(ValueError):
            authorise_simulation(None)

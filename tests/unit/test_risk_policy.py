"""Research-only risk checks; no route to broker/order placement."""
from dataclasses import replace
from decimal import Decimal
import unittest
from alpha_lab.risk.policy import RiskPolicy, ResearchProposal, assess_proposal


class RiskPolicyTests(unittest.TestCase):
    def setUp(self):
        self.good = ResearchProposal(
            equity=Decimal('10000'), open_exposure=Decimal('0'),
            proposed_notional=Decimal('1000'), realised_daily_pnl=Decimal('0'),
            drawdown_fraction=Decimal('0'), quote_age_seconds=10,
            data_integrity_ok=True, kill_switch_active=False, side='LONG',
        )

    def check_rejection(self, code, **overrides):
        decision = assess_proposal(replace(self.good, **overrides))
        self.assertEqual(decision.status, 'REJECTED')
        self.assertIn(code, decision.reasons)
        self.assertFalse(decision.execution_authorised)

    def test_valid_proposal_is_research_only(self):
        d = assess_proposal(self.good)
        self.assertEqual(d.status, 'RESEARCH_ONLY_PASS')
        self.assertTrue(d.passes_research_checks)
        self.assertFalse(d.execution_authorised)

    def test_short_side_rejected(self):
        self.check_rejection('UNSUPPORTED_SIDE', side='SHORT')

    def test_stale_quote_rejected(self):
        self.check_rejection('STALE_QUOTE', quote_age_seconds=181)

    def test_data_integrity_rejected(self):
        self.check_rejection('UNVERIFIED_DATA', data_integrity_ok=False)

    def test_kill_switch_rejected(self):
        self.check_rejection('KILL_SWITCH_ACTIVE_OR_UNKNOWN', kill_switch_active=True)

    def test_position_size_rejected(self):
        self.check_rejection('NEW_POSITION_LIMIT', proposed_notional=Decimal('2001'))

    def test_portfolio_exposure_rejected(self):
        self.check_rejection('TOTAL_EXPOSURE_LIMIT', open_exposure=Decimal('2500'))

    def test_daily_loss_rejected_at_threshold(self):
        self.check_rejection('DAILY_LOSS_LIMIT', realised_daily_pnl=Decimal('-200'))

    def test_drawdown_rejected_at_threshold(self):
        self.check_rejection('DRAWDOWN_LIMIT', drawdown_fraction=Decimal('0.05'))

    def test_nonfinite_price_rejected(self):
        with self.assertRaisesRegex(ValueError, 'finite'):
            assess_proposal(replace(self.good, equity=Decimal('NaN')))

    def test_invalid_policy_rejected(self):
        with self.assertRaises(ValueError):
            RiskPolicy(max_total_exposure_fraction=Decimal('1.2'))

    def test_unknown_boolean_fails_closed(self):
        self.check_rejection('UNVERIFIED_DATA', data_integrity_ok=None)

    def test_invalid_equity_rejected(self):
        self.check_rejection('INVALID_EQUITY', equity=Decimal('0'))

    def test_negative_position_rejected(self):
        self.check_rejection('INVALID_NOTIONAL', proposed_notional=Decimal('-1'))

    def test_invalid_quote_age_rejected(self):
        self.check_rejection('INVALID_QUOTE_AGE', quote_age_seconds=-1)


if __name__ == '__main__':
    unittest.main()

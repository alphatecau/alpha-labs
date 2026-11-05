"""Evidence summaries remain unvalidated even when historical returns are positive."""
from copy import deepcopy
from decimal import Decimal
import unittest
from alpha_lab.research.evidence_gate import summarise_offline_research


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        good = {'strategy': {'return_pct': 1.5},
                'equal_allocation_buy_hold': {'return_pct': 2.0},
                'double_cost_strategy': {'return_pct': 0.5}}
        self.report = {
            'status': 'HYPOTHESIS_SCREEN_ONLY_NOT_VALIDATED_ALPHA',
            'configuration_sha256': 'a' * 64,
            'dataset': {'sha256': 'f' * 64, 'provenance': 'synthetic', 'quote_currency': 'USDC'},
            'periods': {'training': deepcopy(good), 'holdout': deepcopy(good)},
        }

    def test_truthful_output(self):
        out = summarise_offline_research(self.report)
        self.assertFalse(out['trading_enabled'])
        self.assertFalse(out['price_authenticity_verified'])
        self.assertFalse(out['holdout_independently_sealed'])
        self.assertEqual(out['status'], 'EVIDENCE_INSUFFICIENT_RESEARCH_ONLY')
        self.assertEqual(out['periods']['holdout']['excess_vs_passive_pct_points'], -0.5)
        self.assertFalse(out['periods']['holdout']['outperforms_passive'])

    def test_even_positive_returns_do_not_authorise_trading(self):
        self.report['periods']['holdout']['strategy']['return_pct'] = 9
        out = summarise_offline_research(self.report)
        self.assertFalse(out['trading_enabled'])
        self.assertEqual(out['status'], 'EVIDENCE_INSUFFICIENT_RESEARCH_ONLY')

    def test_false_validated_status_rejected(self):
        self.report['status'] = 'VALIDATED_ALPHA'
        with self.assertRaises(ValueError):
            summarise_offline_research(self.report)

    def test_missing_comparator_rejected(self):
        del self.report['periods']['training']['equal_allocation_buy_hold']
        with self.assertRaises(ValueError):
            summarise_offline_research(self.report)

    def test_nan_return_rejected(self):
        self.report['periods']['holdout']['strategy']['return_pct'] = float('nan')
        with self.assertRaises(ValueError):
            summarise_offline_research(self.report)

    def test_missing_provenance_rejected(self):
        self.report['dataset']['provenance'] = ''
        with self.assertRaises(ValueError):
            summarise_offline_research(self.report)

    def test_extra_period_rejected(self):
        self.report['periods']['future'] = deepcopy(self.report['periods']['holdout'])
        with self.assertRaises(ValueError):
            summarise_offline_research(self.report)


if __name__ == '__main__':
    unittest.main()

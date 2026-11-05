"""Frozen, non-live, deterministic historical research tests."""
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

from archive_fixture import two_month_transport
from alpha_lab.data.csv_import import load_csv, Dataset, Bar
from alpha_lab.data.adapters.binance_archive import build_dataset
from alpha_lab.research.long_history import (default_config, evaluate_periods, freeze_experiment,
    _read_spec, _risk_stats, evaluate_spec)

class HistoricalResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name)/'datasets'
        transport,_=two_month_transport()
        cls.imported=build_dataset('BTCUSDT','2024-12','2025-01',cls.root,transport=transport)
        cls.csv=Path(cls.imported['csv']);cls.manifest=Path(cls.imported['manifest'])
        cls.dataset=load_csv(cls.csv,quote_currency='USDT',interval_minutes=60,provenance='test-only-synthetic-archive')

    def test_replay_parity_and_split(self):
        report=evaluate_periods(self.dataset,min_bars=400)
        self.assertEqual(list(report['periods']),['training','validation','test_unsealed'])
        self.assertFalse(report['trading_enabled'])
        self.assertFalse(report['holdout_independently_sealed'])
        self.assertTrue(report['replay_ledger_parity_checked'])
        t1=int(len(self.dataset.bars)*.60)
        self.assertEqual(report['boundaries_index']['validation'][0],t1+48)
        for entry in report['periods'].values():
            self.assertTrue(entry['legacy_ledger_parity'])
            self.assertIn('sharpe_zero_risk_free',entry['modelled_strategy'])
            self.assertIn('max_drawdown_pct',entry['modelled_strategy'])

    def test_higher_costs_do_not_improve_modelled_nav(self):
        report=evaluate_periods(self.dataset,min_bars=400)
        for entry in report['periods'].values():
            self.assertLessEqual(entry['strategy_double_execution_friction']['net_modelled_execution_return_pct'],
                                 entry['modelled_strategy']['net_modelled_execution_return_pct']+1e-9)

    def test_operating_cost_reduces_after_overhead_return(self):
        cfg=default_config();cfg['operating_cost_usdt_per_year']='1000'
        report=evaluate_periods(self.dataset,cfg,min_bars=400)
        for entry in report['periods'].values():
            self.assertLess(entry['after_modelled_execution_and_operating_expenses_pct'],
                            entry['modelled_strategy']['net_modelled_execution_return_pct'])

    def test_future_prices_cannot_affect_training(self):
        original=evaluate_periods(self.dataset,min_bars=400)
        bars=list(self.dataset.bars)
        offset=int(len(bars)*.85)
        # Modify only late test candles; earlier training and validation stay the same.
        for i in range(offset,len(bars)):
            bar=bars[i]
            bars[i]=Bar(bar.time,bar.open*2,bar.high*2,bar.low*2,bar.close*2,bar.volume)
        changed=Dataset(tuple(bars),'USDT','modified-test-fixture','synthetic',60)
        mutated=evaluate_periods(changed,min_bars=400)
        self.assertEqual(original['periods']['training'],mutated['periods']['training'])
        self.assertEqual(original['periods']['validation'],mutated['periods']['validation'])

    def test_short_fixture_cannot_clear_production_gate(self):
        with self.assertRaisesRegex(ValueError,'Insufficient'):
            evaluate_periods(self.dataset)

    def test_frozen_spec_tampering_and_no_overwrite(self):
        path=self.root/'replay'/'experiments'/'frozen_test.json'
        spec=freeze_experiment(self.csv,self.manifest,path)
        got,_=_read_spec(self.csv,self.manifest,path)
        self.assertEqual(got['specification_sha256'],spec['specification_sha256'])
        with self.assertRaises(FileExistsError): freeze_experiment(self.csv,self.manifest,path)
        body=json.loads(path.read_text());body['configuration']['max_allocation']='0.90'
        path.write_text(json.dumps(body))
        with self.assertRaisesRegex(ValueError,'modified'):_read_spec(self.csv,self.manifest,path)

    def test_invalid_frozen_config_rejected(self):
        cfg=default_config();cfg['fast']=10
        with self.assertRaisesRegex(ValueError,'frozen'):
            freeze_experiment(self.csv,self.manifest,self.root/'invalid-spec.json',cfg)

    def test_evaluate_spec_rejects_under_two_years(self):
        spec=self.root/'short-spec.json'
        freeze_experiment(self.csv,self.manifest,spec)
        report=self.root/'replay'/'reports'/'short_report.json'
        with self.assertRaisesRegex(ValueError,'Insufficient'):
            evaluate_spec(self.csv,self.manifest,spec,report)
        self.assertFalse(report.exists())

    def test_risk_stats_are_null_when_undefined(self):
        stats=_risk_stats([10000.0]*100,10000.0)
        self.assertIsNone(stats['sharpe_zero_risk_free'])
        self.assertIsNone(stats['sortino_zero_target'])
        self.assertEqual(stats['max_drawdown_pct'],0)

if __name__=='__main__':unittest.main()

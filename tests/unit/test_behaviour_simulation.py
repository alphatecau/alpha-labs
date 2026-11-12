import unittest
from dataclasses import replace
from alpha_lab.behaviour_simulation import ScenarioInput, simulate


class BehaviourSimulationTests(unittest.TestCase):
    def setUp(self):
        self.event = ScenarioInput(
            event_id="fixture-001", asset="BTC",
            headline="Synthetic policy event (not actual news)",
            observed_at_utc="2026-01-01T10:00:00Z",
            information_cutoff_utc="2026-01-01T10:05:00Z",
            source_id="synthetic-fixture",
        )

    def test_deterministic_replay(self):
        self.assertEqual(simulate(self.event, seed=7), simulate(self.event, seed=7))

    def test_never_emits_trade_signal(self):
        result = simulate(self.event)
        self.assertEqual(result.status, "UNVERIFIED")
        self.assertEqual(result.recommendation, "NO_SIGNAL")
        self.assertEqual(len(result.synthetic_reactions), 15)

    def test_rejects_future_information(self):
        with self.assertRaises(ValueError):
            simulate(replace(self.event, observed_at_utc="2026-01-01T10:06:00Z"))

    def test_rejects_missing_provenance(self):
        with self.assertRaises(ValueError):
            simulate(replace(self.event, source_id=""))

    def test_rejects_unbounded_runs(self):
        for kwargs in ({"agents": 11}, {"rounds": 6}, {"rounds": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                simulate(self.event, **kwargs)

    def test_rejects_naive_timestamp(self):
        with self.assertRaises(ValueError):
            simulate(replace(self.event, observed_at_utc="2026-01-01T10:00:00"))


if __name__ == "__main__":
    unittest.main()

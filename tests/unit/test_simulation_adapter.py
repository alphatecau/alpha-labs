import unittest
from dataclasses import replace
from alpha_lab.behaviour_simulation import ScenarioInput
from alpha_lab.simulation_adapter import (
    SandboxedSimulationAdapter, SimulationAdapterError,
)

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.event = ScenarioInput("evt1", "BTC", "Synthetic event",
                                   "2026-01-01T00:00:00Z",
                                   "2026-01-01T00:00:01Z", "fixture")

    def test_accepts_bounded_synthetic_provider(self):
        adapter = SandboxedSimulationAdapter("mock", lambda request: {
            "event_id": request["event_id"],
            "observations": [{"persona": "sceptic", "narrative": "Hypothetical reaction"}],
            "recommendation": "BUY", "confidence": 1.0})
        result = adapter.run(self.event)
        self.assertEqual(result.status, "UNVERIFIED")
        self.assertEqual(result.recommendation, "NO_SIGNAL")
        self.assertEqual(len(result.observations), 1)

    def test_rejects_mismatched_event(self):
        adapter = SandboxedSimulationAdapter("mock", lambda _: {
            "event_id": "wrong", "observations": []})
        with self.assertRaises(SimulationAdapterError):
            adapter.run(self.event)

    def test_rejects_transport_failure(self):
        def failed(_):
            raise TimeoutError("timeout")
        with self.assertRaises(SimulationAdapterError):
            SandboxedSimulationAdapter("mock", failed).run(self.event)

    def test_rejects_over_budget(self):
        adapter = SandboxedSimulationAdapter("mock", lambda _: {})
        with self.assertRaises(SimulationAdapterError):
            adapter.run(self.event, agents=11)

    def test_rejects_future_event(self):
        adapter = SandboxedSimulationAdapter("mock", lambda _: {})
        with self.assertRaises(ValueError):
            adapter.run(replace(self.event, observed_at_utc="2026-01-02T00:00:00Z"))

    def test_rejects_invalid_response(self):
        adapter = SandboxedSimulationAdapter("mock", lambda _: {
            "event_id": "evt1", "observations": "invalid"})
        with self.assertRaises(SimulationAdapterError):
            adapter.run(self.event)

if __name__ == "__main__":
    unittest.main()

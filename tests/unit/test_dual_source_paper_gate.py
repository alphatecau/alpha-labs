from datetime import datetime, timedelta, timezone
import unittest

from alpha_lab.research.dual_source_paper_gate import DualSourcePaperGate
from alpha_lab.research.local_paper_terminal import command

NOW = datetime(2026, 11, 16, 0, 0, tzinfo=timezone.utc)


class Feed:
    def snapshot(self, now):
        return {}, {"BTC-USD": True, "ETH-USD": True, "SOL-USD": True}, {}
    def poll(self, pool):
        return None
    def close(self):
        return None


class GateTests(unittest.TestCase):
    def test_starts_halted_and_refresh_enables(self):
        gate = DualSourcePaperGate(Feed(), validator=lambda asset, now: {
            "status": "VERIFIED_RESEARCH_DATA", "asset": asset, "observed_at_utc": now})
        self.assertFalse(any(gate.snapshot(NOW)[1].values()))
        self.assertEqual(len(gate.refresh(now=NOW)), 3)
        self.assertTrue(all(gate.snapshot(NOW)[1].values()))
        self.assertFalse(any(gate.snapshot(NOW + timedelta(seconds=61))[1].values()))

    def test_provider_failure_blocks_one_asset(self):
        def check(asset, now):
            if asset == "SOL":
                raise RuntimeError("provider down")
            return {"status": "VERIFIED_RESEARCH_DATA", "asset": asset, "observed_at_utc": now}
        gate = DualSourcePaperGate(Feed(), validator=check)
        gate.refresh(now=NOW)
        health = gate.snapshot(NOW)[1]
        self.assertTrue(health["BTC-USD"])
        self.assertTrue(health["ETH-USD"])
        self.assertFalse(health["SOL-USD"])

    def test_invalid_evidence_fails_closed(self):
        gate = DualSourcePaperGate(Feed(), validator=lambda asset, now: {"status": "PASS"})
        gate.refresh(now=NOW)
        self.assertFalse(any(gate.snapshot(NOW)[1].values()))

    def test_terminal_refresh_command_never_auto_arms(self):
        gate = DualSourcePaperGate(Feed(), validator=lambda asset, now: {
            "status": "VERIFIED_RESEARCH_DATA", "asset": asset, "observed_at_utc": now})
        class Session:
            feed = gate
            def state(self):
                return {"risk": {"armed": False}}
            def control(self, action):
                raise AssertionError("successful refresh must not change controls")
        result = command(Session(), "refresh-data")
        self.assertEqual(result["validation"], "PASS")
        self.assertFalse(result["armed"])

    def test_terminal_refresh_failure_halts(self):
        gate = DualSourcePaperGate(Feed(), validator=lambda asset, now: {
            "status": "VERIFIED_RESEARCH_DATA", "asset": asset, "observed_at_utc": now}
            if asset != "SOL" else {"status": "HALT"})
        class Session:
            feed = gate
            halted = False
            def control(self, action):
                self.halted = action == "halt"
        session = Session()
        result = command(session, "refresh-data")
        self.assertEqual(result["validation"], "HALT")
        self.assertTrue(session.halted)


if __name__ == "__main__":
    unittest.main()

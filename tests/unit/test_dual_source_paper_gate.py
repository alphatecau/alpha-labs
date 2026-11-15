from datetime import datetime, timedelta, timezone
import unittest
from threading import Event, Thread

from alpha_lab.research.dual_source_paper_gate import DualSourcePaperGate

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

    def test_old_refresh_cannot_restore_health_after_new_failure(self):
        entered, release = Event(), Event()
        calls = {"count": 0}

        def validator(asset, now):
            calls["count"] += 1
            if calls["count"] == 1:
                entered.set()
                if not release.wait(timeout=5):
                    raise RuntimeError("test timed out")
                return {"status": "VERIFIED_RESEARCH_DATA", "asset": asset,
                        "observed_at_utc": now}
            raise RuntimeError("provider offline")

        gate = DualSourcePaperGate(Feed(), validator=validator)
        worker = Thread(target=lambda: gate.refresh(now=NOW))
        worker.start()
        self.assertTrue(entered.wait(timeout=5))
        gate.refresh(now=NOW)
        release.set()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertFalse(any(gate.snapshot(NOW)[1].values()))

    def test_invalid_evidence_fails_closed(self):
        gate = DualSourcePaperGate(Feed(), validator=lambda asset, now: {"status": "PASS"})
        gate.refresh(now=NOW)
        self.assertFalse(any(gate.snapshot(NOW)[1].values()))


if __name__ == "__main__":
    unittest.main()

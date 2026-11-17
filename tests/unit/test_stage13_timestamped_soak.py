"""Deterministic tests for Stage 13 local duration evidence."""
import unittest
from datetime import datetime, timezone

from alpha_lab.research.stage13_timestamped_soak import capture

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


class FakeTime:
    seconds = 0.0

    def tick(self):
        return self.seconds

    def sleep(self, seconds):
        self.seconds += seconds


class Feed:
    def poll(self, _pool):
        pass

    def snapshot(self, _now):
        return ({}, {"BTC-USD": False, "ETH-USD": False, "SOL-USD": False}, {})


class Stage13TimestampAcceptance(unittest.TestCase):
    def test_elapsed_time_recorded_and_degraded_status_retained(self):
        fake = FakeTime()
        result = capture(duration_seconds=30, interval_seconds=15, feed=Feed(),
                         clock=lambda: NOW, monotonic=fake.tick, sleep=fake.sleep)
        self.assertEqual(result["elapsed_monotonic_seconds"], 30)
        self.assertTrue(result["duration_verified_locally"])
        self.assertEqual(result["status"], "DEGRADED")
        self.assertFalse(result["independent_time_attestation"])
        self.assertEqual(result["live_orders"], 0)

    def test_invalid_bounds_rejected_before_feed_use(self):
        with self.assertRaises(ValueError):
            capture(duration_seconds=29, feed=Feed())


if __name__ == "__main__":
    unittest.main()

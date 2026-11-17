import unittest
from alpha_lab.research.stage16_bounded_pilot import pilot


def good_quotes(**kwargs):
    return {"status": "PASS", "mode": "READ_ONLY", "paper_orders": 0,
            "live_orders": 0, "live_execution_authorised": False}


def good_paper():
    return {"status": "PASS", "mode": "SIMULATION_ONLY", "fills": 1,
            "backup": "VERIFIED", "restart": "HALT",
            "live_execution_authorised": False}


class Stage16Tests(unittest.TestCase):
    def test_two_isolated_cycles(self):
        result = pilot(cycles=2, observe_fn=good_quotes, rehearse_fn=good_paper)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["cycles_completed"], 2)
        self.assertFalse(result["live_execution_authorised"])

    def test_bad_quote_halts_without_rehearsal(self):
        calls = []
        def bad(**kwargs):
            data = good_quotes(**kwargs)
            data["status"] = "DEGRADED"
            return data
        result = pilot(cycles=3, observe_fn=bad,
                       rehearse_fn=lambda: calls.append("paper"))
        self.assertEqual(result["status"], "HALT")
        self.assertEqual(result["cycles_completed"], 1)
        self.assertEqual(calls, [])

    def test_bad_backup_halts(self):
        def bad():
            data = good_paper()
            data["backup"] = "FAILED"
            return data
        self.assertEqual(pilot(cycles=2, observe_fn=good_quotes,
                               rehearse_fn=bad)["status"], "HALT")

    def test_live_execution_flag_halts(self):
        def bad():
            data = good_paper()
            data["live_execution_authorised"] = True
            return data
        self.assertEqual(pilot(cycles=2, observe_fn=good_quotes,
                               rehearse_fn=bad)["status"], "HALT")

    def test_reject_unbounded_cycles(self):
        for count in (0, 25, True, -1):
            with self.assertRaises(ValueError):
                pilot(cycles=count, observe_fn=good_quotes, rehearse_fn=good_paper)

if __name__ == "__main__":
    unittest.main()

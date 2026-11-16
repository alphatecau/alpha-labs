import unittest
from unittest.mock import patch
import agent_v3

class AgentTests(unittest.TestCase):
    def test_min_interval(self):
        self.assertEqual(agent_v3.validate_interval("60"), 60)
    def test_max_interval(self):
        self.assertEqual(agent_v3.validate_interval("3600"), 3600)
    def test_too_fast(self):
        with self.assertRaises(ValueError):
            agent_v3.validate_interval("1")
    def test_too_slow(self):
        with self.assertRaises(ValueError):
            agent_v3.validate_interval("3601")
    def test_invalid(self):
        with self.assertRaises(ValueError):
            agent_v3.validate_interval("bad")
    def test_dry_run_no_execute(self):
        with patch("agent_v3.subprocess.run") as call:
            call.return_value.returncode=0
            agent_v3.run_once("worker_v2.py",False)
            self.assertEqual(call.call_args.args[0], [agent_v3.sys.executable,"worker_v2.py"])
    def test_execute_only_passes_flag(self):
        with patch("agent_v3.subprocess.run") as call:
            call.return_value.returncode=0
            agent_v3.run_once("worker_v2.py",True)
            self.assertEqual(call.call_args.args[0][-1],"--execute")

if __name__ == "__main__":
    unittest.main()

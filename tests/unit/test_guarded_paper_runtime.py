import tempfile
import unittest
from pathlib import Path
from alpha_lab.research.guarded_paper_runtime import GuardedPaperRuntime
from alpha_lab.research.paper_first_authority import Mode, TradingAuthority


class GuardedPaperRuntimeTests(unittest.TestCase):
    def test_default_halt_and_no_live(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = GuardedPaperRuntime(str(Path(directory) / "paper.sqlite3"))
            try:
                with self.assertRaises(PermissionError):
                    runtime.enable(operator_approved=True)
                self.assertFalse(runtime.status()["live_copy_enabled"])
                runtime.set_authority(TradingAuthority(emergency_halt=False))
                runtime.enable(operator_approved=True)
                self.assertFalse(runtime.status()["halted"])
                runtime.set_authority(TradingAuthority(requested_mode=Mode.LIVE_COPY,
                                                      user_opt_in=True, emergency_halt=False))
                with self.assertRaises(PermissionError):
                    runtime.enable(operator_approved=True)
                with self.assertRaises(PermissionError):
                    runtime.execute(operator_approved=True)
                self.assertTrue(runtime.status()["halted"])
            finally:
                runtime.close()

    def test_unapproved_operator_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = GuardedPaperRuntime(str(Path(directory) / "paper.sqlite3"),
                                          authority=TradingAuthority(emergency_halt=False))
            try:
                runtime.enable(operator_approved=True)
                with self.assertRaises(PermissionError):
                    runtime.execute(operator_approved=False)
                self.assertTrue(runtime.status()["halted"])
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()

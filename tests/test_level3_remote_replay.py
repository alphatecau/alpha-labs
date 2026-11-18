"""Remote nonce replay persists across database reopen."""
import tempfile
import unittest
from pathlib import Path
from tools.level3_staging.remote_replay import claim_once
from tools.level3_staging.remote_auth import RemoteDenied

class ReplayTests(unittest.TestCase):
    def test_persistent_replay_denial(self):
        with tempfile.TemporaryDirectory() as d:
            private=Path(d)/"private"
            private.mkdir(mode=0o700)
            db=private/"nonces.db"
            self.assertTrue(claim_once(db,"a"*64))
            with self.assertRaises(RemoteDenied):
                claim_once(db,"a"*64)
            self.assertTrue(claim_once(db,"b"*64))
    def test_unsafe_parent_denied(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"open"
            p.mkdir(mode=0o777)
            p.chmod(0o777)
            with self.assertRaises(RemoteDenied):
                claim_once(p/"nonces.db","a"*64)

if __name__=="__main__":
    unittest.main()

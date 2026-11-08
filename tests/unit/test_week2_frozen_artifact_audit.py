import math
import tempfile
import unittest
from pathlib import Path
from scripts.week2_frozen_artifact_audit import _folds, _block_interval, audit

class Week2FrozenAuditTests(unittest.TestCase):
    def test_constant_nav_has_zero_returns(self):
        nav=[10000.0]*2400
        folds=_folds(nav)
        self.assertEqual(len(folds),5)
        self.assertTrue(all(x["return_pct"]==0 for x in folds))
        interval=_block_interval(nav,123,repetitions=100)
        self.assertEqual(interval["familywise_95_lower_pct"],0)
        self.assertEqual(interval["familywise_95_upper_pct"],0)

    def test_bootstrap_deterministic(self):
        nav=[10000*math.exp(.00001*i) for i in range(2400)]
        a=_block_interval(nav,999,repetitions=100)
        self.assertEqual(a,_block_interval(nav,999,repetitions=100))

    def test_tampered_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"fake.zip"
            path.write_bytes(b"not the frozen archive")
            with self.assertRaisesRegex(ValueError,"digest mismatch"):
                audit(path)

if __name__=="__main__":
    unittest.main()

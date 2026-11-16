import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import worker_v2 as w

class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.issue={"author":{"login":"alphatecau"},"labels":[{"name":w.LABEL}],
            "body":'{"schema":1,"tool":"repo_status","repo":"alpha-labs"}'}
    def test_valid(self):
        self.assertEqual(w.validate(self.issue)["tool"],"repo_status")
    def test_bad_author(self):
        self.issue["author"]["login"]="other"
        with self.assertRaises(ValueError): w.validate(self.issue)
    def test_missing_label(self):
        self.issue["labels"]=[]
        with self.assertRaises(ValueError): w.validate(self.issue)
    def test_shell_forbidden(self):
        self.issue["body"]='{"schema":1,"tool":"shell","repo":"alpha-labs"}'
        with self.assertRaises(ValueError): w.validate(self.issue)
    def test_other_repo_forbidden(self):
        self.issue["body"]='{"schema":1,"tool":"repo_status","repo":"TradingAgents"}'
        with self.assertRaises(ValueError): w.validate(self.issue)
    def test_extra_field_forbidden(self):
        self.issue["body"]='{"schema":1,"tool":"repo_status","repo":"alpha-labs","command":"id"}'
        with self.assertRaises(ValueError): w.validate(self.issue)
    def test_boolean_schema_forbidden(self):
        self.issue["body"]='{"schema":true,"tool":"repo_status","repo":"alpha-labs"}'
        with self.assertRaises(ValueError): w.validate(self.issue)
    def test_replay(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(w,"STATE",Path(td)/"state.sqlite3"):
                db=w.connect()
                self.assertTrue(w.reserve(db,139))
                self.assertFalse(w.reserve(db,139))
                w.mark(db,139,"success")
                self.assertEqual(db.execute("SELECT status FROM executions WHERE issue=139").fetchone()[0],"success")
                db.close()
    def test_receipt_never_contains_output(self):
        with patch.object(w,"run") as run:
            w.report(139,{"tool":"repo_status","repo":"alpha-labs"},"success")
            self.assertEqual(run.call_count,2)
            self.assertNotIn("stdout",str(run.call_args_list))
if __name__=="__main__":
    unittest.main()

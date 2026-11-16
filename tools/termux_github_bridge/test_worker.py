import unittest
from worker import validate, LABEL

class Validation(unittest.TestCase):
    def setUp(self):
        self.issue = {"author":{"login":"alphatecau"},
            "labels":[{"name":LABEL}],
            "body":'{"schema":1,"tool":"repo_status","repo":"alpha-labs"}'}
    def test_valid(self):
        self.assertEqual(validate(self.issue)["tool"], "repo_status")
    def test_author(self):
        self.issue["author"]["login"]="attacker"
        with self.assertRaises(ValueError): validate(self.issue)
    def test_label(self):
        self.issue["labels"]=[]
        with self.assertRaises(ValueError): validate(self.issue)
    def test_shell(self):
        self.issue["body"]='{"schema":1,"tool":"shell","repo":"alpha-labs"}'
        with self.assertRaises(ValueError): validate(self.issue)
    def test_other_repo(self):
        self.issue["body"]='{"schema":1,"tool":"repo_status","repo":"TradingAgents"}'
        with self.assertRaises(ValueError): validate(self.issue)
    def test_extra_fields(self):
        self.issue["body"]='{"schema":1,"tool":"repo_status","repo":"alpha-labs","cmd":"x"}'
        with self.assertRaises(ValueError): validate(self.issue)
if __name__ == "__main__":
    unittest.main()

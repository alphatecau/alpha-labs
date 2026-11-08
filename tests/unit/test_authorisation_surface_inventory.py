import tempfile
import unittest
from pathlib import Path

from tools.authorisation_surface_inventory import inventory


class AuthorisationInventoryTests(unittest.TestCase):
    def test_discovers_function_and_never_claims_exhaustive_runtime_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "tools").mkdir()
            (root / "tools" / "example.py").write_text(
                "def endpoint():\n    return {'promotion_authorised': True}\n",
                encoding="utf-8",
            )
            result = inventory(root)
            self.assertFalse(result["runtime_call_graph_verified"])
            self.assertFalse(result["entry_points_exhaustively_verified"])
            self.assertFalse(result["promotion_authorised"])
            self.assertEqual(result["findings"][0]["function"], "endpoint")

    def test_syntax_errors_are_reported_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "scripts").mkdir()
            (root / "scripts" / "broken.py").write_text("def broken(:\n")
            result = inventory(root)
            self.assertEqual(result["parse_errors"][0]["error"], "SyntaxError")


if __name__ == "__main__":
    unittest.main()

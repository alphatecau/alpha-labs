"""Offline tests for the OSV response parser."""
import io
import json
import unittest

from scripts.osv_audit import audit


class Response(io.BytesIO):
    status = 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


class OSVTests(unittest.TestCase):
    def test_vulnerability_report(self):
        def opener(req, timeout):
            self.assertEqual(req.get_method(), "POST")
            self.assertEqual(timeout, 20)
            return Response(json.dumps({"results": [{"vulns": [{"id": "OSV-2026-EXAMPLE"}]}]}).encode())
        result = audit([("example", "1.0")], opener=opener)
        self.assertEqual(result[0]["id"], "OSV-2026-EXAMPLE")

    def test_missing_results_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            audit([("example", "1.0")], opener=lambda *_args, **_kwargs: Response(b'{"results":[]}'))

    def test_no_packages_does_not_call_network(self):
        self.assertEqual(audit([], opener=lambda *_a, **_kw: self.fail("unexpected network")), [])


if __name__ == "__main__":
    unittest.main()

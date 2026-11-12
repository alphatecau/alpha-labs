import tempfile
import unittest
from alpha_lab.research.identity_rate_limit import SQLiteIdentityLimiter


class IdentityLimiterTests(unittest.TestCase):
    def test_shared_file_limits_identity_and_resets_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = [120]
            a = SQLiteIdentityLimiter(
                tmp + "/rate.db", limit=2, window=60, clock=lambda: now[0]
            )
            b = SQLiteIdentityLimiter(
                tmp + "/rate.db", limit=2, window=60, clock=lambda: now[0]
            )
            try:
                self.assertTrue(a.allow("https://issuer.example/", "owner"))
                self.assertTrue(b.allow("https://issuer.example/", "owner"))
                with self.assertRaises(PermissionError):
                    a.allow("https://issuer.example/", "owner")
                self.assertTrue(a.allow("https://issuer.example/", "other"))
                now[0] = 180
                self.assertTrue(b.allow("https://issuer.example/", "owner"))
            finally:
                a.close()
                b.close()

    def test_invalid_identity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            limiter = SQLiteIdentityLimiter(tmp + "/rate.db")
            try:
                with self.assertRaises(PermissionError):
                    limiter.allow("http://issuer", "owner")
                with self.assertRaises(PermissionError):
                    limiter.allow("https://issuer/", "")
            finally:
                limiter.close()


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch
from deployment.auth0_refreshing_verifier import RefreshingAuth0Verifier


class RefreshTests(unittest.TestCase):
    def test_invalid_interval(self):
        with self.assertRaises(ValueError):
            RefreshingAuth0Verifier("https://issuer.example", "client", refresh_seconds=1)

    def test_refresh_failure_does_not_reuse_old_keys(self):
        now = [0]
        calls = [0]
        class FakeVerifier:
            def __call__(self, token):
                return {"verified": True}
        def loader(*args, **kwargs):
            calls[0] += 1
            if calls[0] > 1:
                raise PermissionError("network failure")
            return FakeVerifier()
        with patch("deployment.auth0_refreshing_verifier.load_auth0_verifier", side_effect=loader):
            verifier = RefreshingAuth0Verifier("https://issuer.example", "client", clock=lambda: now[0], refresh_seconds=30)
            self.assertTrue(verifier("synthetic")["verified"])
            now[0] = 31
            with self.assertRaises(PermissionError):
                verifier("synthetic")
            with self.assertRaises(PermissionError):
                verifier("synthetic")
            self.assertEqual(calls[0], 2)

    def test_refresh_recovers_only_after_interval(self):
        now = [0]
        calls = [0]
        def loader(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 2:
                raise OSError("synthetic JWKS outage")
            return lambda token: {"generation": calls[0]}
        with patch("deployment.auth0_refreshing_verifier.load_auth0_verifier", side_effect=loader):
            verifier = RefreshingAuth0Verifier(
                "https://issuer.example", "client",
                clock=lambda: now[0], refresh_seconds=30)
            self.assertEqual(verifier("synthetic")["generation"], 1)
            now[0] = 31
            with self.assertRaises(PermissionError):
                verifier("synthetic")
            now[0] = 32
            with self.assertRaises(PermissionError):
                verifier("synthetic")
            self.assertEqual(calls[0], 2)
            now[0] = 61
            self.assertEqual(verifier("synthetic")["generation"], 3)

    def test_successful_periodic_refresh(self):
        now = [0]
        calls = [0]
        def loader(*args, **kwargs):
            calls[0] += 1
            return lambda token: {"generation": calls[0]}
        with patch("deployment.auth0_refreshing_verifier.load_auth0_verifier", side_effect=loader):
            verifier = RefreshingAuth0Verifier("https://issuer.example", "client", clock=lambda: now[0], refresh_seconds=30)
            self.assertEqual(verifier("synthetic")["generation"], 1)
            now[0] = 31
            self.assertEqual(verifier("synthetic")["generation"], 2)


if __name__ == "__main__":
    unittest.main()

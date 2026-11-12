import unittest
from datetime import datetime, timezone
from alpha_lab.research.paper_identity import PaperIdentityVerifier, issue_test_token


class PaperIdentityTests(unittest.TestCase):
    def setUp(self):
        self.key = b"x" * 32
        self.verifier = PaperIdentityVerifier(key=self.key, issuer="trusted",
                                              audience="alpha-paper")
        self.now = datetime.fromtimestamp(2000000000, tz=timezone.utc)
        self.claims = dict(sub="alice", iss="trusted", aud="alpha-paper",
                           iat=1999999900, exp=2000000100)

    def test_valid_signature_returns_principal(self):
        principal = self.verifier.verify(issue_test_token(self.key, self.claims), now=self.now)
        self.assertEqual(principal.subject, "alice")

    def test_forged_expired_wrong_audience_and_long_lifetime(self):
        valid = issue_test_token(self.key, self.claims)
        altered = valid[:-2] + ("AA" if valid[-2:] != "AA" else "BB")
        bad_claims = [
            dict(self.claims, exp=2000000000),
            dict(self.claims, aud="another-service"),
            dict(self.claims, iss="untrusted"),
            dict(self.claims, iat=2000000001),
            dict(self.claims, exp=2000001000),
            dict(self.claims, sub="../bob"),
        ]
        for token in [altered, "invalid", "a.b.c"] + [
            issue_test_token(self.key, claims) for claims in bad_claims
        ]:
            with self.subTest(token=token), self.assertRaises(PermissionError):
                self.verifier.verify(token, now=self.now)

    def test_weak_key_and_untrusted_time_rejected(self):
        with self.assertRaises(ValueError):
            PaperIdentityVerifier(key=b"weak", issuer="trusted", audience="alpha-paper")
        with self.assertRaises(ValueError):
            self.verifier.verify(issue_test_token(self.key, self.claims),
                                 now=datetime(2033, 5, 18))


if __name__ == "__main__":
    unittest.main()

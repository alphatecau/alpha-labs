import unittest
from deployment.auth0_staging_settings import staging_auth0_settings

GOOD = {"AUTH0_ISSUER": "https://alpha-labs-dev.au.auth0.com/",
        "AUTH0_CLIENT_ID": "synthetic-staging-client-id",
        "AUTH0_CALLBACK_URL": "https://staging.example.com/auth/callback",
        "ALPHA_BFF_ORIGIN": "https://staging.example.com"}


class Auth0StagingSettingsTests(unittest.TestCase):
    def test_exact_origin_and_callback(self):
        result = staging_auth0_settings(GOOD)
        self.assertEqual(result["issuer"], "https://alpha-labs-dev.au.auth0.com")
        self.assertEqual(result["redirect_uri"], GOOD["AUTH0_CALLBACK_URL"])

    def test_reject_callback_mismatch_and_http(self):
        for key, value in (("AUTH0_CALLBACK_URL", "https://evil.example/auth/callback"),
                           ("AUTH0_CALLBACK_URL", "http://staging.example.com/auth/callback"),
                           ("AUTH0_CALLBACK_URL", "https://staging.example.com/other"),
                           ("ALPHA_BFF_ORIGIN", "https://staging.example.com/path"),
                           ("AUTH0_ISSUER", "https://alpha-labs-dev.au.auth0.com/?unsafe=1")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                staging_auth0_settings({**GOOD, key: value})

    def test_missing_configuration_fails_closed(self):
        for key in GOOD:
            with self.subTest(key=key), self.assertRaises(ValueError):
                staging_auth0_settings({k:v for k,v in GOOD.items() if k != key})


if __name__ == "__main__":
    unittest.main()

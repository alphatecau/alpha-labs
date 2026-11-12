import unittest
from deployment.trusted_site_relay import TrustedSiteRelay

SECRET = "test-only-secret-32-characters-minimum-xyz"


class RelayTests(unittest.TestCase):
    def test_verified_owner_forwarded_only_as_signed_assertion(self):
        seen = []

        def transport(path, headers):
            seen.append((path, headers))
            return {
                "status": "verified_source",
                "data": {"performance": {"status": "unavailable"}},
            }

        relay = TrustedSiteRelay(
            lambda session: {"verified": True, "owner_id": "owner_a"}, transport, SECRET
        )
        self.assertEqual(relay.fetch("session", "summary")["status"], "verified_source")
        self.assertEqual(seen[0][0], "/api/v1/research/summary")
        self.assertTrue(seen[0][1]["Authorization"].startswith("Bearer "))
        self.assertNotIn("owner_a", seen[0][0])

    def test_unverified_session_denied_without_backend_call(self):
        relay = TrustedSiteRelay(
            lambda _: {"verified": False, "owner_id": "owner_a"},
            lambda *args: self.fail("backend contacted"),
            SECRET,
        )
        with self.assertRaises(PermissionError):
            relay.fetch("bad", "runs")

    def test_forged_owner_is_denied(self):
        relay = TrustedSiteRelay(
            lambda _: {"verified": True, "owner_id": "../../owner_b"},
            lambda *args: self.fail("backend contacted"),
            SECRET,
        )
        with self.assertRaises(PermissionError):
            relay.fetch("bad", "runs")

    def test_write_like_resource_denied(self):
        relay = TrustedSiteRelay(
            lambda _: {"verified": True, "owner_id": "owner_a"},
            lambda *args: self.fail("backend contacted"),
            SECRET,
        )
        with self.assertRaises(ValueError):
            relay.fetch("ok", "orders")

    def test_unavailable_backend_fails_closed(self):
        relay = TrustedSiteRelay(
            lambda _: {"verified": True, "owner_id": "owner_a"},
            lambda *args: {"error": "unavailable"},
            SECRET,
        )
        with self.assertRaises(RuntimeError):
            relay.fetch("ok", "runs")


if __name__ == "__main__":
    unittest.main()

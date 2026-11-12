import unittest
from unittest.mock import patch
from deployment.staging_dependency_readiness import create_readiness_check


class Cursor:
    def __init__(
        self,
        grants=(True, True, True, True),
        role=("alpha_session", False, False, False),
    ):
        self.grants, self.role, self.query = grants, role, ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=None):
        self.query = query
        if params is not None:
            assert len(params) == 4 and all(
                p.startswith("public.alpha_") for p in params
            )

    def fetchone(self):
        if "FROM pg_roles" in self.query:
            return self.role
        if "to_regclass" in self.query:
            return self.grants
        return (1,)


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self._cursor


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.state = Cursor()
        self.session = Cursor()
        self.args = dict(
            state_connect=lambda: Connection(self.state),
            session_connect=lambda: Connection(self.session),
            issuer="https://issuer.example.test",
            client_id="example-client",
            tenant_probe=lambda: True,
            jwks_fetch=lambda url: {},
        )

    def check(self):
        return create_readiness_check(**self.args)

    @patch(
        "deployment.staging_dependency_readiness.load_auth0_verifier",
        return_value=object(),
    )
    def test_all_restricted_dependencies_ready(self, verifier):
        self.assertIs(self.check()(), True)
        verifier.assert_called_once()

    @patch("deployment.staging_dependency_readiness.load_auth0_verifier")
    def test_denies_unsafe_db_role(self, verifier):
        self.session.role = ("alpha_session", True, False, False)
        self.assertIs(self.check()(), False)
        verifier.assert_not_called()

    @patch("deployment.staging_dependency_readiness.load_auth0_verifier")
    def test_denies_missing_grants_or_table(self, verifier):
        for grants in (
            (False, True, True, True),
            (True, False, True, True),
            (True, True, False, True),
            (True, True, True, False),
        ):
            with self.subTest(grants=grants):
                self.state.grants = grants
                self.assertIs(self.check()(), False)
        verifier.assert_not_called()

    @patch("deployment.staging_dependency_readiness.load_auth0_verifier")
    def test_denies_missing_tenant_reader(self, verifier):
        self.args["tenant_probe"] = lambda: {"ok": True}
        self.assertIs(self.check()(), False)
        verifier.assert_not_called()

    @patch(
        "deployment.staging_dependency_readiness.load_auth0_verifier",
        side_effect=OSError("JWKS offline"),
    )
    def test_denies_auth0_outage(self, verifier):
        self.assertIs(self.check()(), False)

    def test_denies_database_outage(self):
        def offline():
            raise ConnectionError("postgres down")

        self.args["session_connect"] = offline
        self.assertIs(self.check()(), False)

    def test_denies_missing_probe_at_startup(self):
        self.args["tenant_probe"] = None
        with self.assertRaises(ValueError):
            self.check()


if __name__ == "__main__":
    unittest.main()

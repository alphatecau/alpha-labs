"""Run security unit suites and fail closed on skips, missing tests or errors.

This is NOT a substitute for real Auth0, PostgreSQL or ingress acceptance.
"""
import sys
import unittest

PATTERNS = (
    "test_oidc_verifier.py",
    "test_verified_proxy_ingress.py",
    "test_auth0_discovery_pkce_foundation.py",
    "test_opaque_session_foundation.py",
    "test_auth_session_fail_closed_regressions.py",
)

def main():
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for pattern in PATTERNS:
        found = loader.discover("tests/unit", pattern=pattern, top_level_dir=".")
        count = found.countTestCases()
        if count == 0:
            print(f"FAIL: missing required suite {pattern}", file=sys.stderr)
            return 2
        suite.addTests(found)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print(f"Security unit gate: run={result.testsRun}, skipped={len(result.skipped)}, failures={len(result.failures)}, errors={len(result.errors)}")
    if not result.wasSuccessful() or result.skipped or result.testsRun < 20:
        print("FAIL: security unit acceptance incomplete; release remains NO-GO", file=sys.stderr)
        return 1
    print("PASS: synthetic security unit gate ONLY; real staging and independent review remain required")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

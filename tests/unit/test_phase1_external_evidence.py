import unittest
from datetime import date, datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from alpha_lab.research.phase1_external_evidence import verify_external_etf_evidence


class ExternalEvidenceTests(unittest.TestCase):
    def test_independent_evidence_and_adversarial_cases(self):
        with TemporaryDirectory() as tmp:
            cal = Path(tmp) / "calendar.csv"
            actions = Path(tmp) / "actions.csv"
            cal.write_text("date,symbol,is_session\n2025-01-02,SPY,true\n")
            actions.write_text("date,symbol,split_factor,cash_dividend\n2025-01-02,SPY,1,0\n")
            args = dict(
                symbol="SPY", observed_sessions={date(2025, 1, 2)},
                calendar_csv=cal, calendar_sha256=sha256(cal.read_bytes()).hexdigest(),
                actions_csv=actions, actions_sha256=sha256(actions.read_bytes()).hexdigest(),
                calendar_publisher="exchange-calendar-provider",
                actions_publisher="issuer-action-provider",
                calendar_retrieved_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
                actions_retrieved_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
                as_of=datetime(2025, 1, 4, tzinfo=timezone.utc),
            )
            result = verify_external_etf_evidence(**args)
            self.assertEqual(result["status"], "EVIDENCE_CONSISTENT_NOT_AUTHENTICATED")
            self.assertFalse(result["eligible_for_strategy_promotion"])
            self.assertFalse(result["publisher_identity_verified"])
            with self.assertRaisesRegex(ValueError, "Distinct"):
                verify_external_etf_evidence(**dict(args, actions_publisher=args["calendar_publisher"]))
            with self.assertRaisesRegex(ValueError, "Future"):
                verify_external_etf_evidence(**dict(args, actions_retrieved_at=args["as_of"] + timedelta(days=1)))
            with self.assertRaisesRegex(ValueError, "hash"):
                verify_external_etf_evidence(**dict(args, calendar_sha256="0" * 64))
            with self.assertRaisesRegex(ValueError, "session mismatch"):
                verify_external_etf_evidence(**dict(args, observed_sessions={date(2025, 1, 3)}))
            actions.write_text("date,symbol,split_factor,cash_dividend\n2025-01-02,SPY,NaN,0\n")
            with self.assertRaisesRegex(ValueError, "corporate-action values"):
                verify_external_etf_evidence(**dict(args, actions_sha256=sha256(actions.read_bytes()).hexdigest()))
            actions.write_text("date,symbol,split_factor,cash_dividend\n")
            with self.assertRaisesRegex(ValueError, "Incomplete evidence"):
                verify_external_etf_evidence(**dict(args, actions_sha256=sha256(actions.read_bytes()).hexdigest()))


if __name__ == "__main__":
    unittest.main()

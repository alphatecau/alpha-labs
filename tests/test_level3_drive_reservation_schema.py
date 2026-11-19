"""Ensure the independent Drive reservation migration remains least-privilege."""
from pathlib import Path
import unittest

SQL = Path(__file__).resolve().parents[1] / "docs" / "LEVEL3_DRIVE_RESERVATION_STAGING.sql"


class ReservationSchemaTests(unittest.TestCase):
    def test_constraints_and_no_grants(self):
        sql = SQL.read_text()
        for term in (
            "CREATE TABLE IF NOT EXISTS level3_custody.drive_upload_reservation",
            "PRIMARY KEY (parent_id, sha256)",
            "state IN ('reserved', 'verified')",
            "length(file_id) BETWEEN 1 AND 256",
            "REVOKE SELECT ON TABLE level3_custody.drive_upload_reservation",
            "level3_broker_login",
            "level3_auditor_login",
        ):
            self.assertIn(term, sql)
        for forbidden in ("DROP TABLE", "DROP SCHEMA", "TRUNCATE TABLE", "GRANT SELECT", "GRANT ALL"):
            self.assertNotIn(forbidden, sql.upper())

    def test_revocation_is_conditional_for_ci(self):
        sql = SQL.read_text()
        self.assertIn("IF EXISTS (SELECT 1 FROM pg_roles", sql)
        self.assertIn("DO $level3_revoke$", sql)

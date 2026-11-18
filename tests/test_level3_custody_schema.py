"""Validate proposed Level 3 custody migration is conservative and scoped."""
from pathlib import Path
import unittest

SQL=Path(__file__).resolve().parents[1]/"deployment"/"level3_custody_schema.sql"

class CustodySchemaTests(unittest.TestCase):
    def test_migration_contract(self):
        sql=SQL.read_text()
        for term in ("BEGIN;","COMMIT;","level3_custody.remote_nonce",
                     "level3_custody.approval_claim","level3_custody.audit_event",
                     "PRIMARY KEY","CHECK","previous_hash","event_hash"):
            self.assertIn(term,sql)
        for forbidden in ("DROP TABLE","DROP SCHEMA","TRUNCATE","CASCADE","ALTER ROLE","CREATE EXTENSION"):
            self.assertNotIn(forbidden,sql.upper())

if __name__=="__main__":
    unittest.main()

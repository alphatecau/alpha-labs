"""Disposable real PostgreSQL audit chain -> signed durable auditor checkpoints."""
import os
import tempfile
import unittest
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tools.level3_staging.auditor_checkpoint import verify_sign_and_retain
from tools.level3_staging.auditor_file_store import AuditorFileStore
from tools.level3_staging.postgres_custody import append_audit, verify_audit_chain


@unittest.skipUnless(os.environ.get("LEVEL3_TEST_POSTGRES_DSN"), "disposable CI database required")
class PostgresAuditorCheckpointE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.conn = psycopg.connect(os.environ["LEVEL3_TEST_POSTGRES_DSN"], autocommit=True)
        if cls.conn.execute("SELECT current_database()").fetchone()[0] != "level3_ci_test":
            cls.conn.close()
            raise RuntimeError("refusing non-disposable database")
        cls.conn.execute(Path("deployment/level3_custody_schema.sql").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_real_chain_to_two_signed_persistent_checkpoints(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / "auditor"
        root.mkdir(mode=0o700)
        store = AuditorFileStore(root)
        key = Ed25519PrivateKey.generate()
        public = key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        audience = "alpha-labs-level3:ci_" + uuid.uuid4().hex
        nonce = uuid.uuid4().hex + uuid.uuid4().hex
        digest = "d" * 64
        append_audit(self.conn, str(uuid.uuid4()), nonce, "claimed", digest)
        first = verify_sign_and_retain(self.conn, audience, key, store, public)
        append_audit(self.conn, str(uuid.uuid4()), nonce, "complete", digest)
        second = verify_sign_and_retain(self.conn, audience, key, store, public)
        self.assertGreater(second["signed"]["receipt"]["count"],
                           first["signed"]["receipt"]["count"])
        self.assertEqual(second["signed"]["receipt"]["head_hash"],
                         verify_audit_chain(self.conn)["head_hash"])
        reopened = AuditorFileStore(root)
        self.assertEqual(reopened.read_latest(audience)["receipt"],
                         second["signed"]["receipt"])


if __name__ == "__main__":
    unittest.main()

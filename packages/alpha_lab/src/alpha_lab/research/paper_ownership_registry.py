"""Research-only, fail-closed verified-principal account registry.

Account ownership is derived exclusively from an upstream verified principal.
Provisioning is an explicit trusted-server action, never a browser endpoint.
"""
import hashlib
import re
import sqlite3

from alpha_lab.research.paper_account_service import VerifiedPrincipal


class PaperOwnershipRegistry:
    def __init__(self, database):
        if not isinstance(database, str) or not database:
            raise ValueError("Explicit registry database path required")
        self.conn = sqlite3.connect(database, isolation_level=None)
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS paper_ownership(
            owner_digest TEXT NOT NULL, account TEXT NOT NULL,
            active INTEGER NOT NULL CHECK(active IN (0,1)),
            PRIMARY KEY(owner_digest, account))""")

    @staticmethod
    def _key(principal, account):
        if not isinstance(principal, VerifiedPrincipal):
            raise PermissionError("Verified principal required")
        if not isinstance(principal.subject, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", principal.subject):
            raise PermissionError("Invalid subject")
        if not isinstance(principal.issuer, str) or not principal.issuer.startswith("https://") or len(principal.issuer) > 255:
            raise PermissionError("Invalid issuer")
        if not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", account):
            raise PermissionError("Invalid account")
        digest = hashlib.sha256((principal.issuer + "\0" + principal.subject).encode()).hexdigest()
        return digest, account

    def provision(self, principal, account):
        key = self._key(principal, account)
        self.conn.execute("INSERT INTO paper_ownership(owner_digest,account,active) VALUES(?,?,1) "
                          "ON CONFLICT(owner_digest,account) DO UPDATE SET active=1", key)

    def revoke(self, principal, account):
        key = self._key(principal, account)
        self.conn.execute("UPDATE paper_ownership SET active=0 WHERE owner_digest=? AND account=?", key)

    def require(self, principal, account):
        key = self._key(principal, account)
        return self._require_key(key)

    def require_owner_id(self, owner_id, account):
        """Trusted session adapter only; never accept an owner from a browser."""
        if (not isinstance(owner_id, str) or not re.fullmatch(r"oidc_[a-f0-9]{64}", owner_id)
                or not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", account)):
            raise PermissionError("Verified owner ID and account required")
        return self._require_key((owner_id[5:], account))

    def _require_key(self, key):
        row = self.conn.execute("SELECT active FROM paper_ownership WHERE owner_digest=? AND account=?", key).fetchone()
        if row is None or row[0] != 1:
            raise PermissionError("Paper account not provisioned")
        return True

    def close(self):
        self.conn.close()

"""Server-owned SQLite account ownership registry for offline staging research.

Provisioning is administrative only. The public WSGI status endpoint cannot
create, transfer, or enumerate accounts. One-process prototype; not a hosted
multi-tenant identity database.
"""
import sqlite3
from pathlib import Path

from alpha_lab.research.paper_account_service import VerifiedPrincipal


class PaperOwnershipRegistry:
    def __init__(self, path):
        path = Path(path)
        if not path.is_absolute() or not path.parent.is_dir():
            raise ValueError("Ownership database requires existing absolute parent")
        self.connection = sqlite3.connect(str(path), timeout=5)
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS paper_accounts (
            issuer TEXT NOT NULL,
            subject TEXT NOT NULL,
            account TEXT NOT NULL,
            active INTEGER NOT NULL CHECK(active IN (0,1)),
            PRIMARY KEY(issuer, subject, account)
        )""")
        self.connection.commit()

    def provision(self, principal, account):
        self._validate(principal, account)
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO paper_accounts(issuer,subject,account,active) VALUES(?,?,?,1)",
                (principal.issuer, principal.subject, account))

    def revoke(self, principal, account):
        self._validate(principal, account)
        with self.connection:
            self.connection.execute(
                "UPDATE paper_accounts SET active=0 WHERE issuer=? AND subject=? AND account=?",
                (principal.issuer, principal.subject, account))

    def authorised(self, principal, account):
        self._validate(principal, account)
        row = self.connection.execute(
            "SELECT active FROM paper_accounts WHERE issuer=? AND subject=? AND account=?",
            (principal.issuer, principal.subject, account)).fetchone()
        return row is not None and row[0] == 1

    @staticmethod
    def _validate(principal, account):
        import re
        if not isinstance(principal, VerifiedPrincipal) or not isinstance(principal.issuer, str) or not principal.issuer:
            raise PermissionError("Verified principal required")
        if not isinstance(principal.subject, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", principal.subject):
            raise PermissionError("Invalid subject")
        if not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", account):
            raise PermissionError("Invalid account")

    def close(self):
        self.connection.close()


class OwnedPaperStatus:
    """Read-only wrapper enforcing persistent ownership on every status lookup."""
    def __init__(self, accounts, ownership):
        self.accounts = accounts
        self.ownership = ownership

    def status(self, principal, account):
        if not self.ownership.authorised(principal, account):
            raise PermissionError("Account not owned or revoked")
        return self.accounts.status(principal, account)

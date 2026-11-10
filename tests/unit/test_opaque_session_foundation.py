import unittest
from datetime import datetime, timezone, timedelta
from deployment.postgres_opaque_sessions import PostgresOpaqueSessions

class Cursor:
    def __init__(self, state): self.state=state; self.row=None
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def execute(self,sql,params):
        if sql.startswith("INSERT"):
            digest,owner,expiry=params
            self.state[digest]=(owner,expiry)
        elif sql.startswith("SELECT"):
            digest,now=params
            rec=self.state.get(digest)
            self.row=(rec[0],) if rec and rec[1]>now else None
        elif sql.startswith("DELETE"):
            self.state.pop(params[0],None)
        else: raise AssertionError("unexpected SQL")
    def fetchone(self): return self.row

class Connection:
    def __init__(self,state): self.state=state
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def cursor(self): return Cursor(self.state)

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.state={}
        self.now=datetime(2026,1,1,tzinfo=timezone.utc)
        self.sessions=PostgresOpaqueSessions(lambda: Connection(self.state),clock=lambda:self.now)
    def test_create_resolve_revoke(self):
        token=self.sessions.create("subject","https://issuer.example/")
        owner=self.sessions.resolve_owner(token)
        self.assertTrue(owner.startswith("oidc_"))
        self.assertNotIn(token,str(self.state))
        self.sessions.revoke(token)
        with self.assertRaises(PermissionError):self.sessions.resolve_owner(token)
    def test_expiry(self):
        token=self.sessions.create("subject","https://issuer.example/")
        self.now+=timedelta(minutes=31)
        with self.assertRaises(PermissionError):self.sessions.resolve_owner(token)
    def test_owner_matches_oidc_verifier_identity_contract(self):
        import hashlib
        token=self.sessions.create("subject","https://issuer.example/")
        expected="oidc_"+hashlib.sha256(b"https://issuer.example/\\x00subject".replace(b"\\x00",b"\x00")).hexdigest()
        self.assertEqual(self.sessions.resolve_owner(token),expected)
    def test_invalid_token(self):
        with self.assertRaises(PermissionError):self.sessions.resolve_owner("bad")
if __name__=="__main__":unittest.main()

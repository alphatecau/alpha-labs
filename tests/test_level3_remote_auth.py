"""Remote authentication signature, expiry, body and audience tests."""
import base64
import hashlib
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from tools.level3_staging.remote_auth import RemoteDenied,canonical,verify,verify_keyed

class RemoteAuthTests(unittest.TestCase):
    def setUp(self):
        self.private=Ed25519PrivateKey.generate()
        self.public=self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        self.body=b'{"path":"docs/level3-staging/a.md"}'
        self.claims={"version":1,"method":"POST","path":"/v1/signed-create",
            "body_sha256":hashlib.sha256(self.body).hexdigest(),"audience":"alpha-labs-level3",
            "nonce":"a"*64,"expires_at":1100}
    def envelope(self):
        return {"claims":self.claims.copy(),
            "signature":base64.b64encode(self.private.sign(canonical(self.claims))).decode()}
    def keyed_envelope(self):
        claims={**self.claims,"audience":"alpha-labs-level3:staging","key_id":"operator-1"}
        return {"claims":claims,"signature":base64.b64encode(
            self.private.sign(canonical(claims))).decode()}

    def test_keyed_valid(self):
        self.assertEqual(verify_keyed(self.keyed_envelope(),self.body,
            {"operator-1":self.public},"alpha-labs-level3:staging",now=1000),"a"*64)

    def test_keyed_prod_replay_denied(self):
        with self.assertRaises(RemoteDenied):
            verify_keyed(self.keyed_envelope(),self.body,
                {"operator-1":self.public},"alpha-labs-level3:production",now=1000)

    def test_keyed_unknown_key_denied(self):
        with self.assertRaises(RemoteDenied):
            verify_keyed(self.keyed_envelope(),self.body,
                {"other":self.public},"alpha-labs-level3:staging",now=1000)

    def test_keyed_key_id_tampering_denied(self):
        envelope=self.keyed_envelope()
        envelope["claims"]["key_id"]="operator-2"
        with self.assertRaises(RemoteDenied):
            verify_keyed(envelope,self.body,
                {"operator-1":self.public,"operator-2":self.public},
                "alpha-labs-level3:staging",now=1000)

    def test_valid(self):
        self.assertEqual(verify(self.envelope(),self.body,self.public,"alpha-labs-level3",now=1000),"a"*64)
    def test_tampered_body(self):
        with self.assertRaises(RemoteDenied):
            verify(self.envelope(),b"tampered",self.public,"alpha-labs-level3",now=1000)
    def test_wrong_audience(self):
        with self.assertRaises(RemoteDenied):
            verify(self.envelope(),self.body,self.public,"another",now=1000)
    def test_expired(self):
        with self.assertRaises(RemoteDenied):
            verify(self.envelope(),self.body,self.public,"alpha-labs-level3",now=1100)
    def test_overlong_expiry(self):
        self.claims["expires_at"]=1201
        with self.assertRaises(RemoteDenied):
            verify(self.envelope(),self.body,self.public,"alpha-labs-level3",now=1000)
    def test_bad_signature(self):
        envelope=self.envelope()
        envelope["signature"]=base64.b64encode(b"0"*64).decode()
        with self.assertRaises(RemoteDenied):
            verify(envelope,self.body,self.public,"alpha-labs-level3",now=1000)
    def test_wrong_method(self):
        self.claims["method"]="GET"
        with self.assertRaises(RemoteDenied):
            verify(self.envelope(),self.body,self.public,"alpha-labs-level3",now=1000)

if __name__=="__main__":
    unittest.main()

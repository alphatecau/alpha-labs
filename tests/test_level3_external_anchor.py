import base64
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from tools.level3_staging.external_anchor import canonical_receipt,verify_anchor

class ExternalAnchorTests(unittest.TestCase):
    def setUp(self):
        self.private=Ed25519PrivateKey.generate()
        self.public=self.private.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.head={"count":2,"last_sequence":4,"head_hash":"a"*64}
        self.receipt={"version":1,"audience":"alpha-labs-level3:staging",**self.head}
    def signed(self):
        return {"receipt":self.receipt.copy(),"signature":base64.b64encode(
            self.private.sign(canonical_receipt(self.receipt))).decode()}
    def test_valid(self):
        self.assertTrue(verify_anchor(self.signed(),self.public,self.receipt["audience"],self.head))
    def test_rollback_detected(self):
        with self.assertRaises(ValueError):
            verify_anchor(self.signed(),self.public,self.receipt["audience"],
                {"count":1,"last_sequence":2,"head_hash":"b"*64})
    def test_cross_environment_denied(self):
        with self.assertRaises(ValueError):
            verify_anchor(self.signed(),self.public,"alpha-labs-level3:production",self.head)
    def test_signature_tampering_denied(self):
        signed=self.signed()
        signed["receipt"]["count"]=1
        with self.assertRaises(ValueError):
            verify_anchor(signed,self.public,self.receipt["audience"],self.head)

if __name__=="__main__":
    unittest.main()

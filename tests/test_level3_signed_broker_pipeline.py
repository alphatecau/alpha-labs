"""Signed broker pipeline must deny before touching custody without safety gates."""
import hashlib
import json
import unittest
from unittest.mock import patch
from tools.level3_staging.signed_broker_pipeline import signed_create,BrokerDisabled
from tools.level3_staging.postgres_custody import CustodyDenied

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.payload=b"hello"
        self.path="docs/level3-staging/hello.md"
        self.nonce="a"*64
        self.body=json.dumps({"approval_nonce":self.nonce,"path":self.path,
            "payload_sha256":hashlib.sha256(self.payload).hexdigest()}).encode()
    def call(self,**kwargs):
        return signed_create(None,"/nonexistent",{"claims":{},"signature":""},
            self.body,{},"alpha-labs-level3:staging",self.nonce,self.path,
            self.payload,**kwargs)
    def test_disabled_by_default(self):
        with self.assertRaises(BrokerDisabled):
            self.call()
    def test_caller_cannot_override_server_disabled_mode(self):
        with patch.dict("os.environ",{"LEVEL3_CUSTODY_MODE":"disabled"}):
            with self.assertRaises(BrokerDisabled):
                self.call(durable_storage=True,independent_anchor=True,operator_approved=True)
    def test_production_audience_denied(self):
        with patch.dict("os.environ",{"LEVEL3_CUSTODY_MODE":"enabled"}):
            with self.assertRaises(BrokerDisabled):
                signed_create(None,"/nonexistent",{},self.body,{},
                    "alpha-labs-level3:production",self.nonce,self.path,self.payload,
                    durable_storage=True,independent_anchor=True,operator_approved=True)
    def test_no_anchor_denied(self):
        with self.assertRaises(BrokerDisabled):
            self.call(durable_storage=True,operator_approved=True)
    def test_no_operator_approval_denied(self):
        with self.assertRaises(BrokerDisabled):
            self.call(durable_storage=True,independent_anchor=True)
    def test_no_durable_storage_denied(self):
        with self.assertRaises(BrokerDisabled):
            self.call(independent_anchor=True,operator_approved=True)
    def test_oversized_payload_denied_before_auth_or_db(self):
        # Exercise the payload-size gate, not the disabled-mode gate.
        with patch.dict("os.environ",{"LEVEL3_CUSTODY_MODE":"enabled"}):
            with patch("tools.level3_staging.signed_broker_pipeline.verify_keyed") as auth:
                with patch("tools.level3_staging.signed_broker_pipeline.claim_with_audit") as db:
                    with self.assertRaises(CustodyDenied):
                        signed_create(None,"/nonexistent",{},self.body,{},
                            "alpha-labs-level3:staging",self.nonce,self.path,b"x"*32769,
                            durable_storage=True,independent_anchor=True,operator_approved=True)
                    auth.assert_not_called()
                    db.assert_not_called()

    def test_signed_body_mismatch_denied_without_custody(self):
        # Auth succeeds, but signed body must match the exact approved intent.
        with patch.dict("os.environ",{"LEVEL3_CUSTODY_MODE":"enabled"}):
            with patch("tools.level3_staging.signed_broker_pipeline.verify_keyed",return_value="b"*64) as auth:
                with patch("tools.level3_staging.signed_broker_pipeline.claim_with_audit") as db:
                    with self.assertRaises(CustodyDenied):
                        signed_create(None,"/nonexistent",{},self.body,{},
                            "alpha-labs-level3:staging",self.nonce,
                            "docs/level3-staging/different.md",self.payload,
                            durable_storage=True,independent_anchor=True,operator_approved=True)
                    auth.assert_called_once()
                    db.assert_not_called()

    def test_malformed_signed_body_denied_without_custody(self):
        with patch.dict("os.environ",{"LEVEL3_CUSTODY_MODE":"enabled"}):
            with patch("tools.level3_staging.signed_broker_pipeline.verify_keyed",return_value="b"*64):
                with patch("tools.level3_staging.signed_broker_pipeline.claim_with_audit") as db:
                    with self.assertRaises(CustodyDenied):
                        signed_create(None,"/nonexistent",{},b"{invalid",{},
                            "alpha-labs-level3:staging",self.nonce,self.path,self.payload,
                            durable_storage=True,independent_anchor=True,operator_approved=True)
                    db.assert_not_called()

    def test_auth_failure_denied_before_custody(self):
        from tools.level3_staging.remote_auth import RemoteDenied
        with patch.dict("os.environ",{"LEVEL3_CUSTODY_MODE":"enabled"}):
            with patch("tools.level3_staging.signed_broker_pipeline.verify_keyed",
                       side_effect=RemoteDenied("invalid signature")):
                with patch("tools.level3_staging.signed_broker_pipeline.claim_with_audit") as db:
                    with self.assertRaises(RemoteDenied):
                        self.call(durable_storage=True,independent_anchor=True,operator_approved=True)
                    db.assert_not_called()

if __name__=="__main__":
    unittest.main()

"""Staging-only signed-create orchestration; not an HTTP listener.

Fails closed unless independent durable file storage and auditor-controlled
external anchoring have been provisioned and approved. Render free disk is not
acceptable custody. The caller must supply a validated approved intent.
"""
import hashlib
import json
import uuid
from tools.level3_staging.remote_auth import verify_keyed
from tools.level3_staging.postgres_custody import (
    CustodyDenied,claim_with_audit,complete_with_audit,
)
from tools.level3_staging.intent_recovery import reconcile_intent

class BrokerDisabled(CustodyDenied):
    pass

def signed_create(conn,root,envelope,request_body,public_keys,audience,
                  approval_nonce,path,payload,*,durable_storage=False,
                  independent_anchor=False,operator_approved=False,
                  fault=None):
    if not (durable_storage and independent_anchor and operator_approved):
        raise BrokerDisabled("durable storage, independent audit anchor and approval required")
    if not isinstance(payload,bytes) or len(payload)>32768:
        raise CustodyDenied("invalid payload size")
    digest=hashlib.sha256(payload).hexdigest()
    # Authentication precedes any database or filesystem access.
    remote_nonce=verify_keyed(envelope,request_body,public_keys,audience)
    try:
        body=json.loads(request_body)
    except (ValueError,TypeError) as exc:
        raise CustodyDenied("invalid request body") from exc
    if (not isinstance(body,dict) or set(body)!={"approval_nonce","path","payload_sha256"} or
        body["approval_nonce"]!=approval_nonce or body["path"]!=path or
        body["payload_sha256"]!=digest):
        raise CustodyDenied("signed request does not bind approval, path and payload")
    if fault=="before_claim":
        raise RuntimeError("injected before claim")
    claim_with_audit(conn,remote_nonce,approval_nonce,path,digest,str(uuid.uuid4()))
    if fault=="after_claim":
        raise RuntimeError("injected after durable claim")
    reconcile_intent(root,approval_nonce,path,digest,payload,
                     fault=fault if fault in ("before_write","after_temp","after_link") else None)
    if fault=="before_completion":
        raise RuntimeError("injected before completion")
    return complete_with_audit(conn,approval_nonce,path,digest,str(uuid.uuid4()))

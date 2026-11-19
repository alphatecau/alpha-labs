"""Fail-closed preflight for independent auditor Drive custody.

This is an offline policy check. Caller must supply freshly fetched Drive
metadata using the auditor identity, never broker-supplied metadata.
"""
from tools.level3_staging.drive_permission_guard import verify_auditor_folder


def verify_independent_custody(metadata, auditor_email, primary_email, folder_id):
    if not isinstance(folder_id, str) or not folder_id:
        raise ValueError("missing folder identity")
    if not isinstance(metadata, dict) or metadata.get("id") != folder_id:
        raise ValueError("auditor folder identity mismatch")
    verify_auditor_folder(metadata, auditor_email)
    permissions = metadata["permissions"]
    roles = {}
    for item in permissions:
        email = item.get("emailAddress")
        if not isinstance(email, str) or not email.strip():
            raise ValueError("missing permission identity")
        email = email.lower()
        if email in roles:
            raise ValueError("duplicate permission identity")
        roles[email] = item["role"]
    if not isinstance(primary_email, str) or not primary_email:
        raise ValueError("missing primary account")
    if auditor_email.lower() == primary_email.lower():
        raise ValueError("auditor and primary identities must differ")
    if roles.get(primary_email.lower()) != "reader":
        raise ValueError("primary account must have reader-only access")
    if len(roles) != len(permissions) or set(roles) != {
        auditor_email.lower(), primary_email.lower()
    }:
        raise ValueError("unexpected custody permissions")
    return True

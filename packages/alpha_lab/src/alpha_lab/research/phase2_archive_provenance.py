"""Explicit archive provenance gates. Metadata alone never proves historical capture."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from alpha_lab.research.phase1_signed_archive import verify_signed_archive


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_archive_provenance(*, archive_path, research_path, manifest_path,
                              signature_path, expected_archive_id, decision_time,
                              trust_registry, provider_id, attestation=None,
                              max_file_bytes=256 * 1024 * 1024):
    """Require independently provisioned registry key and optional capture attestation.

    trust_registry is operator-managed and must be provisioned through an
    independently authenticated channel, never the dataset under test.
    attestation is only an external review record, not cryptographic proof.
    """
    if not isinstance(trust_registry, dict) or provider_id not in trust_registry:
        raise ValueError("Unrecognised archive provider")
    record = trust_registry[provider_id]
    if not isinstance(record, dict) or record.get("onboarding") != "independently_verified":
        raise ValueError("Provider key not independently onboarded")
    key = record.get("ed25519_public_key")
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("Invalid trusted provider key")
    verified = verify_signed_archive(
        archive_path=archive_path, research_path=research_path,
        manifest_path=manifest_path, signature_path=signature_path,
        trusted_ed25519_public_key=key,
        expected_archive_id=expected_archive_id, decision_time=decision_time,
        max_file_bytes=max_file_bytes,
    )
    # A manually supplied attestation record is not a verified trusted
    # timestamp. Do not elevate eligibility or historical provenance.
    verified["trusted_key_registry_entry_present"] = True
    verified["archive_provider_identity_independently_verified"] = False
    verified["historical_capture_independently_attested"] = False
    verified["external_attestation_supplied"] = attestation is not None
    verified["eligible_for_strategy_promotion"] = False
    verified["status"] = "PROVENANCE_REVIEW_REQUIRED"
    return verified

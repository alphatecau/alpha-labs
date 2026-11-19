"""Conservative, evidence-only Level 3 custody activation gate."""

REQUIRED_GATES = frozenset({
    "auditor_oauth_scopes",
    "auditor_folder_ownership",
    "auditor_folder_permissions",
    "independent_signing_key",
    "external_monotonic_checkpoint",
    "full_chain_verification",
    "drive_upload_readback",
    "ambiguous_upload_recovery",
    "render_neon_tls",
    "physical_android_acceptance",
    "security_review",
    "operator_release_approval",
})


def evaluate_release(evidence):
    """Missing, unknown, or non-boolean evidence always blocks activation.

    This evaluates asserted evidence only; it does not independently attest
    that a remote gate actually passed. A trusted reviewer must validate each.
    """
    if not isinstance(evidence, dict):
        return {"allowed": False, "missing": sorted(REQUIRED_GATES)}
    missing = sorted(gate for gate in REQUIRED_GATES if evidence.get(gate) is not True)
    return {"allowed": not missing, "missing": missing}

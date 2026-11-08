# Phase 2 — archive provenance and bounded integrity review

Research-only draft. The original signed archive verifier now uses bounded manifest/signature reads, streaming SHA-256 of archive and research file bytes, a configurable file limit (default 256 MiB), and rejects symlinks and non-regular files. Existing signed manifest verification and chronology checks remain in place.

The additional provenance gate requires an operator-managed trusted-key registry entry marked as independently onboarded. **That marker is an assertion**, not independent proof: the software cannot determine whether a registry entry was legitimately obtained. An arbitrary caller can create a fake registry. Likewise, a caller-supplied attestation is not a trusted timestamp. The gate intentionally returns `PROVENANCE_REVIEW_REQUIRED` and `eligible_for_strategy_promotion=False` even when all supplied checks pass.

**External verification required before provenance can be trusted:** obtain archive provider identity and Ed25519 public key from independently authenticated provider documentation; retain a signed, auditable onboarding record; verify an external immutable capture timestamp and its link to the exact signed bytes; assess provider revocation and key rotation; use an independently reviewed immutable trust store not supplied by the dataset or strategy under evaluation.

No historical market dataset or archive provider has been independently verified. This is not proof of historical availability, strategy profitability, broker readiness, or trading authorisation. Preserve all previous rejected strategy evidence and keep trading/deployment disabled.

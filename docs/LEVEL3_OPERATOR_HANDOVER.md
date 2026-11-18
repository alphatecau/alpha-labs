# Level 3 MCP — operator handover and security hold

Status: **DRAFT / NO DEPLOYMENT**. PR #181 is not a production release.

## Implemented in this branch
- Signed create-only tool limited to docs/level3-staging/*.md and tests/level3-staging/*.txt (simple names only, <=32 KiB).
- One-time SQLite approval nonce claims, O_EXCL file creation and fsync.
- Separate offline operator approval signer; private key is not an MCP tool argument.
- Signed, short-lived readiness attestation checked at stdio startup.
- Startup storage path checks and audit hash-chain verification.
- Optional direct-engine audit recording; stdio startup requires LEVEL3_AUDIT_PATH.
- Tests for replay, tampering, malformed requests and simulated post-claim interruption.

## Important security limitations
- Signed readiness claims are **attestations**, not proof that separate Android UIDs or independent storage exist. The signing authority must independently validate every gate.
- Same-UID Termux processes cannot isolate signing keys or SQLite files from one another. Separate Termux tabs do not provide a trust boundary.
- Hash chaining is tamper-evident only if the latest hash is anchored outside the worker's control. Current local journal is not independently anchored.
- The claim and journal are separate commits; interruption between them can leave a consumed nonce without a claim audit entry. Do not treat this as an atomic audited transaction.
- Audit appends are not protected against concurrent writers; enforce a single worker and externally anchored logging until fixed.
- A signed readiness attestation currently uses the same verification public key configured for approvals. Production should separate approval and deployment attestations.
- Signed readiness does not itself verify the real environment or enforce audit anchoring.
- Recovery inspector reports claimed records and never resets them; manual investigation is mandatory.

## Tomorrow — operator actions, only after engineering gates pass
1. Review and merge PR #181 **only after** all checks and security review pass.
2. Create an isolated execution identity or remote broker for approval signing, ledger ownership and immutable audit anchoring. Do not store the private key under the worker's Android UID.
3. Prepare a fresh isolated checkout and private storage directories. Do not alter the existing Level 2 gateway or research checkout.
4. Verify independent key inaccessibility, ledger protection, audit anchoring, interruption recovery and Android acceptance.
5. Issue a short-lived readiness attestation only after collecting evidence for every gate.
6. Register the **separate** Level 3 connector and authenticated tunnel, and exercise create/replay/deny tests.

**No production tunnel, connector registration, or live trading permission is authorised by this document.**

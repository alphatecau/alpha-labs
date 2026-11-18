# Level 3 MCP: deployment boundary and acceptance gate

## Runtime entrypoint
Only `python -m tools.level3_staging.mcp_signed_stdio` is a candidate signed-write runtime. `controlled_write.py` and `mcp_proposals.py` are historical offline prototypes, not approved runtime entrypoints. The Android `os.link` failure in the legacy test suite is tracked as a portability defect; do not patch it by weakening create-only or approval semantics.

## Security topology
The Termux application UID is **untrusted for custody**. All Termux sessions, directories and processes within that UID share access and are not independent trust domains.

The Level 3 worker may hold a *public* Ed25519 approval verification key. It must not hold the private approval key, independently protected ledger/audit credentials, or authority to sign its own readiness attestations.

A separately authenticated broker, different Android application UID, or independent server account must:
1. Custody the signing private key; never expose it to MCP worker or ChatGPT tools.
2. Own the authoritative nonce ledger and audit anchor, with permissions inaccessible to the worker.
3. Verify exact path, content digest, expiry, unique nonce, and operator approval before issuing a signature.
4. Retain an off-worker anchor of the audit chain and reject rollback.
5. Provide signed readiness evidence based on measured security conditions, not self-reported booleans.

**Implementation limitation:** Current signed-create worker writes SQLite and audit files directly. It cannot enforce independently protected ledger/audit custody while using the same Termux UID. The architecture must be refactored to use a broker before production activation. Directory mode 0700 does not solve same-UID access.

## Acceptance sequence
- GitHub CI all required checks green.
- Android targeted signed tests PASS, including real process termination and audit concurrency.
- `python -m tools.level3_staging.android_probe` PASS on device.
- Verify startup denies missing or invalid readiness and unreconciled audit.
- Broker identity, credential and storage separation independently demonstrated.
- Audit anchor and replay/rollback resistance demonstrated.
- Isolated end-to-end MCP initialize, tools/list, denied call, approved create and replay rejection demonstrated against broker-backed runtime.
- Connector registered separately; existing Level 2 gateway unchanged.

**Deployment decision: NO-GO** until the broker and all acceptance evidence exist. No live-trading, shell, arbitrary file write or repository push permission.

# Level 3 controlled MCP write — staging design

**Status: DESIGN ONLY — NOT DEPLOYED, NOT APPROVED FOR NETWORK ACCESS.**

## Boundary

Retain the existing Level 2 Termux MCP connector as read-only and unchanged. A Level 3 connector must use a separate MCP server, identity, tunnel profile, process, UID and dedicated writable staging checkout. No shared writable mount or inherited Level 2 credential.

## Initial operation

Create-only UTF-8 files (maximum 32 KiB) under `docs/level3-staging/<simple-name>.md` or `tests/level3-staging/<simple-name>.txt`. No edits, deletes, arbitrary paths, shell, Git pushes, secrets, trading, deployments or live orders. Reject symlinks, nested paths, existing targets and all unrecognised inputs.

## Two-phase approval

1. `propose_create` returns canonical relative path, byte count and SHA-256 digest, without writing.
2. An independent trusted operator reviews the exact content and creates a short-lived approval record outside the MCP service's writable scope. Approval binds operation, path, digest, identity and expiry.
3. `apply_create` checks approval and filesystem isolation, consumes the approval exactly once with a crash-safe transaction, creates the target exclusively and records audit evidence. On uncertainty, fail closed and require manual reconciliation.

**Do not rely on unlinking or hard-linking a JSON approval file as an atomic concurrent authorisation mechanism.** Use a durable transactional ledger or equivalent exclusive, atomic claim, with independent approval authority. A separate approval signing key must not be accessible to the MCP server.

## Required implementation controls

- Descriptor-relative `openat` traversal with `O_NOFOLLOW` and directory file descriptors; filesystem permissions enforce the sandbox even if application validation fails.
- Exclusive creation, file and directory `fsync`, bounded request size, rate limits and per-request identifiers.
- Approval replay resistance under concurrency, crash and restart; signed or independently authenticated approvals with least-privilege keys.
- Tamper-evident, crash-recoverable audit log and deterministic inspection of partial writes.
- Separate process credentials, localhost-only binding, authenticated tunnel and deny-by-default network exposure.
- Negative tests for traversal, symlink swaps, directory replacement, stale/mismatched/replayed approvals, concurrent claims, disk-full and process interruption.

## Release gates

1. Offline implementation and test coverage; CI passes on PR.
2. Independent security review and threat model approval.
3. Dedicated Android staging checkout and isolated service; no write exposure to the existing research checkout.
4. Explicit operator approval before connector registration or production routing.
5. End-to-end authorised create test and negative tests; verify Level 2 remains read-only.

No restart, production activation, trading permission or unattended deployment is authorised by this document.

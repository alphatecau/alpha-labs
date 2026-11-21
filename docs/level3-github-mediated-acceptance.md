# GitHub-mediated Level 3: Android staging acceptance

Status: **core create/update acceptance PASSED; security and operational acceptance PENDING**. No direct MCP write tool is enabled.

## Design and trust boundary

- The operator independently reviews the GitHub file at an immutable full 40-character commit SHA and verifies its SHA-256.
- An operator-run Termux CLI fetches the pinned file, checks its digest and allowlisted path, and requires an explicit confirmation.
- Creation is exclusive (no overwrite). Updating checks old and new SHA-256, refusing stale changes.
- Allowed: `docs/level3-staging/[A-Za-z0-9_-]+.md` and `tests/level3-staging/[A-Za-z0-9_-]+.txt`, max 32 KiB.
- **A commit SHA does not prove GitHub PR approval**. The installer does not query or cryptographically attest to PR approval. A compromised same-UID Android process can potentially tamper with files or approval prompts; no independent security boundary exists.
- The operator-run installer and updater now append fsynced success records to a local audit journal. This is not tamper-proof, and there is no transactional crash journal or automatic restoration. Read-only reconciliation and recovery reporting are available.
- No arbitrary shell commands, trading operations, credentials, or production writes are provided.

## Verified on Android (operator-provided Termux output, 2026-11-21)

- Downloaded both installers and both test modules from pinned commit `d3dd284287748b420c25477df25f2e97e1b3414a`.
- `python -m unittest discover -s tests -p 'test_level3_github_pinned_*.py' -v` reported **14 tests passed** in 0.136 seconds.
- Created `docs/level3-staging/github_acceptance.md` from pinned commit `bab50e39520231047e133e4a1240a5538d1bf7e4`, after explicit `INSTALL`. Reported SHA-256 `90411fd66d43e62b6348676094b2173c89ae055778c18b4235d79c37a45b61ed`; result `status: created`.
- Updated the same staging file from pinned commit `5a77f94c244cd336807811bfd0d88834ebb9dbef`, after explicit `UPDATE`. New reported SHA-256 `7fbe05567fcc7266ed24061e0c5fa13a296210cbcdd7f5ab96266e5902b9e7b7`; result `status: updated`.
- Repeated the identical update: **`DENIED: existing file changed: update refused`**. This confirms optimistic-concurrency replay rejection, not a cryptographic nonce-replay guarantee.
- Existing Level 2 adapter had previously been verified listening on `127.0.0.1:8765`; no restart or configuration changes requested during this sequence.

## Remaining before operational acceptance

1. Transactional crash recovery, including detection of operations interrupted before audit append.
2. Documented backup and rollback with independent content-hash verification; read-only recovery reports are implemented.
3. Independent GitHub review/approval verification (or explicitly maintain the operator-trusted manual mode).
4. Independent authorisation and key custody before direct MCP write exposure.
5. Re-run regression and end-to-end acceptance after security changes.

## Real Android audit acceptance (operator output, 2026-11-21)

- Pinned fixture commit `bee29f8d2857a264824d24b6bc10ad61b7ade5e3` created `docs/level3-staging/audit_acceptance.md` after explicit `INSTALL`.
- SHA-256 `708cc91e9b1a5c00b4180e1bcdb2a8fea629046cb78ecd766531ca623fbf787f` verified by installer.
- Audit JSONL last entry displayed matching commit, path, SHA-256, `operation: created`, `outcome: completed`, timestamp `1795251199`.
- This verifies a successful audit entry, **not** crash consistency, tamper resistance, complete historical reconciliation or independent approval custody.

## Android reconciliation acceptance (operator output, 2026-11-21)

- Fetched `github_staging_reconcile.py` and its tests from commit `012b22dc946f8f1d75c2ea03e0c82509c280c1c7`.
- `python -m unittest discover -s tests -p 'test_level3_github_*.py' -q`: **20 tests passed** in 0.104 seconds.
- Read-only reconciliation returned `entries: 1`, audited path `docs/level3-staging/audit_acceptance.md`, `status: match`, expected SHA-256 `708cc91e9b1a5c00b4180e1bcdb2a8fea629046cb78ecd766531ca623fbf787f`, `ok: true`.
- These results do not verify independent approval custody, tamper resistance, automatic crash recovery or direct MCP write exposure.

## Repository CI after recovery-report implementation

Commit `d8b87f6b1cbacfe06f6cf6b2fecf67c1c6950cc2`: seven checks completed successfully (Ruff, CodeQL, Gitleaks, Level 3 staging prototype checks, backend CI, Sites tests and offline research tests). These are repository checks, not a substitute for device acceptance.

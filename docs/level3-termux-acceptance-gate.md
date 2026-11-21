# Termux Level 3 staging acceptance gate

Status: **NO-GO for device activation**. This is a development checklist, not evidence of deployment.

## Observed Android controller (operator-provided read-only output, 2026-11-21)

- Existing `level2_mcp.py` advertises `workspace_write` and `workspace_update` in source, but the connected ChatGPT MCP interface currently exposes only `workspace_status`, `workspace_diff`, and `workspace_read`.
- `controller/controller.py:86-123` implements a write lock, SHA-256 compare, atomic replacement, and append-only audit attempt. **There is no per-operation approval verification in `write()`.**
- Policy requires `level == 2`, `remote_access == false`, `trading_enabled == false`, and `status == workspace_prepared_permissions_not_activated`.
- The launcher executes `level2_mcp.py`; existing tunnel and read-only service must not be restarted or replaced during preparation.
- The local workspace has five untracked diagnostic files. Preserve them.
- The local Git checkout has no remote configured. Do not rely on `git pull` in the Android workspace.

## Prototype security limitations

- `termux_local_approval.py` stores request contents and approval status in a directory accessible to the same Android UID as the worker. The worker can potentially alter approval records: **typing APPROVE is a workflow safeguard, not independent authorisation**.
- The prototype only supports create-only operations in `docs/level3-staging/*.md` and `tests/level3-staging/*.txt`; it does not provide approved editing.
- State and target writes are not a single transaction; interruption after creating the target but before marking the request complete requires manual reconciliation.
- Request expiry, revocation, immutable audit, and independent approval custody are not implemented.

## Mandatory acceptance before exposing write tools

1. Keep the original Level 2 service and tunnel unchanged; verify all three existing read tools still work.
2. Keep Level 3 staging paths separate from the existing working checkout, or demonstrate equivalent filesystem containment.
3. Do not advertise existing `workspace_write` or `workspace_update` until they enforce per-operation authorisation at execution time.
4. Require an approval record bound to operation, path, content digest, expiry and unique nonce; verify it with an independently held signing key or another demonstrably separate security principal.
5. Reject unapproved, expired, replayed, modified, symlink, hardlink, traversal, oversized, sensitive-path and concurrent modification requests.
6. Keep the signing secret and replay ledger outside the worker-accessible workspace, with actual operating-system isolation (proot under the same UID is insufficient).
7. Test deny paths first, then a single harmless approved staging file creation, verify exact contents and audit receipt, and test replay rejection.
8. Verify all exposed MCP tools with the actual connected client; local source code and GitHub CI alone do not establish activation.
9. No arbitrary shell, production changes, live trading, credentials, paid services or unrestricted filesystem access.
10. Preserve rollback: no automatic restart, no overwrite of existing launcher or policy, and no merge/deploy without passing acceptance.

## Deployment decision

Do not activate this same-UID approval prototype as a security boundary. It may be exercised in an isolated local test directory with synthetic data, but staging write exposure requires a stronger execution-time approval mechanism. See the existing signed-create implementation in `tools/level3_staging/signed_create.py` for a candidate; validate its key custody and Android compatibility before using it.

References: MCP tools specification and OWASP MCP Security Cheat Sheet (least privilege, human confirmation, validation, auditing).

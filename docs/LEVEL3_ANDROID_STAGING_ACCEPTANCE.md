# Level 3 Android staging acceptance — NOT YET AUTHORISED TO DEPLOY

## Preflight (read-only)
- Confirm existing Level 2 `workspace_status` from ChatGPT and local /healthz and /readyz.
- Record running gateway PID and tunnel profile; do not stop, restart, reconfigure or share its credentials.
- Verify adequate battery/storage and inspect `git status` on all existing worktrees.
- Create a **new, dedicated** staging checkout. Never reset, clean or overwrite the existing research checkout.

## Mandatory isolation
- Distinct process/UID, writable staging directory, connector identity, tunnel and credentials.
- Approval-signing private key **never** resides in the MCP worker environment, storage or accessible mount.
- SQLite ledger and audit location protected from MCP worker modification outside its narrowly defined transactional API. Merely placing them outside the checkout is **not sufficient** when the same UID can modify them.
- No shell tool, Git push, production checkout access, live trading, credential writes or wildcard path access.
- TLS/authentication and origin checks for any network transport. No public unauthenticated endpoint.
- Separate local operator approval action with visible exact file content and SHA-256, short expiry and one-time nonce.

## Acceptance tests
1. CI green on the exact deployed commit, plus independent code/security review.
2. Positive test: authorised staging Markdown file created, exact SHA-256, 0600 permissions and durable audit evidence.
3. Negative tests: unauthorised request, stale signature, tampered content/path, replay, symlink, existing file, overlimit and concurrent request.
4. Kill/restart between claim and file creation and between file fsync and ledger completion; assert no approval replay and documented manual reconciliation.
5. Verify the worker cannot read approval-signing private key or write outside allowlisted staging paths.
6. Verify Level 2 connector remains read-only and independently reachable from ChatGPT after Level 3 registration.
7. Revoke the Level 3 connector and verify Level 2 continues operating.

## Current blockers
- The GitHub MCP proposal server does **not** expose a write tool.
- Signed create primitive has not been integrated into an MCP write handler.
- Signed create's SQLite ledger is not yet independently protected from a compromised worker; audit is not tamper-evident.
- Crash interruption, concurrent operation and actual Android staging tests are not complete.

**Do not deploy the current prototype as a writable MCP service.** No merge to main or service activation until these gates pass.

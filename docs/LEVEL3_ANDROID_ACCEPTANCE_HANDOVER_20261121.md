# Android Level 3 MCP acceptance handover — 2026-11-21

## Verified on the connected Android Level 2 MCP
- Tunnel `alpha-labs-android-level2` connects and `workspace_status` succeeds.
- `workspace_read("README.md")` succeeds after correcting Ubuntu policy and workspace path mappings.
- Android workspace: `/data/data/com.termux/files/home/termux-level2-agent/workspaces/alpha-labs`.
- Existing Ubuntu alias: `/root/termux-level2-agent/workspaces -> /mnt/alpha-mcp/workspaces`; the operator restored the missing `/mnt/alpha-mcp/workspaces` mapping.
- Workspace branch reported: `agent/level2-local-20261116`; five untracked diagnostic/acceptance files are present. Preserve them.
- Available remote tools: `workspace_status`, `workspace_diff`, `workspace_read` only. No remote Android write/command tool has been verified.

## Level 3 source and hold
On main, `tools/level3_staging/mcp_broker_stdio.py` checks a broker socket with a different UID and signed readiness; `broker_stdio_launcher.py` requires broker environment and independently provisioned worker UID. The worker is not a generic file editor: use only broker-authorised create-only operations.

Per `docs/LEVEL3_SECURITY_BOUNDARY.md` and `docs/LEVEL3_BROKER_RC.md`, production is NO-GO until:
1. Separate worker, broker, and signer identities (Termux sessions sharing one app UID do not qualify).
2. Independent custody of private approval signing key, nonce ledger, and tamper-evident off-worker audit anchor.
3. Signed readiness based on independently measured conditions.
4. Verified peer UID and socket permissions, staging root confinement, denial/replay/tamper/crash/restart/concurrency tests.
5. Android acceptance and separately authenticated Level 3 connector; keep Level 2 unchanged.

## Implementation order
1. Select an independent broker hosting identity and separate signer custody; do not use an additional Termux session as a security boundary.
2. Implement off-worker audit anchoring and anti-rollback reconciliation; fail closed on outage or mismatch.
3. Integrate broker-backed readiness checks and external signer approval workflow.
4. Add CI integration tests covering identity separation (where supported), replay, denied path, digest mismatch, concurrent nonces, tamper, crash recovery and audit anchor failure.
5. Provision a dedicated isolated staging checkout and broker identity, then run Android device tests.
6. Register a separate Level 3 MCP connector only after all gates pass.

## Operator safety
- Do not paste API keys or signing private keys into ChatGPT or GitHub.
- Do not expose Unix broker socket on public TCP.
- Do not grant unrestricted shell, overwrite, Git push/merge, or trading execution.
- Do not merge or deploy merely because Level 2 reads pass.

This handover is documentation of observed status, not a claim of Level 3 activation.

# Level 3 MCP security boundary and rollout decision

Status: **proposal-only dispatcher implemented; not deployed; direct write NO-GO**.

## Capabilities

- The new `proposal_only_mcp.py` exposes only `level3_propose_create`. It queues a pending request under the existing restricted staging root; it does not create the target file.
- The older `termux_local_mcp.py` includes `level3_apply_approved_create` and MUST NOT be exposed through the ChatGPT tunnel.
- The operator-run GitHub-pinned installer/updater is the verified manual write path. Its local prompt is a usability control, not an independent security boundary.
- Level 2 adapter and tunnel remain untouched.

## Required security boundary before direct apply

The MCP-facing process and its credentials must not be able to approve or forge an approval, change the approved payload, or modify approval state. On Android Termux the observed same-UID process model does **not** provide that boundary. Permissions 0700/0600 do not isolate processes sharing that UID. The proposal queue must therefore be considered untrusted input.

An acceptable direct-write design requires all of:

1. An independently controlled approval authority (separate principal or off-device service) with secure identity and operator authentication.
2. An approval binding a canonical operation, allowlisted path, SHA-256 payload digest, unique nonce, short expiry and environment, with cryptographic verification by the applying service.
3. Single-use replay prevention stored durably, fail-closed on ambiguity or crash.
4. A writer restricted to the staging root, refusing symlinks and traversal, with no arbitrary shell, secrets, trading or production write methods.
5. Independently protected logs and explicit reconciliation of interrupted operations.
6. Threat-model review and adversarial tests before any tunnel exposure; manual Android end-to-end acceptance after isolated staging deployment.

A GitHub PR approval or commit pin alone does not satisfy the above authorisation boundary. Until independent custody is demonstrated, continue manual GitHub-mediated operator installation and expose at most the proposal-only tool in an isolated test service.

## Verification

New dispatcher tests check that only proposal is listed, a proposal does not create a target, apply and unknown methods are denied, path escape is refused, and unexpected arguments are refused. CI and physical Android testing must be reported separately; tests do not prove host isolation.

## Android proposal-only dispatcher acceptance (operator output, 2026-11-21)

- Downloaded `proposal_only_mcp.py` and `test_level3_proposal_only_mcp.py` from commit `fb0ddc48d172e56f97d36baa0d248e396c02dfb9`.
- Ran `python -m unittest discover -s tests -p 'test_level3_proposal_only_mcp.py' -v`: **6 tests passed in 0.025 seconds**.
- Confirmed proposal-only listing, no target creation, apply refusal, unknown-method refusal, traversal denial and unexpected-argument denial.
- This does not establish independent approval custody or live MCP tunnel connectivity.

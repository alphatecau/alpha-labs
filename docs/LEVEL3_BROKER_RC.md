# Level 3 broker-backed release candidate — deployment hold

## Architecture
- `mcp_broker_stdio.py`: unprivileged worker. Has only Unix socket path and MCP JSON-RPC tools. It does not open the ledger, audit file or private signer key.
- `broker_stdio_launcher.py`: broker running as a **different Linux/Android UID**, authenticated by Linux `SO_PEERCRED`. It owns the nonce SQLite ledger and hash-chain journal and applies signed create-only operations.
- `operator_approval.py`: offline approval signer must be held by a **third security identity** or separately protected external service. Neither broker nor worker should have the private signing key.
- Broker is **Unix-socket only**; never expose it on public TCP. `LEVEL3_WORKER_UID` must be the actual worker UID. Socket directory access must be configured explicitly by the system operator.

## Broker environment (names only; no credentials in repository)
`LEVEL3_BROKER_SOCKET`, `LEVEL3_STAGING_ROOT`, `LEVEL3_LEDGER_PATH`, `LEVEL3_AUDIT_PATH`, `LEVEL3_APPROVER_PUBLIC_KEY_B64`, `LEVEL3_WORKER_UID`.

The worker requires only `LEVEL3_BROKER_SOCKET`.

## Current limitations and security hold
1. This is a development candidate, **not deployed or operational**. GitHub CI uses one UID and cannot demonstrate Android UID separation.
2. The broker currently verifies audit chain/outbox consistency but does not implement an **independent off-device audit anchor**. An attacker with broker UID can rewrite both. This is a mandatory production gate.
3. The broker currently accepts approvals signed externally, but key custody and operator approval must be established outside the worker and broker. No production signer exists.
4. The signed readiness attestation is not yet enforced by the new broker-backed stdio entrypoint. This is a mandatory production gate.
5. The broker writes into an isolated staging checkout. The checkout and allowed directories must be provisioned so the broker can create files without granting access to other repositories.
6. Unix socket group permissions, peer UID, broker restart, audit durability and external connector authentication require actual deployment acceptance.
7. The old `mcp_signed_stdio.py` direct-ledger entrypoint remains offline-test-only and denies ordinary startup.

## Acceptance before connector activation
- CI all required workflows PASS.
- Isolated Linux users and permissions verified using real process UIDs.
- Full signed-create, replay, tamper, crash/restart and concurrent requests verified across the socket.
- Independent audit anchoring and rollback resistance verified.
- Separate signer private key inaccessible to worker and broker.
- Broker-backed startup readiness and evidence verification enforced.
- Separate authenticated ChatGPT connector configured and tested without touching Level 2.
- **No live trading, arbitrary file edits, shell, push or merge tools.**

**NO-GO** until all items pass.

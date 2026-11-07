# v0.12 security findings and threat model

**No public deployment, production secrets, broker permissions or capital access.** Security review scope is the implemented local foundation, not the complete commercial specification.

| Threat | Implemented control / test | Residual gap and launch gate |
| --- | --- | --- |
| Forged identity / cross-tenant access | Opaque token lookup, expiry/revocation, operator/viewer checks, tenant predicates on every account/order/position/event query; negative HTTP and direct-service tests | Production OIDC identity, secure registration, MFA, passkeys and recovery absent; independent security review required |
| Browser cross-origin/DNS rebinding | IPv4-loopback binding, exact Host/Origin, cross-site/identity-header rejection, CSP, no-store and no-referrer | Local HTTP is intentional development-only; public TLS, proxy trust, CSRF/session design require separate deployment |
| Repeated/malformed/large requests | Body limit, duplicate-key/nonfinite rejection, rate limits, socket timeout, exact route/schema fields | Rate state is per-process; distributed quota, DoS capacity and load beyond local fixture test unverified |
| Duplicate/replayed orders/fills | Durable unique request keys, conflict detection, partial-fill IDs, terminal-state checks and transactions | Bearer tokens are reusable while valid; no signed service-to-service anti-replay protocol is implemented |
| Agent/prompt privilege escalation | Data-only bounded assessment contract; no broker, DB, shell, deployment or policy handles; approval/tool fields rejected; no model connection | Same-process trusted code is not a hostile plugin sandbox; isolate any future model tool gateway and separately test provider attacks |
| Stale/future/reordered quotes | Event/receipt/transport bounds, microsecond causality, immutable revalidation, identity/quote-currency binding | No authenticated exchange source, stream sequence/gap repair, corporate-action coverage or licensing certification |
| Risk bypass / outage | Trusted authoriser recomputes limits inside fill transaction; no approval field accepted; non-simulation modes and every real broker adapter blocked | Not an independently deployed risk service; a process/DB administrator can tamper; service identity, signed grants and external policy owner required |
| Ledger corruption / restart | Atomic cash/inventory/order/audit writes, event-based independent reconciliation, backup/restore, persistent HALT, pending-order cancellation | Local hash chain is not an external witness; privileged rewrite/truncation can escape detection without trusted pinned heads |
| Credential theft | No broker credential accepted or stored. Local tokens hashed in server memory; browser holds tokens only in memory; private runtime token file and DB permissions | The runtime file contains local development tokens. It is not a production secrets manager. Broker connection requires managed secret storage, encryption, scoped read/trade permissions and revocation tests; withdrawals always excluded |
| Unsafe frontend content | Dynamic content rendered with textContent; no third-party scripts, unsafe HTML injection or external fonts | Physical Android/iOS, accessibility audit and hostile browser-extension/OS scenarios unverified |
| Supply-chain compromise | No third-party Python runtime dependencies introduced; CI contents permission read-only; browser-test package pinned | External dependency vulnerability/secret scanner and independent penetration test must be recorded before beta; existing disabled security workflow is not a passed scan |

## Confirmed limitations

- No customer accounts, subscription charging, exchange/broker login, production permissions, managed encryption or legal approval.
- Simulation only supports one synthetic spot instrument, long inventory and marketable limits. Displayed depth is not depleted across independent sessions; no order-book/fill reliability claim.
- Regional live eligibility is universally disabled. Broader regulatory/product restrictions are a design gate, not an implemented global compliance engine.
- Correlation, corporate actions, observed execution latency/slippage, stochastic depth and multi-currency accounting are not implemented in this slice.
- The simulation service can reject all proposals. It cannot prove real strategy evidence; unknown strategies remain UNVERIFIED and the known historical failures remain REJECTED.

## Incident procedure

1. Press HALT or use the authenticated control endpoint. Verify the persisted account flag and cancelled pending orders.
2. Stop the local process on evidence/account inconsistency. Preserve the DB/WAL and private runtime directory; do not publish tokens or personal journal data.
3. Reconcile from journal in a trusted copy, verify audit heads and restore a known backup into a new path. A restore does not itself authorise resume.
4. Revoke local tokens (sign-out or process restart). No broker credentials exist in this release. Future provider incidents require the provider's independently verified revocation procedure.
5. Record exact commit, account scope, timestamps, failure, corrective change and new negative tests. Recovery keeps entries suspended and requires separate operator review.

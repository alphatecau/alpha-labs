# Protected owner paper staging acceptance

Private staging and hosted owner paper remain NO-GO. The existing Render service is a health probe. Use the external authenticated BFF for the owner desk. Its server-side boundary does not depend on the public research Site.

## Composition

| Component | Existing entry point | Required binding |
|---|---|---|
| Auth0 and read-only research BFF | deployment.authenticated_staging_bootstrap.build_authenticated_application | Pinned HTTPS issuer, client audience, exact callback, private client configuration, PostgreSQL PKCE/session/ownership/quota roles, account-role research reader |
| Simulated trading | LivePaperSession and PaperMarketFeed | Single writer, persistent private SQLite journal, Coinbase Exchange public books, immutable USD market and cost configuration |
| Protected state | PostgresPaperCheckpoints and checkpoint_schema | Separate PostgreSQL authority, owner-pinned table, LOGIN NOINHERIT role with SELECT and INSERT, independently stored checkpoint key |
| HTTPS ingress | deployment.owner_paper_bff.create_owner_paper_application | Verified proxy socket peers, canonical origin, separate CSRF key, single worker. Strip incoming forwarding headers and set the trusted scheme at the ingress. |
| Browser | /auth/login and /owner-paper/ | Current authorised owner session. Keep the existing public Site as a research surface. |

Supply connections with bounded connect time, verified TLS and separate permissions. Stop the feed before closing the journal. Auth0 callback tests must confirm the hosted issuer and audience, PKCE, callback and nonce, cookie attributes, successful owner sign-in, second-account denial, expiry and revocation. Verify the actual reverse proxy against direct requests and forged headers. Apply ingress abuse controls to sign-in before exposing the service. The PostgreSQL store caps active PKCE challenges and reclaims expired records.

## Provisioning and recovery

1. A designated operator installs the checkpoint schema with an owner separate from the application login. Grant the application only SELECT and INSERT on the checkpoint table. Put the signing key under separate custody from both stores and the CSRF key.
2. Provision exactly once with an empty authority and fresh journal using LivePaperSession with provision=True. Normal application startup uses the default provision=False. Retain old v1 fills and checkpoint history for reconciliation. v1 authenticated fills only, so an operator must verify any prior risk and control state independently before carrying it forward. Keep a new protected journal halted until review.
3. For a matched backup, halt and quiesce the writer. Confirm the journal and authority agree. Take the SQLite backup through the SQLite backup API and dump the protected PostgreSQL table as a custom-format archive. Record the latest authenticated owner, sequence, digest, exact source SHA and key reference in an independently retained append-only receipt. Preserve backup permissions and retention independently of the writer.
4. Restore into separate isolated storage and an empty PostgreSQL database. Restore the owner and least-privilege grants, run SQLite quick_check, and verify the exact latest receipt against both stores before starting. Start halted. Compare cash, positions, costs, latest order IDs, risk state and journal sequence against the backup record. Retry a known simulated order ID and confirm one recorded outcome.
5. On an uncertain commit, quarantine both copies. An exact authenticated match can recover halted after restart. A missing or mismatched checkpoint produces CHECKPOINT_HALT and must be reconciled against independent evidence. Recover or preserve the verified pair before accepting any new order. A coordinated rollback to an older authentic pair requires the independent current receipt to detect it.
6. Retain fill, order, guard and checkpoint evidence according to the operator's approved retention policy. The owner API returns a bounded checkpoint window. Preserve the complete PostgreSQL append-only history in recovery archives.

The disposable recovery exercise performs a real pg_dump and pg_restore, attempts to restore stale authority beside current SQLite, and stops PostgreSQL mid-write. Reproduce with Python 3.12, psycopg and PostgreSQL binaries on a host that permits loopback networking.

~~~sh
PYTHONPATH=packages/alpha_lab/src:.:tests/unit python tests/acceptance/protected_paper_recovery.py --postgres-bin /path/to/postgresql/bin
~~~

## Manual Android acceptance

Use a separately authorised staging HTTPS URL and the owner's Android Chrome. Record device and browser versions, UTC time, SHA and results. Use the isolated simulated account and save only redacted screenshots.

1. Open /api/v1/paper/state in an incognito tab. Expect HTTP 401. Use a second valid test identity to confirm HTTP 403 on both the desk and API.
2. Open /auth/login and sign in as the test owner. Expect return to /owner-paper/. Reload and rotate the screen. Confirm readable status, touch targets, scrolling within the orders and fills tables, and the correct signed-in account. Capture the initial HALT and verified checkpoint.
3. Check source timestamps and fresh status for BTC, ETH and SOL. Arm and enter a low-risk simulated market buy with a protective stop. Verify the stable order ID, one fill, fee, cash, position and cost basis.
4. Enter a simulated limit order away from the current book. Verify pending status. Cancel it and refresh. Verify cancellation persists and the original order has no additional fills. Use the deterministic fixture for partial-fill and full-fill cases.
5. Interrupt connectivity immediately after submitting a simulated order, reconnect and retry the same ID. Check the ledger for one outcome. Exercise stale quotes or provider outage and confirm the server refuses execution and the controls disable.
6. Tap Emergency HALT, reload and verify HALT. Restart the approved fixture service and verify no automatic arming. Verify checkpoint history and reconciliation. Sign out and confirm the old tab and saved API URL deny access. Repeat after natural session expiry and explicit revocation.
7. Verify that held positions, cancellation, shared quota, current identity and the independent backup receipt all agree with the staging evidence. Record any failure against the matrix before release review.

On a workstation with Chromium and Playwright, the loopback touch-viewport harness uses disposable PostgreSQL, a synthetic browser session and test TLS. Hosted Auth0 and the physical device require the steps above.

~~~sh
PYTHONPATH=packages/alpha_lab/src:.:tests/unit python tests/acceptance/owner_paper_browser.py --postgres-bin /path/to/postgresql/bin --chromium /path/to/chromium
~~~

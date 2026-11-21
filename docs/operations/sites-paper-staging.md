# Alpha Labs Site paper staging

The paper console reads stopped BTC, ETH and SOL journals and current public Coinbase books. Hosted routes only read. Order entry and the operational HALT switch belong to the existing local simulator. A stored guard describes the instant of capture. Current public quotes never revalue the archived portfolio.

## Identity and network

The Site Worker forwards only its host-scoped HttpOnly state or session cookie to the fixed Alpha Labs Auth0 staging BFF. Site login starts at `/auth/login`. The BFF uses its existing registered Render callback, PKCE, its single-use PostgreSQL state, verified ID token, existing ownership mapping and opaque sessions. A Site-initiated callback redirects once to the fixed Site hostname. Only the original browser's state cookie can complete that exchange. The standalone Render research login keeps its own browser session. Site logout is a same-origin POST that revokes the Site session in PostgreSQL. An existing provider SSO session can allow a later sign-in.

The Worker reads `GET /api/v1/paper/snapshot`, `/api/v1/paper/markets` and `/api/v1/paper/research`. The release must pin the deployed Git SHA and reject a different revision. Session validity and current tenant ownership are checked on every read. A worker admits up to 30 paper reads per owner per fixed minute. Coinbase requests share each process's five-second poll cache and provider backoff. The read budget is per process.

## Provision a snapshot

1. Quit the local paper terminal. Use the existing [Android recovery procedure](android-paper-recovery.md) to compare the actual journal and its separately stored backup. For the historical phone journal use the two-fill minimum. Confirm the journal's local account belongs to the intended, already provisioned Auth0 owner. Preserve the originals and private audit receipt.
2. On the **same verified stopped copy**, record the full-file SHA-256, event count, event-chain head and UTC capture time. A protected journal requiring an external checkpoint authority must use that authority's verification workflow before it can be supported here.
3. In **alpha-labs-auth-staging**, provide that copy privately, either as `<file-sha256>.sqlite3` in a pre-existing read-only directory selected via `ALPHA_PAPER_JOURNAL_DIR`, or as a Render secret file named `<file-sha256>.b64` containing one unwrapped base64 line. The default directory is `/etc/secrets`. Render's secret-file size cap applies. The adapter also caps decoded snapshots at 8 MiB. Keep journals, credentials and real owner mappings out of Git and the Site.
4. Set the private Render environment variable `ALPHA_PAPER_JOURNALS_JSON` to a JSON object. Each key is the exact pre-provisioned Auth0 owner ID. Its value has `account` (exact SQLite guard), `sha256` (whole file), `sequence` (integer), `head` (event-chain digest) and `captured_at` (UTC timestamp). Sharing one file between tenants is refused. The mapping is an operator attestation for the original local account. A matching local account name alone does not identify a tenant.
5. Restart only the isolated staging revision after updating its private files or mapping. A missing or invalid binding leaves the journal unavailable. A cached verified immutable snapshot lasts until configuration reload. Rotate the file and mapping together. Retain the previous pin and snapshot for rollback.

## Acceptance and rollback

Check the staging health, signed-out API rejection, sign-in, denied second tenant, archived fill count and head, recorded HALT, pagination, and sign-out/revocation. Compare a restored copy with the same independently retained head, then repeat after an isolated restart. Check mobile layout at 320 and 390 CSS pixels. Capture HTTP statuses and commit IDs. Keep OAuth state, authorisation codes, cookies, private order IDs and tenant identifiers out of evidence logs.

AUD trading P&L uses FIFO with purchase and sale fees converted at the latest prior UTC calendar day's available RBA F11.1 USD-per-AUD rate. Rates more than seven days old, unavailable FX or missing fill timestamps leave AUD unavailable. Unrealised P&L uses the last recorded USD fill mark per instrument and snapshot FX. It excludes FX P&L on idle USD cash. Journal cash and equity are translated at snapshot FX. The response identifies the dates, rates and source digest. Legacy journals can have fills without resting-order records.

Save the Site revision without publishing until owner acceptance. To withdraw a candidate, restore the previous staged Render deploy and its matching private snapshot configuration. Site version 9 is the existing public rollback reference. Run the restored health, auth and denial checks. No production deployment is part of staging acceptance.

# Google Drive OAuth recovery — Android operator runbook

## Confirmed fault

The available Composio Google Drive connector is ACTIVE but Google Drive v3
`about.get` and `files.get` return HTTP 403
`ACCESS_TOKEN_SCOPE_INSUFFICIENT`. The Composio dashboard has displayed
multiple private connections; connector visibility does not map those names
to authenticated Google identities.

## Safe procedure

1. Preserve existing connections. Do not delete, share with team, or create more duplicates.
2. Identify the intended auditor account `alpha.tec.au869@gmail.com` through an
   authenticated Google identity response, not a connection nickname.
3. Inspect the provider OAuth configuration and requested Google Drive scopes.
   A reconnect using unchanged scopes cannot add permissions.
4. Use a private auditor-only OAuth configuration with the least permissions
   sufficient for the intended folder access and auditor-owned checkpoint writes.
5. Complete Google's consent flow in the browser; never send tokens to chat.
6. Re-test `about.get`, independent folder metadata and permissions, then
   a disposable upload/download/delete cycle under the verified account.
7. Record the exact account identity and returned scopes in protected
   operational evidence (not token values). If any step fails, stop.

## Separation of duties

The broker must not receive the auditor's OAuth credentials or private signing
key. Do not share the independent auditor folder with broker write permissions.
Google Drive is not intrinsically immutable; independently retained checkpoints
and complete audit-chain verification remain mandatory.

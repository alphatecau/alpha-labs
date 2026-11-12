# Operator handoff — free-only Auth0 and Render staging (2026-11-12)

Status: ACTION REQUIRED. No service/credential change has been made. The current Render alpha-labs web service is a health probe, not an authenticated BFF.

## Existing confirmed assets
- Render workspace: Shannon's workspace, `tea-dbloi19srm7s73f93bgg`
- Web service: `srv-dbop6f3bc2fs73cqfksg`, `https://alpha-labs-k869.onrender.com`, auto-deploy disabled; currently public ingress. DO NOT deploy owner paper routes to it.
- PostgreSQL 16 staging database: `dpg-dboq4j7f3r2c73bvlif0-a`, free, expires 2026-12-09. Not suitable for durable journal acceptance.
- Existing Auth0 domain from prior operator record: `alpha-labs-dev.au.auth0.com` (reconfirm in tenant dashboard; not live-verified).

## Operator actions in Auth0 dashboard
1. Open Auth0 Dashboard > Applications > Applications. Select the existing Alpha Labs staging **Regular Web Application** (or create a distinct staging Regular Web Application if it is shared with production).
2. Verify domain `alpha-labs-dev.au.auth0.com`; record the **Client ID** and application name. Client ID is not a secret. Never paste Client Secret or tokens into a chat, GitHub issue or commit.
3. Allowed Callback URLs: `https://alpha-labs-k869.onrender.com/auth/callback`
4. Allowed Logout URLs and Allowed Web Origins: `https://alpha-labs-k869.onrender.com`
5. Disable wildcard callback/origin entries for this staging app; save changes. This is a configuration check only: the current probe does not implement the callback.
6. Confirm a separate non-owner test user is available. Do not share passwords or personally identifying tokens.

## Free-tier limitation and decision
Do not deploy the paper order API on Render free web storage. Persistent journals and independently protected checkpoints cannot be claimed on ephemeral storage. The existing free PostgreSQL database expires on 2026-12-09; do not use it as the only source of durable paper account truth. Free-only scope is limited to disposable offline tests, CI, health probe and preparatory authentication configuration.

## Engineering release gates
1. Independently accept PR #103, #104 and #105; record exact-head CI and review.
2. Implement and test an explicit BFF composition with verified Auth0 confidential-client exchange, persistent PKCE/session stores, tenant-role credential broker, trusted proxy ingress and safe startup/shutdown.
3. Provision separately protected durable journal and checkpoint storage with tested backup/restore. If not possible on free tier, stop.
4. After private deployment, test login/logout/revocation, wrong owner, RLS, shared quota, risk HALT, stale feed, duplicate orders, restart recovery and Android physical browser.
5. Keep public trading and broker execution disabled.

## User response requested
Report only: (a) whether the Auth0 staging app is dedicated or shared, (b) whether the exact callback/origin settings are saved, and (c) the staging Client ID if comfortable (public identifier). Never provide Client Secret.

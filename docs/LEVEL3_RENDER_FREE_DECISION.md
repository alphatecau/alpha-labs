# Level 3 free Render deployment decision record

## Verified deployment
- Workspace: `tea-dbloi19srm7s73f93bgg`
- Dedicated service: `srv-dbus2ve1egvs73ehtp50`
- Service name: `alpha-labs-level3-broker-probe`
- URL: https://alpha-labs-level3-broker-probe.onrender.com
- Region: Singapore; plan: free; auto-deploy: disabled
- Initial commit: `97c4423d246e28e0159a0d567a767de77cc9e3f2`
- Render initial deployment `dep-dbus2vu1egvs73ehtq8g` reported **live**.
- Endpoint contract: GET /healthz = 200; GET /readyz = 503; POST = 405; no MCP tools.

## Hard separation and durability decisions
- The public Render service is a **read-only probe**. Do not change its start command to the local Unix-socket broker or publish the broker on a public TCP port.
- The free service filesystem must be treated as ephemeral; do not store the authoritative SQLite nonce ledger, signing keys or audit journal there. Verify any persistence claims against provider documentation before relying on them.
- Cloud-to-Android communication needs mutually authenticated encrypted transport and replay-safe requests; the current Unix-socket `SO_PEERCRED` design only works for processes on the **same Linux host** and cannot authenticate remote Android clients.
- The separate security boundary needs durable independent custody, an off-worker audit anchor, and authenticated remote transport. A separate Render free web process alone does not satisfy those requirements.
- Avoid any service that requires a paid persistent disk, paid database, or upgrade without explicit user approval. A$0 remains a constraint, not a guarantee that production security can be achieved for free.

## Deployment gate
NO-GO for signed writes or public MCP. Leave Level 2 untouched. The next engineering change should define and test the remote request protocol and durable audit backend **before** enabling any mutating cloud endpoint.

# Termux Level 2 → Level 3: verified handover (21 November 2026)

## Observations (Android screenshots and connected MCP)

- Android Termux Level 2 directory: `/data/data/com.termux/files/home/termux-level2-agent`.
- `policy.json` exists there; `level2_mcp.py` loads `BASE / "policy.json"`.
- `level2_mcp.py` and tunnel-client were running; `GET /readyz` returned `ready`.
- A second tunnel start failed to bind `127.0.0.1:8080` because the address was already in use. Do not start a second tunnel on the same port.
- Connected `workspace_status` succeeded. Connected `workspace_read` and `workspace_diff` failed with missing `/root/termux-level2-agent/policy.json`.
- The local script screenshot includes `workspace_write` and `workspace_update`, but these are **not exposed** by the connected read-only MCP connector. Do not infer write authority from their presence.
- A `/root/...` path can be valid *inside proot* even when Termux's host home differs. The root cause is not established until process mount mappings and controller configuration are inspected.

## Safe immediate diagnostic (read-only, existing Termux session)

```sh
printf '=== ENVIRONMENT ===\n'; printf 'HOME=%s\n' "$HOME"; printf '=== HOST FILES ===\n'; ls -l "$HOME/termux-level2-agent/policy.json" "$HOME/termux-level2-agent/level2_mcp.py"; printf '=== PROOT MAPPING ===\n'; ps -ef | grep -E '[p]root|[l]evel2_mcp|[t]unnel-client' | cut -c 1-180; printf '=== POLICY PATH REFERENCES ===\n'; grep -RIn --exclude='policy.json' --exclude-dir='.git' '/root/termux-level2-agent' "$HOME/termux-level2-agent" 2>/dev/null | head -20
```

Do not print credentials, tokens, or the full policy JSON. Do not modify `/root`, symlink private directories, kill processes, or change ports without establishing which process owns them.

## Level 3 release boundary

- Preserve Level 2 and the research workspace.
- Existing Level 3 broker code is a candidate only; see `docs/LEVEL3_SECURITY_BOUNDARY.md` and `docs/LEVEL3_BROKER_RC.md`.
- Require separate broker UID, external operator signing-key custody, durable nonce ledger, independent audit anchor, signed startup readiness, replay/crash/tamper tests, and Android acceptance.
- The free Render `alpha-labs-level3-broker-probe` is a read-only health probe, **not** a write-enabled broker.
- Until those gates pass: no arbitrary shell, unrestricted writes, Git push/merge, secrets, deployment, or trading operations.
- A successful local readiness response or Git status is not proof of Level 3 acceptance.

## Acceptance record template

Record date, Android environment, actual UID separation, connector tool inventory, isolated staging path, broker identity, approved-create receipt, denied path test, replay denial, restart recovery, audit-anchor verification, and independent reviewer approval. Never include secret material.

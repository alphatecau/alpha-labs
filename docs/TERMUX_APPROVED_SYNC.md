# Approved GitHub-to-Termux synchronisation

This is an **opt-in**, local, fail-closed mechanism. It does not run on a schedule or accept instructions over the read-only MCP tunnel. No live trading, execution or deployment permissions are added.

## Preconditions

- Install `git` and Python 3.9+ in Termux.
- Use a dedicated, clean checkout of `alphatecau/alpha-labs`. The existing Level 2 workspace currently contains untracked evidence files, so it will **not** pass the clean-tree check. Do not delete those files to make a sync succeed.
- Keep a separate backup of local research data and ignored files. Git rollback does not restore ignored or external data.
- Review the selected commit in GitHub before approving it.

## Usage (from the repository root)

```sh
python tools/termux_approved_sync.py plan --commit FULL_40_CHARACTER_SHA
python tools/termux_approved_sync.py apply --commit FULL_40_CHARACTER_SHA --approve
python tools/termux_approved_sync.py rollback --approve
```

The selected commit must be an ancestor of the fetched `origin/main` and a fast-forward from local `HEAD`. The script verifies the remote URL, rejects dirty or untracked files, and refuses ambiguous refs or non-fast-forward changes. It creates a dated local backup branch and records before/after SHAs inside the Git directory. Rollback is permitted only when the worktree remains clean and HEAD still matches the recorded post-sync commit. Rollback uses `git reset --keep`, not `--hard`.

**Scope:** Synchronises Git-tracked source only. It does not install dependencies, restart services, modify secrets, run tests, merge pull requests or deploy anything. Existing MCP remains read-only.

**Known operational caveats:** A power loss between fast-forward and recording state can leave a backup branch without a state record. In that case stop and inspect `git reflog` and the backup branch before any manual recovery. A new sync is refused while a previous rollback record exists. Never use this tool on a checkout with valuable uncommitted data.

## Interrupted-sync recovery (new)

The sync now records a durable `pending` intent **before** the fast-forward and atomically marks it `applied` afterwards. An interruption therefore leaves an inspectable recovery record.

```sh
python tools/termux_approved_sync.py recover
python tools/termux_approved_sync.py recover --approve
```

The first command is read-only. With explicit approval, recovery clears a pending record if HEAD remains at the prior commit, or finalises it if HEAD is at the selected target. Any other HEAD fails closed. Backup branches are retained. Do not manually delete state records; investigate unexpected states first. An interruption before the pending record is written can leave a backup branch but no record; inspect the reflog manually.

## Controlled MCP restart acceptance

The MCP is deliberately read-only and cannot restart itself. Run `tools/termux_mcp_reconnect_check.py` locally in Termux before and after a manually controlled tunnel restart. The script probes loopback health and readiness only, never prints credentials or starts/stops processes. Reconnection must also be independently confirmed with `workspace_status` in ChatGPT. Never restart the only active tunnel without ensuring the Android device remains accessible.

# Level 3 controlled GitHub sync — experimental, not deployed

## Security contract
- **No remote shell**: the proposed MCP exposes only `sync_plan`, `sync_apply`, and `sync_recover_status`; never expose the local `authorise` subcommand as an MCP tool.
- One explicitly configured checkout of `alphatecau/alpha-labs` only. Q3HASH and other repositories are **not** authorised by this implementation.
- Only an operator on the Android device may run `authorise`. Approval is tied to the exact checkout, full commit SHA, and ten-minute expiry; the approval file is mode 0600, consumed before attempting an update.
- Existing approved sync enforces clean tree, exact remote, fast-forward, pending recovery record, backup branch and fail-closed rollback.
- Do not point this adapter at the dirty Level 2 MCP workspace. Use a dedicated clean checkout. Do not replace the running read-only MCP until independently tested.
- No broker integration, trading activation, deployment, package installation, or general command execution.

## Proposed MCP integration (requires operator installation)
The Android MCP server must **explicitly register** three bounded wrappers around `tools/termux_level3_sync.py`:
- `sync_plan(commit_sha)` -> invoke `plan --commit SHA`.
- `sync_apply(commit_sha)` -> invoke `apply --commit SHA`, **only after local operator authorisation**.
- `sync_recover_status()` -> invoke `recover-status` (read-only).

The adapter's CLI also supports `authorise --commit SHA` **for direct local Termux use only**. Never register it as a remote MCP method. No general subprocess interface or configurable command/checkout path should be accepted from remote requests. The config and private state directory paths must be hard-coded in the server's deployment configuration, not accepted as remote tool arguments.

## Operator installation prerequisites
1. Review and merge the research PR only after offline tests, independent security review and Android disposable-checkout acceptance.
2. Ensure `~/alpha-sync-test` is a dedicated clean checkout and that the approved sync script exists there. Keep the existing MCP service untouched during evaluation.
3. Create a private state directory (mode 0700) and an absolute-path JSON configuration with exactly `{"repo":"alphatecau/alpha-labs","checkout":"/absolute/path/to/alpha-sync-test"}`. Do not put credentials in this file.
4. Locally run `python tools/termux_level3_sync.py --config CONFIG --state-dir STATE plan --commit SHA`; review output.
5. To permit **one** remote update, run the same CLI with `authorise --commit SHA` locally. The ten-minute grant is consumed by the next matching `sync_apply` request, even if the underlying update fails.
6. Perform a disposable checkout test, interruption recovery test, read-only MCP regression test, then controlled tunnel restart. Preserve the original tunnel as a fallback until verified.

## Limitations
This branch supplies a proposed adapter and tests; it does **not** patch the existing private Android MCP server or activate new remote tools. A local operator must install and register the tools and restart the tunnel. Independent review is still required before exposing write capability.

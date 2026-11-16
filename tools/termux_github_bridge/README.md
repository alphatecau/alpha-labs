# Termux GitHub Bridge — experimental manual queue

This is **not** a direct ChatGPT MCP connection. The phone polls GitHub outbound via an existing authenticated `gh` session. No SSH port, tunnel, persistent service, trading or arbitrary shell execution.

Only GitHub issues **authored by alphatecau** and bearing the privileged label `termux-bridge-approved` qualify. Issue body must be exactly:

```json
{"schema":1,"tool":"repo_status","repo":"alpha-labs"}
```

Permitted tools: `repo_status`, `repo_log`. Permitted repositories: `Q3HASH`, `alpha-labs`. The existing MCP bridge independently enforces its allowlist.

## Termux setup

Ensure `gh auth status` succeeds and `$HOME/termux-mcp-bridge/bridge.py` exists. Fetch these three files from the PR to `$HOME/termux-github-bridge`, then:

```sh
cd "$HOME/termux-github-bridge"
python -m unittest -v test_worker.py
python worker.py
python worker.py --execute
```

Without `--execute`, the worker only validates and prints task metadata. With `--execute`, it runs the approved local MCP tool and **prints results locally only**. It never publishes Git metadata or private information to GitHub and never closes issues. Review output before any manual sharing.

## Security and limitations

This is intentionally **manual polling**, not autonomous remote command execution. GitHub issue labels are not cryptographic authorisation; restrict label permissions and GitHub tokens. Do not add secrets or sensitive data to issue bodies. Do not run unreviewed repository tests through this queue. The bridge must not be run as a background daemon until a separate security review and authenticated response mechanism are implemented.

Acceptance: six unit tests, a locally authenticated `gh` session, and an owner-created labelled test issue. Neither remote ChatGPT connectivity nor Android acceptance is established by CI.

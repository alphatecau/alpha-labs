# Level 3 local MCP stdio adapter — staging only

This adapter exposes **only** `level3_propose_create` over newline-delimited JSON-RPC 2.0 on stdin/stdout. It does not expose apply/approve, arbitrary file editing, command execution, package installation, trading, or a network listener.

## Android Termux acceptance

From a trusted, existing checkout of `alphatecau/alpha-labs` at the reviewed PR commit, run the following read-only validation before considering any connector configuration:

```sh
python -m unittest discover -s tests -p 'test_level3_stdio_mcp.py' -v && python -m unittest discover -s tests -p 'test_level3_proposal_only_mcp.py' -v && python -m unittest discover -s tests -p 'test_level3_staging_write.py' -v
```

To run locally **after** tests pass:

```sh
python -m tools.level3_staging.stdio_server "$PWD"
```

The adapter waits for MCP JSON-RPC requests on stdin and returns responses on stdout. Do not paste secrets into its inputs. A proposal is **not** an applied change. The separate local approval workflow remains required for any creation and is not exposed by this adapter.

## Security and release gates

- No remote MCP tunnel registration until Android protocol/denial tests and an independent security review pass.
- Keep Level 2 read-only tunnel unchanged. Do not connect this local same-UID prototype to an untrusted remote client.
- Verify the reviewer's expected Git SHA, proposal-only tool inventory, allowlisted paths, no writes on proposal, refusal of shell/apply/extra arguments, no secret leakage, and fail-closed oversized/malformed input.
- Same-UID processes on Termux can interfere with local state; this prototype does not provide independent approval isolation.
- Never enable live trading or production deployment from this adapter.

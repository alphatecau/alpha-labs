# MCP3 independent Secure MCP Tunnel — deployment decision

## Selected architecture

ChatGPT connector -> **new OpenAI-hosted tunnel ID** -> **separate tunnel-client process** -> local **stdio** `tools.level3_staging.stdio_server` -> proposal-only queue -> **human-approved local apply**.

Do not route MCP3 through the existing Level 2 tunnel ID or its `main` channel. The existing Level 2 profile and process must not be edited, restarted, or replaced. Do not start the optional HTTP loopback bridge for this deployment.

Official references:
- https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
- https://github.com/openai/tunnel-client/blob/master/docs/configuration.md
- https://github.com/openai/tunnel-client/blob/master/docs/connectors.md

## Required prerequisites

1. Obtain a **new** tunnel ID from OpenAI Platform tunnel settings. Do not reuse the Level 2 tunnel ID.
2. Use the existing supported tunnel-client executable inside its working Ubuntu PRoot environment; direct execution in native Termux fails with `unexpected e_type: 2`.
3. Verify that the PRoot environment can invoke the correct Python interpreter and access `~/termux-level3-source` (paths may differ inside PRoot).
4. Use a **new** profile file, with a distinct health listener such as `127.0.0.1:8084`. The Level 2 health listener remains `127.0.0.1:8080`.
5. Keep control-plane credentials as environment references; never copy literal keys into Git, screenshots, chat or a profile.
6. Bind the new profile's `main` channel to `python -m tools.level3_staging.stdio_server <verified-workspace-path>`, using a verified Python interpreter and working directory.
7. Check `tunnel-client doctor` and `readyz` in the PRoot environment, then register the new hosted endpoint as a separate private ChatGPT MCP connector.

## Acceptance gates

- Level 2 continues to respond on 8080 throughout and after the test.
- MCP3 has a distinct tunnel ID and distinct health listener.
- Remote `tools/list` returns only `level3_propose_create`.
- Remote proposal creates only a pending receipt; no target file is created.
- Local operator reviews exact path, content and SHA-256, types APPROVE, and locally applies once.
- Remote apply/shell/overwrite/traversal/oversized content fail closed.
- Invalid connector credentials cannot reach the MCP tool.
- Disconnect/restart does not permit duplicate application.
- Security review acknowledges that same-UID local approval storage is **not** an independent security boundary.

**Status:** architecture documented; new tunnel ID, runtime configuration, ChatGPT connector registration, and remote acceptance remain unverified. No production or trading permissions.

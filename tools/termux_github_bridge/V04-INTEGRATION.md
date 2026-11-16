# v0.4 signed worker integration — opt-in, unprovisioned

`worker_v4.py` is a **separate** worker. It does not modify or replace the running v0.3 supervisor or its `worker_v2.py` queue. It only polls issues labelled `termux-bridge-v4-signed` and requires a correctly signed envelope for the exact target device. Default mode validates but does not execute. `--execute` is available only for the same two read-only repository operations supported by v0.2.

The worker expects a 32-byte binary HMAC key at `~/.local/state/termux-github-bridge/v4-signing.key`, permission 0600. **Do not generate or provision this key yet**: an independent signer and secure delivery mechanism have not been implemented. Never commit or post the key to GitHub or send it in chat.

Security limitations: shared-secret HMAC does not establish independent signer identity if the same key is stored with the worker; this is a transitional protocol, not the final full-access trust model. A crash after nonce reservation can leave an issue open but intentionally prevents re-execution; manual reconciliation is required. Issue listing is limited to 30; backlog handling remains incomplete. Receipt publication is not transactional. No arbitrary shell, package installation, filesystem writes, boot persistence, or privileged commands.

Run CI: `cd tools/termux_github_bridge && python -m unittest -v test_signed_protocol_v4.py test_worker_v4.py test_agent_v3.py test_worker_v2.py`.

# v0.5 key enrolment and revocation

This component manages **public verification keys only**, not signer private keys. It is not automatically activated by merging. A human operator must independently authenticate the public-key fingerprint before enrolment. Do not accept a fingerprint solely from the same GitHub issue or message that supplied the public key.

Commands (run on the Android worker only after an independently verified fingerprint has been obtained):

```sh
python keyring_v5.py --keyring "$HOME/.local/state/termux-github-bridge/v5-keys.json" enrol --key-id operator-1 --public-key-base64 PUBLIC_KEY --expected-fingerprint VERIFIED_SHA256_FINGERPRINT
python keyring_v5.py --keyring "$HOME/.local/state/termux-github-bridge/v5-keys.json" revoke --key-id operator-1
```

Fingerprint algorithm: SHA-256 of the exact bytes `b"termux-v5-public-key\\x00" + raw_32_byte_public_key`. The operator must obtain this fingerprint over an independent trusted channel. Revocation removes the key from the on-device trust store; it does not revoke already-executed tasks. Key rotation is enrol-new, verify, revoke-old. The v0.5 polling worker, receipt recovery and Android acceptance are still pending. v0.3 stays active.

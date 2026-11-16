# v0.5 offline operator signer — security boundary

This is a **manual, offline signer**, not a hosted service or autonomous signing authority. It must run on a **different trusted host** from the Android Termux worker. The private key never enters GitHub, ChatGPT, an issue body, CI secrets, or the Android device. No signer keys are created by merging this PR.

On the trusted signing host, with Python and cryptography installed:

```sh
python offline_signer_v5.py init --private-key /secure/private/operator.key
python offline_signer_v5.py sign --private-key /secure/private/operator.key --key-id operator-1 --device android-dev-01 --operation repo_status --repo alpha-labs
```

The first command creates a private key with 0600 permissions and prints **only the public verification key**. The second prints a signed, 120-second, read-only task envelope. Public-key enrolment on Android is **not implemented** here: do not assume copying a public key into the device establishes a trusted identity without an independently authenticated fingerprint check.

The CLI uses no GitHub API or network calls. Do not use GitHub Actions as the signing host, and do not run this signer on the Termux worker. If no independent host is available, keep the v0.3 worker and defer activation. Next gates: authenticated public-key enrolment, revocation/rotation, a v0.5 worker integration, crash recovery, and Android acceptance.

"""Staging-only encrypted persistent Ed25519 signing identity.

Exportable software key, NOT a KMS/HSM replacement. Never put passwords or
key material in source control, logs, GitHub Actions or broker environments.
"""
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


class AuditorKeyDenied(ValueError):
    pass


def _derive(passphrase, salt):
    if not isinstance(passphrase, str) or len(passphrase) < 16:
        raise AuditorKeyDenied("auditor passphrase must have at least 16 characters")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(
        passphrase.encode("utf-8")
    )


class EncryptedAuditorSigner:
    def __init__(self, key):
        self._key = key

    @property
    def public_key(self):
        return self._key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )

    def sign(self, data):
        return self._key.sign(data)

    @classmethod
    def create(cls, path, passphrase):
        path = Path(path)
        if path.is_symlink() or not path.parent.is_dir():
            raise AuditorKeyDenied("unsafe key path")
        if path.parent.stat().st_mode & 0o077:
            raise AuditorKeyDenied("auditor key directory must be private")
        salt, nonce = os.urandom(16), os.urandom(12)
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        encrypted = AESGCM(_derive(passphrase, salt)).encrypt(
            nonce, raw, b"alpha-labs-level3-auditor-key-v1"
        )
        payload = json.dumps({
            "version": 1, "kdf": "scrypt-n32768-r8-p1",
            "salt": salt.hex(), "nonce": nonce.hex(),
            "ciphertext": encrypted.hex(),
            "public_key": key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            ).hex(),
        }, sort_keys=True).encode()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(fd)
        finally:
            os.close(fd)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return cls(key)

    @classmethod
    def open(cls, path, passphrase):
        path = Path(path)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if os.fstat(fd).st_mode & 0o077:
                raise AuditorKeyDenied("auditor key file must be private")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                payload = json.loads(stream.read())
        finally:
            os.close(fd)
        if set(payload) != {"version", "kdf", "salt", "nonce", "ciphertext", "public_key"}:
            raise AuditorKeyDenied("invalid key envelope")
        if payload["version"] != 1 or payload["kdf"] != "scrypt-n32768-r8-p1":
            raise AuditorKeyDenied("unsupported key envelope")
        try:
            raw = AESGCM(_derive(passphrase, bytes.fromhex(payload["salt"]))).decrypt(
                bytes.fromhex(payload["nonce"]),
                bytes.fromhex(payload["ciphertext"]),
                b"alpha-labs-level3-auditor-key-v1",
            )
            key = Ed25519PrivateKey.from_private_bytes(raw)
        except (ValueError, TypeError, InvalidTag) as exc:
            raise AuditorKeyDenied("invalid passphrase or damaged key") from exc
        signer = cls(key)
        if signer.public_key.hex() != payload["public_key"]:
            raise AuditorKeyDenied("public key mismatch")
        return signer

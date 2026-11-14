"""Validated identity value for research-only paper-account ownership."""
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class VerifiedPrincipal:
    subject: str
    issuer: str

    def __post_init__(self):
        if not isinstance(self.subject, str) or not 1 <= len(self.subject) <= 255:
            raise ValueError("invalid subject")
        if not isinstance(self.issuer, str):
            raise ValueError("invalid issuer")
        url = urlsplit(self.issuer)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("invalid HTTPS issuer")

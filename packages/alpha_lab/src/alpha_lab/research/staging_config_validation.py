"""Fail-closed offline configuration validation for research-only authenticated staging.

No network, secrets, database connection, migrations or deployment.
"""
from ipaddress import ip_network
from urllib.parse import urlsplit


class StagingConfigurationError(ValueError):
    pass


def validate_staging_configuration(*, expected_origin, callback_uri, issuer,
                                   trusted_peer_cidrs, database_dsn_present,
                                   oidc_client_id_present, oidc_secret_present,
                                   verified_ingress_peer=False,
                                   verified_account_backend=False):
    """Return a readiness report, never approval to deploy.

    The boolean evidence gates must be supplied by an independent operator
    review, not inferred from headers, environment variables or CIDR membership.
    """
    def origin(url, *, callback=False):
        if not isinstance(url, str):
            raise StagingConfigurationError("HTTPS origin required")
        p = urlsplit(url)
        if (p.scheme != "https" or not p.hostname or p.username is not None
                or p.password is not None or p.port not in (None, 443)
                or p.query or p.fragment or (p.path != "/auth/callback" if callback
                                              else p.path not in ("", "/"))):
            raise StagingConfigurationError("Invalid HTTPS origin or callback")
        return p.scheme + "://" + p.netloc

    expected = origin(expected_origin)
    if origin(callback_uri, callback=True) != expected:
        raise StagingConfigurationError("Callback and origin mismatch")
    if not isinstance(issuer, str) or not issuer.endswith("/"):
        raise StagingConfigurationError("OIDC issuer must be HTTPS and end with slash")
    origin(issuer[:-1])
    if not isinstance(trusted_peer_cidrs, (tuple, list)) or not trusted_peer_cidrs:
        raise StagingConfigurationError("Explicit peer CIDRs required")
    networks = []
    for cidr in trusted_peer_cidrs:
        try:
            network = ip_network(cidr, strict=True)
        except (ValueError, TypeError) as exc:
            raise StagingConfigurationError("Invalid trusted peer CIDR") from exc
        if network.prefixlen == 0 or network.is_global or network.is_loopback or network.is_multicast or network.is_unspecified:
            raise StagingConfigurationError("Broad, public or local CIDR is not an authenticated proxy")
        networks.append(network)
    gates = {
        "ingress_peer_independently_verified": verified_ingress_peer is True,
        "persistent_postgres_configured": database_dsn_present is True,
        "oidc_client_configured": oidc_client_id_present is True and oidc_secret_present is True,
        "account_backend_independently_verified": verified_account_backend is True,
    }
    return {"mode": "RESEARCH_ONLY", "trading": "DISABLED",
            "ready_for_deployment": False, "gates": gates,
            "all_prerequisites_reported": all(gates.values()),
            "warning": "CIDR validation cannot establish proxy authentication; deployment requires independent review"}

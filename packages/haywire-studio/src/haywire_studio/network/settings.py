"""Studio socket configuration (read once at startup; restart to apply)."""

import ipaddress

from haywire.barn.builtin.types import BOOL, INT, STRING
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


def _valid_cidr_list(value: str) -> bool:
    """Empty string passes; otherwise every comma-separated entry must parse
    as a CIDR network (``ipaddress.ip_network(entry, strict=False)``)."""
    if not value:
        return True
    for entry in value.split(","):
        try:
            ipaddress.ip_network(entry.strip(), strict=False)
        except ValueError:
            return False
    return True


class NetworkSettings(FrameworkSettings, namespace="network"):
    """Where the studio's web server (and the Farmhand MCP mount it carries) binds."""

    port = setting[INT](
        8124,
        label="Studio Port",
        description="Port the studio's web server listens on. Read once at startup; restart to apply.",
        category="network",
        min=1024,
        max=65535,
    )
    expose_to_network = setting[BOOL](
        False,
        label="Expose",
        description=(
            "Expose the studio to the wider network. "
            "This comes with severe security implications. "
            "It is strongly recommended to pair this with enabled authentication and TLS. "
            "Read once at startup; restart to apply."
        ),
        category="network",
    )
    allowed_remote_ranges = setting[STRING](
        "",
        label="Remote Ranges",
        description=(
            "List of allowed remote ranges when exposed to the network. Needs restart to apply. "
            "Comma-separated CIDR ranges (e.g. '192.168.1.0/24, 10.21.136.0/21, 10.0.0.0/8') allowed to "
            "reach the studio. loopback is always allowed regardless."
        ),
        category="network",
        validator=_valid_cidr_list,
    )
    public_hostname = setting[STRING](
        "",
        label="Public Hostname",
        description=(
            "Hostname (optionally with port, e.g. 'haywire.example.com:443') the studio "
            "is reachable at from outside. Feeds the MCP allowed_hosts list when set. "
            "Read once at startup; restart to apply."
        ),
        category="advanced",
    )
    trusted_proxies = setting[STRING](
        "",
        label="Trusted Proxies",
        description=(
            "Reverse proxies whose forwarded headers are trusted. "
            "Takes a list of comma-separated CIDR ranges. "
            "Read once at startup; restart to apply."
        ),
        category="advanced",
        validator=_valid_cidr_list,
    )
    ssl_certfile = setting[STRING](
        "",
        label="TLS Certificate",
        description=(
            "Path to a TLS certificate file. Set together with the key to serve HTTPS "
            "directly — a self-signed pair is adequate on a LAN. Leave both empty for plain "
            "HTTP. Read once at startup; restart to apply."
        ),
        category="advanced",
    )
    ssl_keyfile = setting[STRING](
        "",
        label="TLS Private Key",
        description=(
            "Path to the private key matching the TLS certificate. Both must be set, or "
            "neither. Read once at startup; restart to apply."
        ),
        category="advanced",
    )

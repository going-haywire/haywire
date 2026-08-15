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
        label="Expose to Network",
        description=(
            "Bind the studio's web server to all interfaces instead of loopback-only, "
            "so other machines on the network can reach it. Read once at startup; "
            "restart to apply."
        ),
        category="network",
    )
    allowed_remote_ranges = setting[STRING](
        "",
        label="Allowed Remote Ranges",
        description=(
            "Comma-separated CIDR ranges (e.g. '192.168.1.0/24, 10.0.0.0/8') allowed to "
            "reach the studio. Applies only when Expose to Network is on; loopback is "
            "always allowed regardless. Read once at startup; restart to apply."
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
            "Comma-separated CIDR ranges of reverse proxies whose forwarded headers "
            "are trusted. Read once at startup; restart to apply."
        ),
        category="advanced",
        validator=_valid_cidr_list,
    )

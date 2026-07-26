"""Studio socket configuration (read once at startup; restart to apply)."""

from haywire.barn.builtin.types import BOOL, INT
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


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
    restrict_to_loopback = setting[BOOL](
        True,
        label="Restrict Farmhand to Loopback",
        description=(
            "Reject Farmhand MCP requests (/mcp) whose Host/Origin header isn't "
            "127.0.0.1/localhost, even if the studio's own port is reachable from "
            "the network. Read once at startup; restart to apply."
        ),
        category="network",
    )

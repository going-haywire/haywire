"""Farmhand framework settings (read once at studio startup; restart to apply)."""

from haywire.barn.builtin.types import BOOL
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


class FarmhandSettings(FrameworkSettings, namespace="farmhand"):
    """The Farmhand MCP server's framework-level switches."""

    enabled = setting[BOOL](
        True,
        label="Enable MCP server",
        description=(
            "Serve the MCP endpoint at /mcp on the studio port so AI-agent clients "
            "can operate this studio. Read once at startup; restart to apply."
        ),
        category="farmhand",
    )
    require_auth = setting[BOOL](
        True,
        label="Require Token",
        description=(
            "Require the Authorization: Bearer <token> header on every /mcp request. \n"
            "Disabling removes this check entirely — anyone able to reach /mcp can call "
            "tools. Read once at startup; restart to apply."
        ),
        category="farmhand",
    )
    restrict_to_loopback = setting[BOOL](
        True,
        label="Restrict Farmhand to Loopback",
        description=(
            "DNS-rebinding protection: reject Farmhand MCP requests (/mcp) whose "
            "Host/Origin header isn't 127.0.0.1/localhost, even if the studio's own "
            "port is reachable from the network. Not a defence against a forged "
            "header — an attacker who can set arbitrary headers bypasses this check. "
            "Read once at startup; restart to apply."
        ),
        category="farmhand",
    )

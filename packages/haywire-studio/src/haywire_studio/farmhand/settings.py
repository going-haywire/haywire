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
        label="Local only",
        description=(
            "Protection against DNS-rebinding. Turn off if an MCP client "
            "needs to connect from another machine — but pair with the auth token."
            "Read once at startup; restart to apply."
        ),
        category="farmhand",
    )

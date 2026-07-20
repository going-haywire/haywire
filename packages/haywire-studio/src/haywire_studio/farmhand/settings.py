"""Farmhand framework settings (read once at studio startup; restart to apply)."""

from haywire.barn.builtin.types import BOOL
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


class FarmhandSettings(FrameworkSettings, namespace="farmhand"):
    """The Farmhand MCP server's framework-level switches."""

    enabled = setting[BOOL](
        True,
        label="Enable Farmhand MCP server",
        description=(
            "Serve the MCP endpoint at /mcp on the studio port so AI-agent clients "
            "can operate this studio. Read once at startup; restart to apply."
        ),
        category="farmhand",
    )

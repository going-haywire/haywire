"""Studio socket configuration (read once at startup; restart to apply)."""

from haywire.barn.builtin.types import INT
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


class NetworkSettings(FrameworkSettings, namespace="network"):
    """Where the studio's web server listens.

    **One field, deliberately.** Everything else that used to live here —
    exposure, the peer allowlist, TLS paths, the proxy list — moved to
    ``~/.haywire/security.json`` (ADR 0028), because the settings UI writes the
    *workspace* tier, a per-project file that travels into git and onto other
    machines. A port is a local convenience; an exposure decision is not, and a
    checkbox cannot express the preconditions safe exposure needs.

    A port number is not a security control: binding 8125 instead of 8124
    exposes nothing that 8124 did not.
    """

    port = setting[INT](
        8124,
        label="Studio Port",
        description="Port the studio's web server listens on. Read once at startup; restart to apply.",
        category="network",
        min=1024,
        max=65535,
    )

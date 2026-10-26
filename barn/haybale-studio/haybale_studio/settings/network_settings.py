"""Studio socket configuration (read once at startup; restart to apply)."""

from haywire.barn.builtin.types import INT
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings
from haywire.core.settings.settings_library import LibrarySettings
from haywire_studio.network import DEFAULT_STUDIO_PORT


# namespace + field name must equal haywire_studio.network.STUDIO_PORT_KEY.
@settings(
    namespace="network",
    label="Network",
    description="Where the studio's web server listens.",
)
class NetworkSettings(LibrarySettings):
    """Where the studio's web server listens.

    Holds only the port. Exposure, the peer allowlist, TLS paths and the proxy
    list live in ``~/.haywire/security.json`` (ADR 0028): the settings UI writes
    the workspace tier, a per-project file that travels into git and onto other
    machines.

    A port number is not a security control: binding 8125 instead of 8124
    exposes nothing that 8124 did not.
    """

    port = setting[INT](
        DEFAULT_STUDIO_PORT,
        label="Studio Port",
        description="Port the studio's web server listens on. Read once at startup; restart to apply.",
        category="network",
        min=1024,
        max=65535,
    )

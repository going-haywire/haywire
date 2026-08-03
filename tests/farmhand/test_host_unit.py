"""Host mechanics that need no transport: capability advertisement, tool table, error format."""

from unittest.mock import patch

from typing import Any, cast

import pytest

from haywire.core.farmhand import FarmhandError
from haywire_studio.farmhand import host as host_module
from haywire_studio.farmhand.auth import BearerTokenMiddleware
from haywire_studio.farmhand.host import FarmhandHost, _FarmhandServer, _format_tool_error
from haywire_studio.farmhand.settings import FarmhandSettings
from haywire_studio.network.settings import NetworkSettings

pytestmark = pytest.mark.unit


def test_require_auth_descriptor_default_is_true():
    # Security-relevant default: the raw descriptor default (independent of any
    # registry/TOML override picked up by other tests in this session) must
    # require a bearer token unless a user explicitly opts out. Guards against
    # silent flips of this default.
    assert FarmhandSettings.__dict__["require_auth"]._default is True


def test_restrict_to_loopback_descriptor_default_is_true():
    assert NetworkSettings.__dict__["restrict_to_loopback"]._default is True


def test_initialization_options_advertise_tools_list_changed():
    # A capability is only present once its handler is registered (SDK gates on
    # request_handlers), so register the tools handler the way the host does.
    server = _FarmhandServer("farmhand")

    @server.list_tools()
    async def _list_tools():
        return []

    options = server.create_initialization_options()
    assert options.capabilities.tools.listChanged is True
    # resources/prompts capabilities appear once their handlers are registered
    # (resources: Task 14). The NotificationOptions carry the listChanged flags
    # so those capabilities advertise True as soon as the handler is added.


def test_format_tool_error_stable_code_no_traceback():
    err = FarmhandError("graph_not_found", "No open graph 'x'", ids={"binding_id": "x"})
    text = _format_tool_error(err)
    assert "[graph_not_found]" in text
    assert "No open graph 'x'" in text
    assert "binding_id=x" in text
    assert "Traceback" not in text


def test_format_tool_error_wraps_unexpected_exceptions():
    text = _format_tool_error(ValueError("boom"))
    assert "[internal]" in text
    assert "boom" in text
    assert "Traceback" not in text


def test_tool_table_seed_and_evict():
    from haywire.core.farmhand import Farmhand, FarmhandRegistry, ToolAnnotations
    from haywire.core.farmhand.identity import FarmhandIdentity
    from haywire.core.library.identity import LibraryIdentity

    registry = FarmhandRegistry()

    class PingTool(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    PingTool.class_identity = FarmhandIdentity(
        registry_id="ping",
        registry_key="studio:farmhand:ping",
        label="Ping",
        description="",
        class_name="PingTool",
        module=__name__,
        annotations=ToolAnnotations(),
    )
    PingTool.class_library = LibraryIdentity(
        label="Studio",
        version="0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path="/tmp/studio",
        module_name="studio",
        id="studio",
    )
    registry._register_class(PingTool, PingTool.class_library)

    host = FarmhandHost.__new__(FarmhandHost)  # table mechanics only, no service needed
    host._tools = {}
    host._registry = registry
    host._seed_tools()
    assert host._tools == {"studio_ping": PingTool}

    host._remove_tool_by_key("studio:farmhand:ping")
    assert host._tools == {}


class _FakeAppTarget:
    """Records what mount() wires up, without needing a real FastAPI/NiceGUI app."""

    def __init__(self):
        self.mounted: dict[str, object] = {}

    def mount(self, path: str, app) -> None:
        self.mounted[path] = app


def _bare_host(tmp_path) -> FarmhandHost:
    host = FarmhandHost.__new__(FarmhandHost)
    host._workspace_root = str(tmp_path)
    host._server = _FarmhandServer("farmhand")
    return host


def test_mount_wraps_with_bearer_middleware_when_require_auth(tmp_path):
    host = _bare_host(tmp_path)
    target = _FakeAppTarget()
    with (
        patch.object(host_module, "FarmhandSettings") as settings_cls,
        patch.object(host_module, "NetworkSettings") as network_cls,
    ):
        settings_cls.return_value.require_auth = True
        network_cls.return_value.restrict_to_loopback = True
        host.mount(8082, app_target=target)
    assert isinstance(target.mounted["/mcp"], BearerTokenMiddleware)


def test_mount_skips_bearer_middleware_when_require_auth_false(tmp_path):
    host = _bare_host(tmp_path)
    target = _FakeAppTarget()
    with (
        patch.object(host_module, "FarmhandSettings") as settings_cls,
        patch.object(host_module, "NetworkSettings") as network_cls,
    ):
        settings_cls.return_value.require_auth = False
        network_cls.return_value.restrict_to_loopback = True
        host.mount(8082, app_target=target)
    assert not isinstance(target.mounted["/mcp"], BearerTokenMiddleware)
    # No token generated at all — nothing written under .haywire/.
    assert not (tmp_path / ".haywire" / "farmhand_token").exists()


def test_mount_disables_dns_rebinding_protection_when_loopback_unrestricted(tmp_path):
    host = _bare_host(tmp_path)
    target = _FakeAppTarget()
    with (
        patch.object(host_module, "FarmhandSettings") as settings_cls,
        patch.object(host_module, "NetworkSettings") as network_cls,
    ):
        settings_cls.return_value.require_auth = True
        network_cls.return_value.restrict_to_loopback = False
        host.mount(8082, app_target=target)
    assert cast(Any, host._session_manager).security_settings.enable_dns_rebinding_protection is False


def test_mount_keeps_dns_rebinding_protection_by_default(tmp_path):
    host = _bare_host(tmp_path)
    target = _FakeAppTarget()
    with (
        patch.object(host_module, "FarmhandSettings") as settings_cls,
        patch.object(host_module, "NetworkSettings") as network_cls,
    ):
        settings_cls.return_value.require_auth = True
        network_cls.return_value.restrict_to_loopback = True
        host.mount(8082, app_target=target)
    security = cast(Any, host._session_manager).security_settings
    assert security.enable_dns_rebinding_protection is True
    assert "127.0.0.1:8082" in security.allowed_hosts

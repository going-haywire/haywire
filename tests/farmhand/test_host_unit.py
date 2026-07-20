"""Host mechanics that need no transport: capability advertisement, tool table, error format."""

import pytest

from haywire.core.farmhand import FarmhandError
from haywire_studio.farmhand.host import FarmhandHost, _FarmhandServer, _format_tool_error

pytestmark = pytest.mark.unit


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

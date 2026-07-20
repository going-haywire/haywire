"""FarmhandRegistry: class filter, register/lookup, lifecycle event surface."""

import pytest

from haywire.core.farmhand import Farmhand, FarmhandRegistry, ToolAnnotations
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEventType

pytestmark = pytest.mark.unit


def _lib_identity(lib_id: str) -> LibraryIdentity:
    return LibraryIdentity(
        label=lib_id,
        version="0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path="/tmp/fake",
        module_name=lib_id,
        id=lib_id,
    )


def _library_tool(lib_id: str = "testing", name: str = "echo"):
    """Build a tool class with a hand-stamped identity (no library import machinery)."""
    from haywire.core.farmhand.identity import FarmhandIdentity

    class EchoTool(Farmhand):
        async def run(self, ctx, text: str) -> dict:
            return {"echo": text}

    EchoTool.class_identity = FarmhandIdentity(
        registry_id=name,
        registry_key=f"{lib_id}:farmhand:{name}",
        label=name,
        description="",
        class_name="EchoTool",
        module=__name__,
        annotations=ToolAnnotations(read_only_hint=True),
    )
    EchoTool.class_library = _lib_identity(lib_id)
    return EchoTool


def test_class_filter_accepts_decorated_tools_only():
    registry = FarmhandRegistry()
    assert registry._class_filter(_library_tool()) is True
    assert registry._class_filter(Farmhand) is False
    assert registry._class_filter(dict) is False

    class Undecorated(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    assert registry._class_filter(Undecorated) is False  # no class_identity


def test_register_and_lookup():
    registry = FarmhandRegistry()
    tool = _library_tool()
    key = registry._register_class(tool, tool.class_library)
    assert key == "testing:farmhand:echo"
    assert registry.get("testing:farmhand:echo") is tool


def test_unregister_removes_class():
    registry = FarmhandRegistry()
    tool = _library_tool()
    registry._register_class(tool, tool.class_library)
    registry._unregister_class("testing:farmhand:echo")
    assert registry.get("testing:farmhand:echo") is None


def test_lifecycle_event_types_exist():
    # The host (Task 8) keys its pipeline on these two event types.
    assert LifeCycleEventType.CLASS_ADDED is not None
    assert LifeCycleEventType.CLASS_REMOVED is not None

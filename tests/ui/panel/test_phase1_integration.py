"""Cross-cutting: define a Panel, register it, query the registry by surface, get the panel."""

from typing import Protocol, runtime_checkable
from unittest.mock import MagicMock

from haybale_graph_editor.state.edit_state import EditState
from haywire.core.library.identity import LibraryIdentity
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.context import SessionContext
from haywire.ui.panel import BasePanel, PanelRegistry, panel
from haywire.ui.surface import Surface


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    folder_path="/tmp/fake",
    module_name="fake",
    name="fake",
)


@runtime_checkable
class _Verbose(Protocol):
    def speak(self) -> None: ...


class _LoudMenu(Surface):
    id = "loud_test_menu"
    provides = _Verbose


class _QuietInspector(Surface):
    id = "quiet_test_inspector"


@panel(surface=_LoudMenu, label="Speaker")
class _SpeakerPanel(BasePanel):
    actions: _Verbose

    @classmethod
    def poll(cls, ctx):
        return ctx.data[EditState].active_node is not None

    def draw(self, ctx, layout):
        pass


@panel(surface=_QuietInspector, label="Speaker Info", registry_id="speaker_info_phase1")
class _SpeakerInfoPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


def test_full_pipeline_panel_registered_and_queryable():
    reg = PanelRegistry()
    reg._register_class(_SpeakerPanel, _FAKE_LIBRARY_IDENTITY)

    assert _SpeakerPanel in reg.get_panels(_LoudMenu)


def test_a_panel_only_appears_on_its_own_surface():
    """The display/action fork is gone: which panels a surface yields depends
    on the surface id alone, so a menu panel is simply absent from another
    surface's list rather than filtered out by a second axis."""
    reg = PanelRegistry()
    reg._register_class(_SpeakerPanel, _FAKE_LIBRARY_IDENTITY)

    assert _SpeakerPanel not in reg.get_panels(_QuietInspector)


def test_full_pipeline_surface_discovered_via_get_root_surfaces():
    reg = PanelRegistry()
    reg._register_class(_SpeakerInfoPanel, _FAKE_LIBRARY_IDENTITY)

    assert _QuietInspector in reg.get_root_surfaces()


def test_a_menu_surface_is_a_root_too():
    """Root-ness is not the strip's whole filter — a menu surface no panel
    hosts is a root as well, and the strip additionally requires
    ``presentation`` (which a menu surface never declares)."""
    reg = PanelRegistry()
    reg._register_class(_SpeakerPanel, _FAKE_LIBRARY_IDENTITY)

    assert _LoudMenu in reg.get_root_surfaces()
    assert _LoudMenu.presentation is None


def test_panel_poll_is_classmethod_and_reads_session_context(register_edit_state):
    container = LibraryStateContainer(LibraryStateRegistry())
    sid = "t"
    EditStateCls = register_edit_state(container, sid)

    app = MagicMock()
    app.library_state_container = container
    ctx = SessionContext(session_id=sid, app=app)

    # No active node — poll returns False.
    assert _SpeakerPanel.poll(ctx) is False

    ctx.data[EditStateCls].active_node = MagicMock()
    assert _SpeakerPanel.poll(ctx) is True

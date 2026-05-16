"""Cross-cutting: define a Panel, register it, query the registry, get an actions provider, get the panel."""

from typing import Protocol, runtime_checkable
from unittest.mock import MagicMock

from haybale_graph_editor.state.edit_state import EditState
from haywire.core.library.identity import LibraryIdentity
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.context import SessionContext
from haywire.ui.panel import BasePanel, PanelRegistry, panel
from haywire.ui.panel.focus import Focus


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    description="test",
    url="",
    help_url="",
    author="",
    author_url="",
    folder_path="/tmp/fake",
    module_name="fake",
    id="fake",
)


@runtime_checkable
class _Verbose(Protocol):
    def speak(self) -> None: ...


class _LoudFocus(Focus):
    id = "loud_test_focus"
    label = "Loud"
    icon = "volume_up"

    @classmethod
    def available(cls, ctx):
        return True


# Action panel — queries via get_panels_for_action.
@panel(actions=_Verbose, focus=_LoudFocus, label="Speaker")
class _SpeakerPanel(BasePanel):
    actions: _Verbose

    @classmethod
    def poll(cls, ctx):
        return ctx.data[EditState].active_node is not None

    def draw(self, ctx, layout):
        pass


# Display panel — queries via get_panels_for_focus / get_display_focuses.
@panel(focus=_LoudFocus, label="Speaker Info", registry_id="speaker_info_phase1")
class _SpeakerInfoPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


def test_full_pipeline_action_panel_registered_and_queryable():
    reg = PanelRegistry()
    reg._register_class(_SpeakerPanel, _FAKE_LIBRARY_IDENTITY)

    panels = reg.get_panels_for_action(_Verbose, _LoudFocus)
    assert _SpeakerPanel in panels


def test_full_pipeline_action_panel_not_returned_by_display_query():
    reg = PanelRegistry()
    reg._register_class(_SpeakerPanel, _FAKE_LIBRARY_IDENTITY)

    # Action panel must NOT appear in display queries.
    panels = reg.get_panels_for_focus(_LoudFocus)
    assert _SpeakerPanel not in panels


def test_full_pipeline_display_panel_discovered_via_get_display_focuses():
    reg = PanelRegistry()
    reg._register_class(_SpeakerInfoPanel, _FAKE_LIBRARY_IDENTITY)

    focuses = reg.get_display_focuses()
    assert _LoudFocus in focuses


def test_full_pipeline_action_panel_focus_not_in_get_display_focuses():
    reg = PanelRegistry()
    reg._register_class(_SpeakerPanel, _FAKE_LIBRARY_IDENTITY)

    # Action panels don't contribute to display focuses.
    focuses = reg.get_display_focuses()
    assert _LoudFocus not in focuses


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

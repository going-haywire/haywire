"""Cross-cutting: define a Panel, register it, query the registry, get an actions provider, get the panel."""

from typing import Protocol, runtime_checkable
from unittest.mock import MagicMock

from haybale_studio.state.edit_state import EditState
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


@panel(action=_Verbose, focus=_LoudFocus, label="Speaker")
class _SpeakerPanel(BasePanel):
    @classmethod
    def poll(cls, ctx):
        return ctx.data[EditState].active_node.value is not None

    def draw(self, ctx, layout, actions):
        pass


def test_full_pipeline_panel_registered_and_queryable():
    reg = PanelRegistry()
    reg._register_class(_SpeakerPanel, _FAKE_LIBRARY_IDENTITY)

    class Host:
        def speak(self) -> None:
            pass

    host = Host()
    panels = reg.get_panels_for(actions_provider=host, focus=_LoudFocus)
    assert _SpeakerPanel in panels


def test_full_pipeline_focus_discovered_via_registry():
    reg = PanelRegistry()
    reg._register_class(_SpeakerPanel, _FAKE_LIBRARY_IDENTITY)

    class Host:
        def speak(self) -> None:
            pass

    focuses = reg.get_focuses_for(actions_provider=Host())
    assert _LoudFocus in focuses


def test_panel_poll_is_classmethod_and_reads_session_context(register_edit_state):
    container = LibraryStateContainer(LibraryStateRegistry())
    sid = "t"
    EditStateCls = register_edit_state(container, sid)

    app = MagicMock()
    app.library_state_container = container
    ctx = SessionContext(session_id=sid, app=app)

    # No active node — poll returns False.
    assert _SpeakerPanel.poll(ctx) is False

    ctx.data[EditStateCls].active_node.value = MagicMock()
    assert _SpeakerPanel.poll(ctx) is True

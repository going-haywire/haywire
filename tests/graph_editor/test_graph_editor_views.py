"""GraphEditor's two views per level: the patch and the stage, switched in the header."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.access import level_mode
from haybale_graph_editor.editors import graph_editor as graph_editor_module
from haybale_graph_editor.editors.graph_canvas.event_handlers import build_event_handler_map, handles_event
from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL, GraphEditor
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.access import AccessTier, LevelMode, access_resolver, set_access_resolver
from haywire.core.graph.edit_route import EditRoute
from haywire.core.node.layout import STAGE
from haywire.core.session.handlers import _REACT_ON_ATTR
from haywire.core.signals import (
    Copy,
    Cut,
    Delete,
    Duplicate,
    Paste,
    Redo,
    SelectAll,
    SelectionMoved,
    ToggleLock,
    ToggleStageView,
    Undo,
)
from haywire.ui.components.graph.event_definitions import BaseGraphEvent, SelectionChangedEvent
from haywire.ui.components.zoom.pan import Viewport

from .test_graph_editor_levels import _editor, _FakeDocument, _FakeGraph

pytestmark = pytest.mark.unit

BINDING = "/tmp/graphs/main.haywire"


@pytest.fixture(autouse=True)
def _restore_resolver():
    previous = access_resolver()
    yield
    set_access_resolver(previous)


def _real_context(tier: AccessTier) -> Any:
    from haywire.core.session.context import SessionContext

    set_access_resolver(lambda name: tier)
    app = MagicMock()
    app.library_state_container = MagicMock()
    ctx = SessionContext(session_id="s1", app=app)
    ctx.principal = "someone"
    return ctx


def _canvas(level: Any) -> Any:
    """A stand-in canvas that records the level mode it last showed, as ``refresh_mode`` reads it.

    Like the real canvas, it keeps its selection in every mode.
    """
    canvas = MagicMock()
    canvas.mode = level.route.mode()

    def refresh_mode() -> None:
        canvas.mode = level.route.mode()

    canvas.refresh_mode.side_effect = refresh_mode
    return canvas


def _views_editor(open_view: str = "patch", mounted: tuple[str, ...] | None = None) -> tuple[Any, Any]:
    """An editor over a document whose canvases are stand-ins built by a stubbed ``_mount_view``.

    ``mounted`` names the views already built; by default just ``open_view``.
    """
    document = _FakeDocument()
    document.editor.graph.props = SimpleNamespace(open_locked=False, open_view=open_view)  # type: ignore[assignment]
    editor, context, _ = _editor(document)
    context.can_access = AccessTier.ADMIN.satisfies
    editor._levels[DOCUMENT_LEVEL] = editor._new_level(context, DOCUMENT_LEVEL, document)
    level = editor._levels[DOCUMENT_LEVEL]
    level.view_panels = MagicMock()
    mounts: list[str] = []

    def mount_view(_context: Any, lvl: Any, view: str, viewport: Any = None) -> None:
        mounts.append(view)
        lvl.canvases[view] = _canvas(lvl)

    editor._mount_view = mount_view  # type: ignore[method-assign,assignment]
    editor.mounts = mounts  # type: ignore[attr-defined]
    for view in mounted if mounted is not None else (open_view,):
        mount_view(context, level, view)
    mounts.clear()
    context.data = {
        EditState: SimpleNamespace(
            active_graph=None,
            active_node=None,
            selected_nodes=set(),
            selected_edges=set(),
            active_edge=None,
            active_mode=LevelMode.VIEW,
            active_route=None,
        )
    }
    context.active_component = None
    return editor, context


def _route_for(editor: Any, ctx: Any) -> None:
    """Give the document level a route whose mode follows ``ctx`` and the level's lock."""
    level = editor._levels[DOCUMENT_LEVEL]
    level.route = EditRoute(lambda: level.container.editor, lambda: level_mode(ctx.can_access, level.locked))


class _FakeButton:
    """Records the classes and props a header view button is given."""

    def __init__(self) -> None:
        self.cls: set[str] = set()
        self.pressed = ""

    def classes(self, add: str | None = None, remove: str | None = None) -> "_FakeButton":
        self.cls -= set((remove or "").split())
        self.cls |= set((add or "").split())
        return self

    def props(self, text: str) -> "_FakeButton":
        self.pressed = text.split("=", 1)[1]
        return self


def _with_buttons(editor: Any) -> dict[str, _FakeButton]:
    buttons = {"patch": _FakeButton(), "stage": _FakeButton()}
    editor._view_buttons = buttons
    editor._update_view_switch(editor._levels[DOCUMENT_LEVEL])
    return buttons


class TestViewSwitchMarking:
    @staticmethod
    def _active(buttons: dict[str, _FakeButton]) -> list[str]:
        marked = [v for v, b in buttons.items() if "hw-shell-toolbar-btn-active" in b.cls]
        assert marked == [v for v, b in buttons.items() if b.pressed == "true"]
        return marked

    def test_the_patch_is_marked_on_open(self):
        editor, _ = _views_editor()
        assert self._active(_with_buttons(editor)) == ["patch"]

    def test_open_view_stage_marks_the_stage(self):
        editor, _ = _views_editor("stage")
        assert self._active(_with_buttons(editor)) == ["stage"]

    def test_switching_moves_the_mark(self):
        editor, context = _views_editor()
        buttons = _with_buttons(editor)
        editor._switch_view(context, DOCUMENT_LEVEL, "stage")
        assert self._active(buttons) == ["stage"]
        editor._switch_view(context, DOCUMENT_LEVEL, "patch")
        assert self._active(buttons) == ["patch"]

    def test_the_toggle_command_moves_the_mark(self):
        editor, context = _views_editor()
        buttons = _with_buttons(editor)
        editor._on_toggle_stage_view(context, ToggleStageView(binding_id=""))
        assert self._active(buttons) == ["stage"]

    def test_a_level_change_shows_that_levels_view(self):
        editor, _ = _views_editor("stage")
        buttons = _with_buttons(editor)
        other = SimpleNamespace(key="other", view="patch")
        editor._update_view_switch(other)  # not the level on screen: ignored
        assert self._active(buttons) == ["stage"]
        other.key = editor._active_level
        editor._update_view_switch(other)
        assert self._active(buttons) == ["patch"]


class TestTwoCanvasesPerLevel:
    def test_first_switch_mounts_the_stage_and_later_switches_reuse_both(self):
        editor, context = _views_editor()
        level = editor._levels[DOCUMENT_LEVEL]
        patch = level.canvases["patch"]

        editor._switch_view(context, DOCUMENT_LEVEL, "stage")
        stage = level.canvases["stage"]
        editor._switch_view(context, DOCUMENT_LEVEL, "patch")
        editor._switch_view(context, DOCUMENT_LEVEL, "stage")

        assert editor.mounts == ["stage"]  # type: ignore[attr-defined]
        assert level.canvases == {"patch": patch, "stage": stage}
        assert level.canvas_manager is stage
        assert level.view == "stage"
        level.view_panels.set_value.assert_any_call("patch")
        level.view_panels.set_value.assert_called_with("stage")

    def test_switching_to_the_view_on_screen_does_nothing(self):
        editor, context = _views_editor()
        editor._switch_view(context, DOCUMENT_LEVEL, "patch")
        editor._switch_view(context, DOCUMENT_LEVEL, "nonsense")
        assert editor.mounts == []  # type: ignore[attr-defined]
        assert editor._levels[DOCUMENT_LEVEL].view == "patch"

    def test_the_visible_canvas_is_the_levels_canvas_manager(self):
        editor, context = _views_editor()
        level = editor._levels[DOCUMENT_LEVEL]
        assert editor._canvas_manager is level.canvases["patch"]
        editor._switch_view(context, DOCUMENT_LEVEL, "stage")
        assert editor._canvas_manager is level.canvases["stage"]

    def test_switch_empties_the_canvas_left_and_shows_the_session_selection_on_the_one_shown(self):
        editor, context = _views_editor(mounted=("patch", "stage"))
        level = editor._levels[DOCUMENT_LEVEL]
        patch, stage = level.canvases["patch"], level.canvases["stage"]

        editor._switch_view(context, DOCUMENT_LEVEL, "stage")

        patch.clear_selection.assert_called_once_with()
        stage.show_session_selection.assert_called_once_with()
        patch.show_session_selection.assert_not_called()

    def test_a_level_off_screen_does_not_touch_the_session_selection(self):
        editor, context = _views_editor(mounted=("patch", "stage"))
        editor._active_level = "elsewhere"
        stage = editor._levels[DOCUMENT_LEVEL].canvases["stage"]

        editor._switch_view(context, DOCUMENT_LEVEL, "stage")

        stage.show_session_selection.assert_not_called()

    def test_a_switch_claims_the_session_for_the_editor(self):
        editor, context = _views_editor()
        editor._switch_view(context, DOCUMENT_LEVEL, "stage")
        editor._claim_session_state.assert_called_once_with(context)  # type: ignore[attr-defined]

    def test_a_switch_hides_the_selection_toolbars(self):
        editor, context = _views_editor()
        provider = MagicMock()
        editor._levels[DOCUMENT_LEVEL].canvases["patch"]._toolbar_provider = provider
        editor._switch_view(context, DOCUMENT_LEVEL, "stage")
        provider.hide.assert_called_once_with()


def _select_node(editor: Any, context: Any) -> Any:
    """Select node ``n1`` for the session on the document level, which the session is on."""
    level = editor._levels[DOCUMENT_LEVEL]
    edit_state = context.data[EditState]
    edit_state.active_graph = level.container.editor.graph
    edit_state.active_node = MagicMock(name="node")
    edit_state.selected_nodes = {"n1"}
    edit_state.selected_edges = {"e1"}
    context.active_component = "lib:node:Blur"
    context.session = MagicMock()
    context.can_edit = lambda: True
    return edit_state


def _published(context: Any, kind: type) -> int:
    return sum(isinstance(call.args[0], kind) for call in context.session.publish.call_args_list)


class TestLockingKeepsTheSelection:
    def test_locking_the_level_on_screen_keeps_the_selection(self):
        """Selection is looking; only acting on it needs edit."""
        editor, context = _views_editor(mounted=("patch", "stage"))
        edit_state = _select_node(editor, context)
        level = editor._levels[DOCUMENT_LEVEL]

        assert editor.set_level_locked(context, DOCUMENT_LEVEL, True) is True

        assert edit_state.selected_nodes == {"n1"}
        assert edit_state.selected_edges == {"e1"}
        assert edit_state.active_node is not None
        assert context.active_component == "lib:node:Blur"
        level.canvases["patch"].clear_selection.assert_not_called()
        level.canvases["stage"].clear_selection.assert_not_called()

    def test_locking_a_level_off_screen_leaves_the_session_selection(self):
        editor, context = _views_editor(mounted=("patch", "stage"))
        edit_state = _select_node(editor, context)
        editor._active_level = "elsewhere"

        assert editor.set_level_locked(context, DOCUMENT_LEVEL, True) is True

        assert edit_state.selected_nodes == {"n1"}
        assert edit_state.active_node is not None
        assert _published(context, SelectionMoved) == 0

    def test_unlocking_keeps_the_selection(self):
        editor, context = _views_editor(mounted=("patch", "stage"))
        _select_node(editor, context)
        editor.set_level_locked(context, DOCUMENT_LEVEL, True)

        assert editor.set_level_locked(context, DOCUMENT_LEVEL, False) is True

        edit_state = context.data[EditState]
        assert edit_state.selected_nodes == {"n1"}
        assert edit_state.active_node is not None


class TestTheLockReachesBothCanvases:
    def test_lock_applies_to_both_canvases(self):
        editor, context = _views_editor(mounted=("patch", "stage"))
        context.can_edit = lambda: True
        level = editor._levels[DOCUMENT_LEVEL]

        assert editor.set_level_locked(context, DOCUMENT_LEVEL, True) is True

        assert level.canvases["patch"].mode is LevelMode.OPERATE
        assert level.canvases["stage"].mode is LevelMode.OPERATE

    def test_a_stage_mounted_after_the_lock_is_locked(self):
        editor, context = _views_editor()
        context.can_edit = lambda: True
        editor.set_level_locked(context, DOCUMENT_LEVEL, True)
        editor._switch_view(context, DOCUMENT_LEVEL, "stage")
        assert editor._levels[DOCUMENT_LEVEL].canvases["stage"].mode is LevelMode.OPERATE


class TestOpenView:
    def test_a_level_opens_on_the_graphs_open_view(self):
        editor, _ = _views_editor("stage")
        assert editor._levels[DOCUMENT_LEVEL].view == "stage"

    def test_an_unknown_open_view_opens_the_patch(self):
        editor, _ = _views_editor("sideways")
        assert editor._levels[DOCUMENT_LEVEL].view == "patch"

    def test_open_view_stage_opens_on_the_stage_and_mounts_the_patch_lazily(self):
        editor, context = _views_editor("stage")
        level = editor._levels[DOCUMENT_LEVEL]
        assert list(level.canvases) == ["stage"]
        assert level.canvas_manager is level.canvases["stage"]

        editor._switch_view(context, DOCUMENT_LEVEL, "patch")

        assert editor.mounts == ["patch"]  # type: ignore[attr-defined]
        assert set(level.canvases) == {"patch", "stage"}

    def test_the_first_canvas_a_level_mounts_reports_compatibility(self, monkeypatch):
        editor, context, _ = _real_mount_editor(monkeypatch)
        level = editor._levels[DOCUMENT_LEVEL]
        level.view = "stage"
        built: list[Any] = []

        def build_canvas(*_args: Any, **kwargs: Any) -> Any:
            built.append(kwargs)
            return MagicMock()

        editor._build_canvas = build_canvas  # type: ignore[method-assign]

        GraphEditor._mount_view(editor, context, level, "stage")
        GraphEditor._mount_view(editor, context, level, "patch")

        assert [k["reports_compatibility"] for k in built] == [True, False]
        assert [k["view"] for k in built] == ["stage", "patch"]


def _real_mount_editor(monkeypatch: Any) -> tuple[GraphEditor, Any, Any]:
    editor, context, document = _editor()
    monkeypatch.setattr(graph_editor_module, "ui", MagicMock())
    editor._level_panels = MagicMock()
    editor._levels[DOCUMENT_LEVEL].view_panels = MagicMock()
    return editor, context, document


class TestCommandsInStageView:
    def test_toggle_stage_view_works_at_view_tier_and_on_a_locked_level(self):
        editor, context = _views_editor()
        level = editor._levels[DOCUMENT_LEVEL]
        level.locked = True
        ctx = _real_context(AccessTier.VIEW)
        _route_for(editor, ctx)

        assert ToggleStageView.access is AccessTier.VIEW
        assert editor.accepts_command(ctx, ToggleStageView(binding_id=BINDING)) is True

        editor._on_toggle_stage_view(context, ToggleStageView(binding_id=BINDING))
        assert level.view == "stage"
        editor._on_toggle_stage_view(context, ToggleStageView(binding_id=BINDING))
        assert level.view == "patch"

    def test_the_editor_reacts_to_toggle_stage_view(self):
        assert getattr(GraphEditor._on_toggle_stage_view, _REACT_ON_ATTR, ()) == (ToggleStageView,)

    def test_stage_view_accepts_every_command_patch_view_accepts(self):
        stage, _ = _views_editor("stage")
        patch_, _ = _views_editor("patch")
        ctx = _real_context(AccessTier.ADMIN)
        _route_for(stage, ctx)
        _route_for(patch_, ctx)

        for command in (
            Paste,
            Cut,
            Duplicate,
            Delete,
            Undo,
            Redo,
            Copy,
            SelectAll,
            ToggleLock,
            ToggleStageView,
        ):
            assert stage.accepts_command(ctx, command(binding_id=BINDING)) is True, command
            assert patch_.accepts_command(ctx, command(binding_id=BINDING)) is True, command

    def test_patch_view_still_accepts_paste(self):
        editor, _ = _views_editor("patch")
        ctx = _real_context(AccessTier.ADMIN)
        _route_for(editor, ctx)
        assert editor.accepts_command(ctx, Paste(binding_id=BINDING)) is True

    def test_a_locked_stage_view_is_capped_exactly_as_a_locked_patch_view(self):
        ctx = _real_context(AccessTier.ADMIN)
        for view in ("stage", "patch"):
            editor, _ = _views_editor(view)
            editor._levels[DOCUMENT_LEVEL].locked = True
            _route_for(editor, ctx)
            for command in (Delete, Paste, Duplicate, Cut, Copy):
                assert editor.accepts_command(ctx, command(binding_id=BINDING)) is False, (view, command)
            for allowed in (ToggleStageView, SelectAll):
                assert editor.accepts_command(ctx, allowed(binding_id=BINDING)) is True, (view, allowed)


class TestTeardownAndRepoint:
    def test_teardown_and_repoint_handle_both_canvases(self):
        editor, context = _views_editor(mounted=("patch", "stage"))
        level = editor._levels[DOCUMENT_LEVEL]
        level.view = "stage"
        patch, stage = level.canvases["patch"], level.canvases["stage"]
        patch.zoom_container.get_viewport.return_value = Viewport(zoom=1.5, pan_x=-10.0, pan_y=-20.0)
        stage.zoom_container.get_viewport.return_value = Viewport(zoom=0.5, pan_x=-30.0, pan_y=-40.0)
        editor._level_panels = MagicMock()
        editor._mount_level = MagicMock()  # type: ignore[method-assign]
        calls: list[tuple[str, Any]] = []
        editor._mount_view = lambda ctx, lvl, view, viewport=None: calls.append((view, viewport))  # type: ignore[method-assign]
        editor._teardown_level = lambda old: GraphEditor._teardown_canvas(editor, old)  # type: ignore[method-assign]
        container = level.container

        editor._repoint_level(context, level, container)  # type: ignore[arg-type]

        patch.cleanup.assert_called_once_with()
        stage.cleanup.assert_called_once_with()
        assert level.canvases == {}
        replacement = editor._levels[DOCUMENT_LEVEL]
        assert replacement is not level
        assert replacement.view == "stage"
        editor._mount_level.assert_called_once_with(  # type: ignore[attr-defined]
            context, replacement, viewport=Viewport(zoom=0.5, pan_x=-30.0, pan_y=-40.0)
        )
        assert calls == [("patch", Viewport(zoom=1.5, pan_x=-10.0, pan_y=-20.0))]

    def test_cleanup_releases_every_canvas_of_every_level(self):
        editor, _ = _views_editor(mounted=("patch", "stage"))
        level = editor._levels[DOCUMENT_LEVEL]
        patch, stage = level.canvases["patch"], level.canvases["stage"]

        editor.cleanup()

        patch.cleanup.assert_called_once_with()
        stage.cleanup.assert_called_once_with()

    def test_rekey_locks_both_canvases_of_a_level_that_became_a_placement(self, monkeypatch):
        editor, context = _views_editor(mounted=("patch", "stage"))
        level = editor._levels[DOCUMENT_LEVEL]
        monkeypatch.setattr(graph_editor_module, "level_key_for", lambda container: DOCUMENT_LEVEL)
        monkeypatch.setattr(graph_editor_module, "inside_placement", lambda container: True)

        editor._rekey_level(context, level)

        assert level.locked is True
        assert level.canvases["patch"].mode is LevelMode.OPERATE
        assert level.canvases["stage"].mode is LevelMode.OPERATE

    def test_hiding_toolbars_reaches_both_canvases(self):
        editor, _ = _views_editor(mounted=("patch", "stage"))
        level = editor._levels[DOCUMENT_LEVEL]
        for canvas in level.canvases.values():
            canvas._toolbar_provider = MagicMock()
        editor._hide_toolbars()
        for canvas in level.canvases.values():
            canvas._toolbar_provider.hide.assert_called_once_with()


class TestAPointerGestureOnTheStageClaimsTheSession:
    def test_pointer_gesture_on_the_stage_canvas_claims_the_session(self):
        editor, context = _views_editor(mounted=("patch", "stage"))
        level = editor._levels[DOCUMENT_LEVEL]
        level.view = "stage"
        claimed: list[Any] = []
        editor._claim_session_state = lambda ctx: claimed.append(ctx)  # type: ignore[method-assign]
        stage = level.canvases["stage"]
        patch = level.canvases["patch"]

        editor._on_canvas_gesture(context, patch)
        assert claimed == []  # the canvas that is not on screen claims nothing
        editor._on_canvas_gesture(context, stage)
        assert claimed == [context]

    def test_the_real_stage_manager_reports_the_gesture_before_dispatching(self):
        """Through ``_handle_canvas_event``: the stage canvas calls ``on_user_event`` for a pointer event."""

        class _Source:
            @handles_event(SelectionChangedEvent, access=LevelMode.VIEW)
            def seen(self, event: BaseGraphEvent) -> None:
                pass

        reported: list[bool] = []
        manager: Any = object.__new__(GraphCanvasManager)
        manager.channel = STAGE
        manager.route = SimpleNamespace(allows=lambda minimum: True, mode=lambda: LevelMode.EDIT)
        manager._on_user_event = lambda: reported.append(True)
        manager._event_handlers = build_event_handler_map([_Source()])

        manager._handle_canvas_event(SelectionChangedEvent(selectedNodes=[], selectedEdges=[]))

        assert reported == [True]


class TestTheNewLevelFakeStillOpens:
    def test_a_level_over_a_graph_without_open_view_opens_the_patch(self):
        document = _FakeDocument()
        group = _FakeGraph("g")
        assert not hasattr(group.props, "open_view")
        editor, context, _ = _editor(document)
        level = editor._new_level(context, "sg", SimpleNamespace(editor=SimpleNamespace(graph=group)))  # type: ignore[arg-type]
        assert level.view == "patch"


class TestTheEmptyStageViewport:
    """A stage canvas with no nodes centres on the stage origin corner, not the patch's midpoint."""

    @staticmethod
    def _built(monkeypatch: Any, view: str, on_stage: int) -> Any:
        editor, context, _ = _editor()
        editor._project_state = MagicMock()
        manager = MagicMock()
        manager.visual_layer.included_node_count.return_value = on_stage
        monkeypatch.setattr(graph_editor_module, "GraphCanvasManager", MagicMock(return_value=manager))
        route = SimpleNamespace(graph=SimpleNamespace(node_wrappers={"n1": object()}))
        context.session_id = "session-1"
        GraphEditor._build_canvas(editor, context, route, view=view)  # type: ignore[arg-type]
        return manager.zoom_container

    def test_an_empty_stage_centres_on_the_origin_corner(self, monkeypatch):
        zoom = self._built(monkeypatch, "stage", on_stage=0)
        zoom._on_ready()
        zoom.center_on.assert_called_once_with(STAGE.origin + 400, STAGE.origin + 300)

    def test_a_stage_with_nodes_fits_its_content(self, monkeypatch):
        zoom = self._built(monkeypatch, "stage", on_stage=1)
        assert zoom._on_ready == zoom.center_on_content

    def test_an_empty_patch_still_centres_on_the_canvas_midpoint(self, monkeypatch):
        editor, context, _ = _editor()
        editor._project_state = MagicMock()
        manager = MagicMock()
        monkeypatch.setattr(graph_editor_module, "GraphCanvasManager", MagicMock(return_value=manager))
        route = SimpleNamespace(graph=SimpleNamespace(node_wrappers={}))
        context.session_id = "session-1"
        GraphEditor._build_canvas(editor, context, route)  # type: ignore[arg-type]
        manager.zoom_container._on_ready()
        manager.zoom_container.center_on.assert_called_once_with(3750, 3750)


class TestShowSessionSelection:
    """``show_session_selection`` prunes the session's selection to what the canvas draws."""

    @staticmethod
    def _manager(shown_nodes: set[str], shown_edges: set[str], edit: Any) -> Any:
        manager: Any = object.__new__(GraphCanvasManager)
        manager._session = MagicMock()
        manager._session.context.data = {EditState: edit}
        manager.visual_layer = MagicMock()
        manager.visual_layer.shows_node.side_effect = lambda n: n in shown_nodes
        manager.visual_layer.shows_edge.side_effect = lambda e: e in shown_edges
        manager.selection = SimpleNamespace(selected_nodes=set(), selected_edges=set())
        return manager

    @staticmethod
    def _edit(nodes: set[str], active: str | None) -> Any:
        return SimpleNamespace(
            selected_nodes=set(nodes),
            selected_edges=set(),
            active_node=SimpleNamespace(node_id=active, registry_key="k") if active else None,
            active_edge=None,
        )

    def test_the_selection_is_pruned_to_the_canvas_and_pushed(self):
        edit = self._edit({"a", "b"}, active="a")
        manager = self._manager({"a"}, set(), edit)

        manager.show_session_selection()

        assert edit.selected_nodes == {"a"}
        assert manager.selection.selected_nodes == {"a"}
        assert edit.active_node.node_id == "a"
        args = manager.visual_layer.sync_selections.call_args
        assert args.args[0] == {"a"}
        assert args.kwargs["active"] == {"kind": "node", "id": "a"}
        assert isinstance(manager._session.publish.call_args.args[0], SelectionMoved)

    def test_an_active_node_the_canvas_does_not_show_is_cleared(self):
        edit = self._edit({"a", "b"}, active="b")
        manager = self._manager({"a"}, set(), edit)
        manager._session.context.active_component = "k"

        manager.show_session_selection()

        assert edit.active_node is None
        assert manager._session.context.active_component is None
        assert manager.visual_layer.sync_selections.call_args.kwargs["active"] == {"kind": "", "id": ""}

    def test_patch_stage_patch_round_trip_keeps_only_what_both_show(self):
        edit = self._edit({"a", "b"}, active="a")
        stage = self._manager({"a"}, set(), edit)
        patch = self._manager({"a", "b"}, set(), edit)

        stage.show_session_selection()
        patch.show_session_selection()

        assert edit.selected_nodes == {"a"}
        assert patch.selection.selected_nodes == {"a"}

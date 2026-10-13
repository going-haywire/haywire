"""GraphEditor levels inside a macro placement: opened locked, never unlockable."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from haybale_graph_editor.editors import graph_editor as graph_editor_module
from haybale_graph_editor.editors.graph_editor import (
    DOCUMENT_LEVEL,
    GraphEditor,
    inside_placement,
    level_key_for,
)
from haybale_graph_editor.protocols import GraphContainer, SubgraphContainer
from haywire.core.access import AccessTier
from haywire.ui.components.zoom.pan import Viewport

from .test_graph_editor_levels import (
    _assert_selection_dropped,
    _claiming,
    _definition,
    _descend,
    _editor,
    _FakeDocument,
    _select,
    _stub,
)
from .test_graph_editor_lock import _locked_editor, _restore_resolver  # noqa: F401

pytestmark = pytest.mark.unit

_REFUSAL = "Inside a macro placement this level stays locked. Use Edit Macro… to change the macro."


def _container(host: GraphContainer, definition: Any) -> SubgraphContainer:
    """A SubgraphContainer over ``definition`` without building a real Editor."""
    container = SubgraphContainer.__new__(SubgraphContainer)
    container.host = host
    container.definition = definition
    container.editor = SimpleNamespace(graph=definition)  # type: ignore[assignment]
    return container


def _placement_definition(key: str = "sg_p") -> Any:
    definition = _definition(key)
    definition.template_key = "lib:macro:Blur"
    return definition


def _placement_level(tier: AccessTier = AccessTier.ADMIN):
    editor, context, document = _locked_editor(tier, open_locked=False)
    container = _container(document, _placement_definition())
    key = editor._open_level(context, container)
    return editor, context, key


def test_a_placement_interior_opens_locked():
    document = _FakeDocument()
    container = _container(document, _placement_definition())
    assert container.editor.graph.props.open_locked is False
    level = GraphEditor._new_level(level_key_for(container), container)
    assert level.locked is True
    assert level.inside_placement is True


def test_a_group_nested_in_a_placement_opens_locked():
    placement = _container(_FakeDocument(), _placement_definition())
    nested = _container(placement, _definition("sg_inner"))
    assert inside_placement(nested) is True
    level = GraphEditor._new_level(level_key_for(nested), nested)
    assert level.locked is True
    assert level.inside_placement is True


def test_a_plain_group_is_not_inside_a_placement():
    document = _FakeDocument()
    group = _container(document, _definition())
    assert inside_placement(document) is False
    assert inside_placement(group) is False
    level = GraphEditor._new_level(level_key_for(group), group)
    assert level.locked is False
    assert level.inside_placement is False


def test_unlock_is_refused_inside_a_placement_even_for_admin():
    editor, context, key = _placement_level(AccessTier.ADMIN)
    assert editor.set_level_locked(context, key, False) is False
    assert editor._levels[key].locked is True
    assert editor.set_level_locked(context, key, True) is True
    assert editor._levels[key].locked is True


def test_toggle_lock_inside_a_placement_notifies(monkeypatch):
    editor, context, key = _placement_level()
    editor._active_level = key
    ui = MagicMock()
    monkeypatch.setattr(graph_editor_module, "ui", ui)
    editor._on_toggle_lock(context, MagicMock())
    ui.notify.assert_called_once_with(_REFUSAL, type="warning")


def test_lock_button_disabled_inside_a_placement():
    editor, context, key = _placement_level(AccessTier.ADMIN)
    editor._active_level = key
    editor._lock_button = MagicMock()
    editor._lock_tooltip = MagicMock()
    editor._update_lock_button(context)
    editor._lock_button.set_enabled.assert_called_once_with(False)
    editor._lock_tooltip.set_text.assert_called_once_with("Locked: inside a macro placement")


def test_reveal_opens_a_placement_interior_locked():
    editor, context, document = _locked_editor(AccessTier.ADMIN, open_locked=False)
    interior = _placement_definition()
    document.editor.graph.subgraphs = {interior.key: interior}
    interior.subgraphs = {}
    level = editor._open_level_for_graph(context, interior.graph_id)
    assert level is not None
    assert level.locked is True
    assert level.inside_placement is True


_PLACEMENT_KEY = "macro_card_1"


def _open_placement(editor: GraphEditor, context: Any) -> None:
    """Enter a placement whose interior sits under ``_PLACEMENT_KEY``."""
    assert _descend(editor, context, _placement_definition(_PLACEMENT_KEY), node_id="card_1") is True


def _shown(editor: GraphEditor, key: str) -> SubgraphContainer:
    """The container the level under ``key`` shows."""
    container = editor._levels[key].container
    assert isinstance(container, SubgraphContainer)
    return container


class TestAReloadedPlacement:
    """A ``.hwm`` reload swaps the placement's interior for a new definition under the same key."""

    def test_an_open_placement_level_follows_a_reload(self):
        from haybale_graph_editor.state.edit_state import EditState

        editor, context, document = _editor()
        _open_placement(editor, context)
        old_level = editor._levels[_PLACEMENT_KEY]
        # The session is on the placement level, so the reload carries it along.
        context.data = {EditState: SimpleNamespace(active_graph=old_level.container.editor.graph)}
        editor._level_panels = MagicMock()
        _stub(editor._claim_session_state).reset_mock()

        reloaded = _placement_definition(_PLACEMENT_KEY)
        document.editor.graph.subgraphs[_PLACEMENT_KEY] = reloaded
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL, _PLACEMENT_KEY]
        assert editor._active_level == _PLACEMENT_KEY
        level = editor._levels[_PLACEMENT_KEY]
        assert _shown(editor, _PLACEMENT_KEY).definition is reloaded
        assert _shown(editor, _PLACEMENT_KEY).host is document
        assert level.locked is True
        assert level.inside_placement is True
        _stub(editor._teardown_level).assert_called_once_with(old_level)
        _stub(editor._mount_level).assert_called_once_with(context, level, viewport=None)
        _stub(editor._claim_session_state).assert_called()

    def test_the_new_canvas_keeps_the_old_viewport(self):
        """The user is looking at the interior when it reloads; the new canvas looks at the same spot."""
        editor, context, document = _editor()
        _open_placement(editor, context)
        viewport = Viewport(zoom=1.5, pan_x=-4000.0, pan_y=-3500.0)
        old_canvas = MagicMock()
        old_canvas.zoom_container.get_viewport.return_value = viewport
        editor._levels[_PLACEMENT_KEY].canvas_manager = old_canvas
        editor._level_panels = MagicMock()

        document.editor.graph.subgraphs[_PLACEMENT_KEY] = _placement_definition(_PLACEMENT_KEY)
        editor._prune_dead_levels(context)

        level = editor._levels[_PLACEMENT_KEY]
        _stub(editor._mount_level).assert_called_once_with(context, level, viewport=viewport)

    def test_a_reload_of_the_level_on_screen_drops_its_selection(self):
        """The selected node is in the replaced interior; nothing on screen holds it any more."""
        editor, context, document = _editor()
        _open_placement(editor, context)
        edit_state = _select(editor, context, MagicMock(name="old_interior_node"))

        document.editor.graph.subgraphs[_PLACEMENT_KEY] = _placement_definition(_PLACEMENT_KEY)
        editor._prune_dead_levels(context)

        assert editor._active_level == _PLACEMENT_KEY
        _assert_selection_dropped(context, edit_state)

    def test_an_interior_node_selected_on_the_placement_is_not_editable_from_the_document(self):
        """A placement's node is selectable at view; going up to the document must not make it editable."""
        from haybale_graph_editor.access import can_edit_graph

        editor, context, document = _locked_editor(AccessTier.EDIT, open_locked=False)
        _open_placement(editor, context)
        edit_state = _select(editor, context, MagicMock(name="interior_node"))

        editor.ascend(context)

        assert can_edit_graph(context) is True  # the document is unlocked ...
        assert edit_state.active_node is None  # ... and holds nothing from the placement

    def test_an_interior_node_selected_on_the_placement_is_not_editable_from_another_tab(self):
        """Focusing another, unlocked tab must not make the placement's node editable either."""
        from haybale_graph_editor.access import can_edit_graph
        from haybale_graph_editor.state.graph_app_state import GraphAppState

        editor, context, document = _locked_editor(AccessTier.EDIT, open_locked=False)
        _open_placement(editor, context)
        other_document = _FakeDocument("/tmp/graphs/other.haywire", graph_id="other_graph")
        other, _context, _ = _editor(other_document)
        _claiming(other)
        documents = {document.binding_id: document, other_document.binding_id: other_document}
        context.app_data[GraphAppState].get.side_effect = documents.get
        edit_state = _select(editor, context, MagicMock(name="interior_node"))

        other.on_focus(context)

        assert edit_state.active_graph is other_document.editor.graph
        assert can_edit_graph(context) is True  # the other tab is unlocked ...
        _assert_selection_dropped(context, edit_state)  # ... and holds nothing from the placement

    def test_a_level_in_the_background_follows_without_coming_forward(self):
        editor, context, document = _editor()
        _open_placement(editor, context)
        editor.ascend(context)

        reloaded = _placement_definition(_PLACEMENT_KEY)
        document.editor.graph.subgraphs[_PLACEMENT_KEY] = reloaded
        editor._prune_dead_levels(context)

        assert editor._active_level == DOCUMENT_LEVEL
        assert _shown(editor, _PLACEMENT_KEY).definition is reloaded

    def test_a_removed_placement_closes_its_level(self):
        editor, context, document = _editor()
        _open_placement(editor, context)

        del document.editor.graph.subgraphs[_PLACEMENT_KEY]
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL]
        assert editor._active_level == DOCUMENT_LEVEL

    def test_a_reloaded_interior_without_its_card_closes_its_level(self):
        editor, context, document = _editor()
        _open_placement(editor, context)

        reloaded = _placement_definition(_PLACEMENT_KEY)
        reloaded.graph_node_wrapper = lambda: None
        document.editor.graph.subgraphs[_PLACEMENT_KEY] = reloaded
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL]

    def test_a_group_nested_in_the_placement_follows_when_its_key_survives(self):
        editor, context, document = _editor()
        _open_placement(editor, context)
        _descend(editor, context, _definition("sg_inner"))
        nested_key = f"{_PLACEMENT_KEY}#sg_inner"

        reloaded = _placement_definition(_PLACEMENT_KEY)
        reloaded_inner = _definition("sg_inner")
        reloaded.subgraphs["sg_inner"] = reloaded_inner
        document.editor.graph.subgraphs[_PLACEMENT_KEY] = reloaded
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL, _PLACEMENT_KEY, nested_key]
        assert editor._active_level == nested_key
        nested = editor._levels[nested_key]
        assert _shown(editor, nested_key).definition is reloaded_inner
        assert _shown(editor, nested_key).host is _shown(editor, _PLACEMENT_KEY)
        assert nested.locked is True
        assert nested.inside_placement is True

    def test_a_group_nested_in_the_placement_closes_when_its_key_is_gone(self):
        """A reload mints fresh keys for the template's own Groups, so this is the usual outcome."""
        editor, context, document = _editor()
        _open_placement(editor, context)
        _descend(editor, context, _definition("sg_inner"))

        reloaded = _placement_definition(_PLACEMENT_KEY)
        document.editor.graph.subgraphs[_PLACEMENT_KEY] = reloaded
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL, _PLACEMENT_KEY]
        assert editor._active_level == _PLACEMENT_KEY
        assert _shown(editor, _PLACEMENT_KEY).definition is reloaded

    def test_a_plain_group_replaced_under_its_key_still_closes(self):
        """Only a placement's interior is replaced in place; a new Group definition is another Group."""
        editor, context, document = _editor()
        _descend(editor, context, _definition("sg_a"))

        document.editor.graph.subgraphs["sg_a"] = _definition("sg_a")
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL]


def _detach(document: _FakeDocument, definition: Any, key: str) -> None:
    """Move ``definition`` to ``key`` in the host's table and make it a plain Group, as the detach does."""
    subgraphs = document.editor.graph.subgraphs
    subgraphs.pop(definition.key)
    definition.key = key
    definition.template_key = None
    subgraphs[key] = definition


class TestADetachedPlacement:
    """Detaching moves the interior's definition to a new key; the open level follows it there."""

    def test_a_detached_placement_level_follows_the_new_key(self):
        from haybale_graph_editor.state.edit_state import EditState

        editor, context, document = _editor()
        _open_placement(editor, context)
        level = editor._levels[_PLACEMENT_KEY]
        manager = level.canvas_manager = MagicMock()
        context.data = {EditState: SimpleNamespace(active_graph=level.container.editor.graph)}
        editor._level_panels = MagicMock()

        _detach(document, _shown(editor, _PLACEMENT_KEY).definition, "subgraph_new")
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL, "subgraph_new"]
        assert editor._active_level == "subgraph_new"
        moved = editor._levels["subgraph_new"]
        assert moved is level
        assert moved.key == "subgraph_new"
        assert moved.canvas_manager is manager
        _stub(editor._teardown_level).assert_not_called()
        _stub(editor._mount_level).assert_not_called()
        assert moved.inside_placement is False
        assert moved.locked is True
        _stub(editor._claim_session_state).assert_called()

    def test_the_mounted_panel_is_renamed_with_its_level(self):
        editor, context, document = _editor()
        _open_placement(editor, context)
        level = editor._levels[_PLACEMENT_KEY]
        level.panel = MagicMock()
        level.panel._props = {"name": _PLACEMENT_KEY}
        editor._level_panels = MagicMock()

        _detach(document, _shown(editor, _PLACEMENT_KEY).definition, "subgraph_new")
        editor._prune_dead_levels(context)

        assert level.panel._props["name"] == "subgraph_new"
        level.panel.update.assert_called_once_with()
        editor._level_panels.set_value.assert_called_with("subgraph_new")

    def test_undo_of_the_detach_follows_back_and_locks(self):
        editor, context, document = _editor()
        _open_placement(editor, context)
        definition = _shown(editor, _PLACEMENT_KEY).definition
        _detach(document, definition, "subgraph_new")
        editor._prune_dead_levels(context)

        _detach(document, definition, _PLACEMENT_KEY)
        definition.template_key = "lib:macro:Blur"
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL, _PLACEMENT_KEY]
        assert editor._active_level == _PLACEMENT_KEY
        level = editor._levels[_PLACEMENT_KEY]
        assert level.locked is True
        assert level.inside_placement is True
        _stub(editor._teardown_level).assert_not_called()

    def test_descendant_levels_follow_the_re_key(self):
        editor, context, document = _editor()
        _open_placement(editor, context)
        _descend(editor, context, _definition("sg_inner"))
        inner = editor._levels[f"{_PLACEMENT_KEY}#sg_inner"]
        assert inner.inside_placement is True

        _detach(document, _shown(editor, _PLACEMENT_KEY).definition, "subgraph_new")
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL, "subgraph_new", "subgraph_new#sg_inner"]
        assert editor._active_level == "subgraph_new#sg_inner"
        assert editor._levels["subgraph_new#sg_inner"] is inner
        assert inner.key == "subgraph_new#sg_inner"
        assert inner.inside_placement is False
        _stub(editor._teardown_level).assert_not_called()

    def test_a_background_editor_follows_without_claiming(self):
        editor, context, document = _editor()
        _open_placement(editor, context)
        _detach(document, _shown(editor, _PLACEMENT_KEY).definition, "subgraph_new")
        _stub(editor._claim_session_state).reset_mock()

        editor._rekey_level(context, editor._levels[_PLACEMENT_KEY], claim=False)

        assert editor._active_level == "subgraph_new"
        _stub(editor._claim_session_state).assert_not_called()

    def test_a_re_keyed_level_whose_card_is_gone_closes(self):
        editor, context, document = _editor()
        _open_placement(editor, context)
        definition = _shown(editor, _PLACEMENT_KEY).definition
        _detach(document, definition, "subgraph_new")
        definition.graph_node_wrapper = lambda: None  # type: ignore[method-assign]
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL]


def _built_canvas(monkeypatch, viewport: Viewport | None) -> MagicMock:
    """Build a canvas over a one-node graph through the real ``_build_canvas``; return its manager."""
    editor, context, _ = _editor()
    editor._project_state = MagicMock()
    manager = MagicMock()
    monkeypatch.setattr(graph_editor_module, "GraphCanvasManager", MagicMock(return_value=manager))
    entry = SimpleNamespace(editor=SimpleNamespace(graph=SimpleNamespace(node_wrappers={"n1": object()})))
    context.session_id = "session-1"
    GraphEditor._build_canvas(editor, context, entry, viewport=viewport)  # type: ignore[arg-type]
    return manager


def test_a_canvas_built_with_a_viewport_restores_it_instead_of_fitting(monkeypatch):
    zoom = _built_canvas(monkeypatch, Viewport(zoom=1.5, pan_x=-4000.0, pan_y=-3500.0)).zoom_container
    zoom._on_ready()
    assert zoom.mock_calls == [
        call.set_zoom(1.5),
        call.set_pan(-4000.0, -3500.0),
    ]


def test_a_canvas_built_without_a_viewport_fits_its_content(monkeypatch):
    zoom = _built_canvas(monkeypatch, None).zoom_container
    assert zoom._on_ready == zoom.center_on_content

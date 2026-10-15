"""Edit Instance on a real placement: confirming detaches it and the open level follows."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL, GraphEditor
from haywire.core.graph.editor import Editor
from haywire.core.signals import SubgraphNavigation
from tests.core.test_macro.test_detach_placement import _place

from .test_graph_editor_levels import _editor, _FakeDocument, _stub
from .test_graph_editor_placement_levels import _patched_ui

pytestmark = pytest.mark.integration


def _open_real_placement(graph, library_system) -> tuple[Editor, Any, GraphEditor, Any, str]:
    real_editor, placement_id = _place(graph, library_system)
    document = _FakeDocument()
    document.editor = real_editor
    editor, context, _ = _editor(document)
    editor._project_state = SimpleNamespace(node_factory=library_system.get_node_factory())  # type: ignore[assignment]
    assert editor.descend_into(context, placement_id) is True
    return real_editor, document, editor, context, placement_id


@pytest.mark.usefixtures("macro_folder")
def test_confirming_edits_the_instance(graph_with_library_system, library_system, monkeypatch):
    graph = graph_with_library_system
    _, _, editor, context, _ = _open_real_placement(graph, library_system)
    key = editor._active_level
    level = editor._levels[key]
    assert level.locked is True
    assert level.inside_placement is True
    definition = graph.subgraphs[key]
    ui, confirm = _patched_ui(monkeypatch)

    editor._on_toggle_lock(context, MagicMock())
    assert definition.origin is None  # nothing detached before the confirm
    confirm.call_args.kwargs["on_confirm"]()

    assert definition.origin is not None
    assert definition.template_key is None
    assert editor._active_level != key
    assert editor._active_level == definition.key
    assert key not in graph.subgraphs
    moved = editor._levels[editor._active_level]
    assert moved is level
    assert moved.locked is False
    assert moved.inside_placement is False
    assert list(editor._levels) == [DOCUMENT_LEVEL, definition.key]


@pytest.mark.usefixtures("macro_folder")
def test_the_menu_route_re_keys_an_open_level_instead_of_opening_a_second(
    graph_with_library_system, library_system, caplog
):
    """Detach straight from the menu while the interior is open but not on screen."""
    graph = graph_with_library_system
    real_editor, _, editor, context, placement_id = _open_real_placement(graph, library_system)
    old_key = editor._active_level
    level = editor._levels[old_key]
    manager = level.canvases["patch"] = MagicMock()
    editor._switch_level(context, DOCUMENT_LEVEL)
    _stub(editor._teardown_level).reset_mock()

    card_cls = library_system.get_node_factory().get_graph_node()
    new_card_id, refusal = real_editor.detach_placement_from_macro(
        placement_id, card_cls.class_identity.registry_key
    )
    assert new_card_id is not None, refusal
    with caplog.at_level(logging.WARNING):
        editor._on_subgraph_navigation(
            context, SubgraphNavigation(graph_id=graph.graph_id, node_id=new_card_id)
        )
        editor._prune_dead_levels(context)  # the mutation signal that follows in the app

    new_key = next(k for k in graph.subgraphs if k != old_key)
    assert list(editor._levels) == [DOCUMENT_LEVEL, new_key]
    assert editor._levels[new_key] is level
    assert level.canvas_manager is manager
    assert editor._active_level == new_key
    _stub(editor._teardown_level).assert_not_called()
    assert not [
        r
        for r in caplog.records
        if r.name.startswith("haybale_graph_editor") and r.levelno >= logging.WARNING
    ]


def _menu_detach(graph, library_system):
    real_editor, _, editor, context, placement_id = _open_real_placement(graph, library_system)
    editor._switch_level(context, DOCUMENT_LEVEL)
    card_cls = library_system.get_node_factory().get_graph_node()
    new_card_id, refusal = real_editor.detach_placement_from_macro(
        placement_id, card_cls.class_identity.registry_key
    )
    assert new_card_id is not None, refusal
    return editor, context, new_card_id


@pytest.mark.usefixtures("macro_folder")
def test_the_menu_route_unlocks_a_level_that_was_already_open(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor, context, card_id = _menu_detach(graph, library_system)
    editor._on_subgraph_navigation(
        context, SubgraphNavigation(graph_id=graph.graph_id, node_id=card_id, unlocked=True)
    )

    level = editor._levels[editor._active_level]
    assert editor._active_level != DOCUMENT_LEVEL
    assert level.locked is False


@pytest.mark.usefixtures("macro_folder")
def test_the_menu_route_without_the_request_leaves_the_level_locked(
    graph_with_library_system, library_system
):
    graph = graph_with_library_system
    editor, context, card_id = _menu_detach(graph, library_system)
    editor._on_subgraph_navigation(context, SubgraphNavigation(graph_id=graph.graph_id, node_id=card_id))

    assert editor._levels[editor._active_level].locked is True


@pytest.mark.usefixtures("macro_folder")
def test_the_menu_route_unlocks_a_freshly_opened_level(
    graph_with_library_system, library_system, monkeypatch
):
    graph = graph_with_library_system
    real_editor, placement_id = _place(graph, library_system)
    document = _FakeDocument()
    document.editor = real_editor
    editor, context, _ = _editor(document)
    editor._project_state = SimpleNamespace(node_factory=library_system.get_node_factory())  # type: ignore[assignment]
    new_level = GraphEditor._new_level

    def _locked_level(key, container):
        level = new_level(key, container)
        level.locked = True
        return level

    monkeypatch.setattr(GraphEditor, "_new_level", staticmethod(_locked_level))
    card_cls = library_system.get_node_factory().get_graph_node()
    card_id, refusal = real_editor.detach_placement_from_macro(
        placement_id, card_cls.class_identity.registry_key
    )
    assert card_id is not None, refusal

    editor._on_subgraph_navigation(
        context, SubgraphNavigation(graph_id=graph.graph_id, node_id=card_id, unlocked=True)
    )

    assert editor._active_level != DOCUMENT_LEVEL
    assert editor._levels[editor._active_level].locked is False

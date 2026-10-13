"""GraphEditor levels inside a macro placement: opened locked, never unlockable."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors import graph_editor as graph_editor_module
from haybale_graph_editor.editors.graph_editor import GraphEditor, inside_placement, level_key_for
from haybale_graph_editor.protocols import GraphContainer, SubgraphContainer
from haywire.core.access import AccessTier

from .test_graph_editor_levels import _definition, _FakeDocument
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

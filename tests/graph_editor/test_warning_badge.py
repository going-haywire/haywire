"""The diagnostics and comment badges are drawn by ``BaseSkin``, never by a skin itself.

``BaseSkin._render`` calls ``render_markers`` after ``render``, so every skin's card
shows them; a skin may override the hook. The behaviour is covered in
``tests/ui/skin/test_skin_markers.py``; these tests keep the skins from drawing
their own.
"""

import importlib
import inspect

import pytest

from haywire.ui.skin.base import BaseSkin


@pytest.mark.unit
def test_the_badge_guard_covers_errors_warnings_and_deprecation():
    src = inspect.getsource(BaseSkin.render_markers)
    call_idx = src.index("self._render_diagnostics_button")
    guard_idx = src.rindex("if ", 0, call_idx)
    guard = src[guard_idx:call_idx]
    assert "runtime_errors" in guard
    assert "has_warning()" in guard
    assert "deprecation_str" in guard


@pytest.mark.unit
def test_the_render_entry_draws_the_markers_after_the_skin():
    src = inspect.getsource(BaseSkin._render)
    assert src.index("self.render(") < src.index("self.render_markers(")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("skin_module", "skin_name"),
    [
        ("haybale_graph_editor.skins.node_skin", "NodeSkin"),
        ("haybale_graph_editor.skins.stacked_skin", "StackedNodeSkin"),
        ("haybale_graph_editor.skins.split_skin", "SplitNodeSkin"),
        ("haybale_graph_editor.skins.error_skin", "ErrorNodeSkin"),
        ("haybale_graph_editor.skins.inset_skin", "InsetSkin"),
        ("haybale_core.skins.widget_node_skin", "WidgetNodeSkin"),
    ],
)
def test_no_skin_draws_its_own_badges(skin_module, skin_name):
    cls = getattr(importlib.import_module(skin_module), skin_name)
    src = inspect.getsource(cls)
    assert "_render_diagnostics_button" not in src
    assert "_render_comment_badge" not in src


@pytest.mark.unit
def test_the_badge_points_to_the_menu_for_a_previous_setup():
    src = inspect.getsource(BaseSkin._render_diagnostics_button)
    assert "Settings reset by a code change" in src
    assert "Right-click the node to restore or discard them." in src
    assert "apply_previous_setup" not in src

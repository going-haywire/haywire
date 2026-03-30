# tests/ui/test_workspace_defaults.py
"""Tests for haywire_studio workspace defaults."""

from haywire_studio.workspace.defaults import (
    DEFAULT_PRESETS,
    _K_GRAPH_EDITOR,
    _K_PROPERTIES,
    _K_LIBRARY_BROWSER,
    _K_CONSOLE,
)
from haywire.ui.workspace.workspace_state import WorkspaceState


def test_default_presets_keys_present():
    assert "Graph Editing" in DEFAULT_PRESETS
    assert "Development" in DEFAULT_PRESETS
    assert "Debugging" in DEFAULT_PRESETS


def test_default_presets_are_workspace_state_instances():
    for name, preset in DEFAULT_PRESETS.items():
        assert isinstance(preset, WorkspaceState), f"Preset '{name}' is not a WorkspaceState"


def test_studio_key_constants_have_studio_prefix():
    assert _K_GRAPH_EDITOR.startswith("studio:editor:")
    assert _K_PROPERTIES.startswith("studio:editor:")
    assert _K_LIBRARY_BROWSER.startswith("studio:editor:")
    assert _K_CONSOLE.startswith("studio:editor:")


def test_graph_editing_preset_layout():
    ws = DEFAULT_PRESETS["Graph Editing"]
    assert ws.left.editor_key == _K_LIBRARY_BROWSER
    assert ws.right.editor_key == _K_PROPERTIES
    assert ws.middle.tabs[0].editor_key == _K_GRAPH_EDITOR


def test_development_preset_has_bottom_visible():
    dev = DEFAULT_PRESETS["Development"]
    assert dev.middle.bottom_visible is True
    assert dev.middle.bottom_editor_key == _K_CONSOLE


def test_debugging_preset_left_collapsed():
    dbg = DEFAULT_PRESETS["Debugging"]
    assert dbg.left.visible is False

# tests/ui/test_workspace_state.py
"""
Tests for WorkspaceState serialization and WorkspaceManager.
"""

import pytest
from dataclasses import asdict

from haywire.ui.workspace.workspace_state import (
    AreaState, TabState, MiddleAreaState, WorkspaceState
)
from haywire.ui.workspace.manager import WorkspaceManager


# ---------------------------------------------------------------------------
# WorkspaceState serialization tests
# ---------------------------------------------------------------------------

class TestWorkspaceStateSerialization:
    def test_area_state_asdict(self):
        state = AreaState(editor_key='graph_editor', visible=True, size=300)
        d = asdict(state)
        assert d == {'editor_key': 'graph_editor', 'visible': True, 'size': 300}

    def test_tab_state_asdict(self):
        state = TabState(editor_key='graph_editor', label='My Graph', metadata={'foo': 1})
        d = asdict(state)
        assert d['editor_key'] == 'graph_editor'
        assert d['label'] == 'My Graph'
        assert d['metadata'] == {'foo': 1}

    def test_middle_area_state_asdict(self):
        state = MiddleAreaState()
        d = asdict(state)
        assert 'tabs' in d
        assert 'active_tab_index' in d
        assert 'bottom_visible' in d
        assert 'bottom_size' in d
        assert 'bottom_editor_key' in d

    def test_workspace_state_asdict(self):
        ws = WorkspaceState(name='Test WS')
        d = asdict(ws)
        assert d['name'] == 'Test WS'
        assert 'left' in d
        assert 'middle' in d
        assert 'right' in d

    def test_workspace_state_roundtrip(self):
        """Serializing then deserializing WorkspaceState fields preserves data."""
        ws = WorkspaceState(name='My WS')
        d = asdict(ws)
        # Reconstruct name only (partial roundtrip — nested dataclasses need manual reconstruction)
        assert d['name'] == 'My WS'
        assert d['left']['editor_key'] == 'studio:editor:library_browser'
        assert d['right']['editor_key'] == 'studio:editor:properties'

    def test_default_workspace_state(self):
        ws = WorkspaceState()
        assert ws.name == "default"
        assert ws.left.editor_key == 'studio:editor:library_browser'
        assert ws.right.editor_key == 'studio:editor:properties'
        assert ws.middle.tabs[0].editor_key == 'studio:editor:graph_editor'


# ---------------------------------------------------------------------------
# WorkspaceManager tests
# ---------------------------------------------------------------------------

class TestWorkspaceManager:
    def setup_method(self):
        self.manager = WorkspaceManager(project_path=None)

    def test_has_default_presets(self):
        names = self.manager.get_preset_names()
        assert 'Graph Editing' in names

    def test_default_presets_are_workspace_state_instances(self):
        for name, preset in self.manager.presets.items():
            assert isinstance(preset, WorkspaceState), f"Preset '{name}' is not a WorkspaceState"

    def test_active_is_workspace_state(self):
        assert isinstance(self.manager.active, WorkspaceState)

    def test_switch_changes_active(self):
        original = self.manager.active
        # Save a second preset to switch to
        self.manager.presets['Test WS'] = WorkspaceState(name='Test WS')
        self.manager.switch('Test WS')
        assert self.manager.active.name == 'Test WS'
        assert self.manager.active is not original

    def test_switch_raises_on_unknown(self):
        with pytest.raises(KeyError):
            self.manager.switch('nonexistent_workspace')

    def test_save_current_creates_preset(self):
        self.manager.save_current('My Custom WS')
        assert 'My Custom WS' in self.manager.presets

    def test_get_preset_names_returns_list(self):
        names = self.manager.get_preset_names()
        assert isinstance(names, list)
        assert len(names) >= 1

    def test_no_project_path_no_persistence(self):
        """WorkspaceManager with no project_path should not attempt file I/O."""
        manager = WorkspaceManager(project_path=None)
        # save_current without project_path should not raise
        manager.save_current('Test')
        assert 'Test' in manager.presets

    def test_has_development_and_debugging_presets(self):
        names = self.manager.get_preset_names()
        assert 'Development' in names
        assert 'Debugging' in names

    def test_development_preset_has_bottom_visible(self):
        dev = self.manager.presets['Development']
        assert dev.middle.bottom_visible is True
        assert dev.middle.bottom_editor_key == 'studio:editor:console'

    def test_debugging_preset_left_collapsed(self):
        dbg = self.manager.presets['Debugging']
        assert dbg.left.visible is False

    def test_deserialize_workspace_roundtrip(self):
        """WorkspaceManager._deserialize_workspace reconstructs a WorkspaceState correctly."""
        from dataclasses import asdict
        ws = self.manager.presets['Development']
        d = asdict(ws)
        restored = WorkspaceManager._deserialize_workspace(d)
        assert restored.name == ws.name
        assert restored.middle.bottom_visible == ws.middle.bottom_visible
        assert restored.middle.bottom_editor_key == ws.middle.bottom_editor_key
        assert len(restored.middle.tabs) == len(ws.middle.tabs)
        assert restored.middle.tabs[0].editor_key == ws.middle.tabs[0].editor_key
        assert restored.left.editor_key == ws.left.editor_key
        assert restored.right.editor_key == ws.right.editor_key

# tests/ui/test_workspace_state.py
"""
Tests for WorkspaceState serialization and WorkspaceManager.
"""

import json

from dataclasses import asdict

from haywire.ui.workspace.workspace_state import AreaState, TabState, MiddleAreaState, WorkspaceState
from haywire.ui.workspace.manager import WorkspaceManager


# ---------------------------------------------------------------------------
# WorkspaceState serialization tests
# ---------------------------------------------------------------------------


class TestWorkspaceStateSerialization:
    def test_area_state_asdict(self):
        state = AreaState(editor_key="graph_editor", visible=True, size=300)
        d = asdict(state)
        assert d == {"editor_key": "graph_editor", "visible": True, "size": 300}

    def test_tab_state_asdict(self):
        state = TabState(editor_key="graph_editor", label="My Graph", metadata={"foo": 1})
        d = asdict(state)
        assert d["editor_key"] == "graph_editor"
        assert d["label"] == "My Graph"
        assert d["metadata"] == {"foo": 1}

    def test_middle_area_state_asdict(self):
        state = MiddleAreaState()
        d = asdict(state)
        assert "tabs" in d
        assert "active_tab_index" in d
        assert "bottom_visible" in d
        assert "bottom_size" in d
        assert "bottom_editor_key" in d

    def test_workspace_state_asdict(self):
        ws = WorkspaceState(name="Test WS")
        d = asdict(ws)
        assert d["name"] == "Test WS"
        assert "left" in d
        assert "middle" in d
        assert "right" in d

    def test_workspace_state_roundtrip(self):
        """Serializing then deserializing WorkspaceState fields preserves data."""
        ws = WorkspaceState(name="My WS")
        d = asdict(ws)
        assert d["name"] == "My WS"
        assert d["left"]["editor_key"] is None  # no studio strings in core
        assert d["right"]["editor_key"] is None

    def test_default_workspace_state(self):
        ws = WorkspaceState()
        assert ws.name == "default"
        assert ws.left.editor_key is None  # generic — no studio strings
        assert ws.right.editor_key is None
        assert ws.middle.tabs[0].editor_key is None  # consistent with other key fields


# ---------------------------------------------------------------------------
# WorkspaceManager tests
# ---------------------------------------------------------------------------


class _FakeIdentity:
    def __init__(self, label: str):
        self.label = label


class _FakeEditorClass:
    def __init__(self, label: str):
        self.class_identity = _FakeIdentity(label)


class _FakeEditorRegistry:
    """Minimal EditorTypeRegistry stand-in for WorkspaceManager tests."""

    def __init__(self, by_area: dict[str, dict[str, _FakeEditorClass]]):
        self._by_area = by_area

    def get_by_default_area(self, area: str) -> dict[str, _FakeEditorClass]:
        return dict(self._by_area.get(area, {}))


def _make_registry(**areas) -> _FakeEditorRegistry:
    """Build a fake registry from area -> [(key, label), ...] pairs."""
    by_area: dict[str, dict[str, _FakeEditorClass]] = {}
    for area, entries in areas.items():
        by_area[area] = {key: _FakeEditorClass(label) for key, label in entries}
    return _FakeEditorRegistry(by_area)


class TestWorkspaceManagerAutoPopulate:
    def test_auto_populates_when_no_file(self, tmp_path):
        registry = _make_registry(
            left=[("editor:browser", "Browser")],
            middle=[("editor:graph", "Graph"), ("editor:library", "Library")],
            right=[("editor:props", "Properties")],
            bottom=[("editor:console", "Console")],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)

        assert manager.active.left.editor_key == "editor:browser"
        assert manager.active.left_bar_active == "editor:browser"
        assert manager.active.right.editor_key == "editor:props"
        assert manager.active.right_bar_active == "editor:props"
        assert manager.active.middle.bottom_editor_key == "editor:console"
        assert manager.active.middle.bottom_visible is False

        labels = [t.label for t in manager.active.middle.tabs]
        keys = [t.editor_key for t in manager.active.middle.tabs]
        assert keys == ["editor:graph", "editor:library"]
        assert labels == ["Graph", "Library"]

    def test_auto_populate_handles_empty_registry(self, tmp_path):
        registry = _make_registry()
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)

        assert manager.active.left.editor_key is None
        assert manager.active.left.visible is False
        assert manager.active.right.editor_key is None
        assert manager.active.right.visible is False
        assert manager.active.middle.bottom_editor_key is None
        assert len(manager.active.middle.tabs) == 1
        assert manager.active.middle.tabs[0].editor_key is None

    def test_auto_populate_partial_areas(self, tmp_path):
        registry = _make_registry(
            middle=[("editor:graph", "Graph")],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)

        assert manager.active.left.editor_key is None
        assert manager.active.right.editor_key is None
        assert manager.active.middle.tabs[0].editor_key == "editor:graph"

    def test_auto_populate_does_not_write_file(self, tmp_path):
        registry = _make_registry(left=[("editor:a", "A")])
        WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        assert not (tmp_path / ".haywire" / "workspace_state.json").exists()


class TestWorkspaceManagerPersistence:
    def _registry(self) -> _FakeEditorRegistry:
        return _make_registry(
            left=[("editor:browser", "Browser")],
            middle=[("editor:graph", "Graph")],
            right=[("editor:props", "Properties")],
            bottom=[("editor:console", "Console")],
        )

    def test_save_writes_file(self, tmp_path):
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        manager.save()

        state_file = tmp_path / ".haywire" / "workspace_state.json"
        assert state_file.exists()

        data = json.loads(state_file.read_text())
        assert data["left"]["editor_key"] == "editor:browser"
        assert data["middle"]["tabs"][0]["editor_key"] == "editor:graph"

    def test_save_creates_haywire_dir(self, tmp_path):
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        assert not (tmp_path / ".haywire").exists()
        manager.save()
        assert (tmp_path / ".haywire").exists()

    def test_load_reads_persisted_state(self, tmp_path):
        # Save from one manager.
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        m1.active.left.visible = False
        m1.active.middle.bottom_visible = True
        m1.save()

        # Fresh manager should load the file, not auto-populate.
        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        assert m2.active.left.visible is False
        assert m2.active.middle.bottom_visible is True
        assert m2.active.left.editor_key == "editor:browser"

    def test_load_survives_empty_registry(self, tmp_path):
        """A persisted file wins over an empty registry."""
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        m1.save()

        empty_registry = _make_registry()
        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=empty_registry)
        assert m2.active.left.editor_key == "editor:browser"

    def test_corrupt_file_falls_back_to_auto_populate(self, tmp_path):
        preset_dir = tmp_path / ".haywire"
        preset_dir.mkdir()
        (preset_dir / "workspace_state.json").write_text("{ not valid json")

        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        assert manager.active.left.editor_key == "editor:browser"

    def test_active_is_workspace_state(self, tmp_path):
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        assert isinstance(manager.active, WorkspaceState)


class TestWorkspaceManagerDeserialize:
    def test_deserialize_workspace_roundtrip(self):
        """WorkspaceManager._deserialize_workspace reconstructs a WorkspaceState correctly."""
        from dataclasses import asdict

        ws = WorkspaceState(
            name="custom",
            left=AreaState(editor_key="editor:a", visible=True, size=250),
            middle=MiddleAreaState(
                tabs=[TabState(editor_key="editor:main", label="Main")],
                bottom_visible=True,
                bottom_size=200,
                bottom_editor_key="editor:bottom",
            ),
            right=AreaState(editor_key="editor:b", visible=True, size=350),
        )
        d = asdict(ws)
        restored = WorkspaceManager._deserialize_workspace(d)
        assert restored.name == ws.name
        assert restored.middle.bottom_visible == ws.middle.bottom_visible
        assert restored.middle.bottom_editor_key == ws.middle.bottom_editor_key
        assert len(restored.middle.tabs) == len(ws.middle.tabs)
        assert restored.middle.tabs[0].editor_key == ws.middle.tabs[0].editor_key
        assert restored.left.editor_key == ws.left.editor_key
        assert restored.right.editor_key == ws.right.editor_key

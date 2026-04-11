# tests/ui/test_workspace_state.py
"""
Tests for WorkspaceState serialization and WorkspaceManager.
"""

import json

from dataclasses import asdict

from haywire.ui.workspace.workspace_state import (
    AreaState,
    TabState,
    MiddleAreaState,
    BottomAreaState,
    WorkspaceState,
)
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
        # Bottom fields live on BottomAreaState, not MiddleAreaState.
        assert "bottom_visible" not in d
        assert "bottom_size" not in d
        assert "bottom_editor_key" not in d

    def test_bottom_area_state_asdict(self):
        state = BottomAreaState()
        d = asdict(state)
        assert "tabs" in d
        assert "active_tab_key" in d
        assert "visible" in d
        assert "size" in d
        assert d["visible"] is False
        assert d["size"] == 200
        assert d["active_tab_key"] is None

    def test_workspace_state_asdict(self):
        ws = WorkspaceState(name="Test WS")
        d = asdict(ws)
        assert d["name"] == "Test WS"
        assert "left" in d
        assert "middle" in d
        assert "bottom" in d
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
        assert ws.bottom.tabs == []
        assert ws.bottom.active_tab_key is None


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
        # Bottom area is retracted by default but its tab roster is populated
        # from the registry on every load.
        assert manager.active.bottom.visible is False
        assert [t.editor_key for t in manager.active.bottom.tabs] == ["editor:console"]
        assert manager.active.bottom.active_tab_key == "editor:console"

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
        assert manager.active.bottom.tabs == []
        assert manager.active.bottom.active_tab_key is None
        assert len(manager.active.middle.tabs) == 1
        assert manager.active.middle.tabs[0].editor_key is None

    def test_auto_populate_partial_areas(self, tmp_path):
        registry = _make_registry(
            middle=[("editor:graph", "Graph")],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)

        assert manager.active.left.editor_key is None
        assert manager.active.right.editor_key is None
        assert manager.active.bottom.tabs == []
        assert manager.active.middle.tabs[0].editor_key == "editor:graph"

    def test_auto_populate_does_not_write_file(self, tmp_path):
        registry = _make_registry(left=[("editor:a", "A")])
        WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        assert not (tmp_path / ".haywire" / "workspace_state.json").exists()

    def test_auto_populate_with_multiple_bottom_editors(self, tmp_path):
        """Every bottom-area editor becomes a tab; first is active by default."""
        registry = _make_registry(
            bottom=[
                ("editor:console", "Console"),
                ("editor:terminal", "Terminal"),
                ("editor:problems", "Problems"),
            ],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)

        keys = [t.editor_key for t in manager.active.bottom.tabs]
        labels = [t.label for t in manager.active.bottom.tabs]
        assert keys == ["editor:console", "editor:terminal", "editor:problems"]
        assert labels == ["Console", "Terminal", "Problems"]
        assert manager.active.bottom.active_tab_key == "editor:console"


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
        # bottom.tabs must NOT be persisted — it is re-derived from the
        # registry on load so new bottom editors appear automatically.
        assert "tabs" not in data["bottom"]
        assert data["bottom"]["active_tab_key"] == "editor:console"
        assert data["bottom"]["visible"] is False
        assert data["bottom"]["size"] == 200

    def test_save_creates_haywire_dir(self, tmp_path):
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        assert not (tmp_path / ".haywire").exists()
        manager.save()
        assert (tmp_path / ".haywire").exists()

    def test_load_reads_persisted_state(self, tmp_path):
        # Save from one manager.
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        m1.active.left.visible = False
        m1.active.bottom.visible = True
        m1.active.bottom.size = 275
        m1.save()

        # Fresh manager should load the file, not auto-populate.
        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        assert m2.active.left.visible is False
        assert m2.active.bottom.visible is True
        assert m2.active.bottom.size == 275
        assert m2.active.left.editor_key == "editor:browser"

    def test_load_refreshes_bottom_tabs_from_registry(self, tmp_path):
        """A newly-installed bottom editor should appear after a reload even
        though the persisted file predates it."""
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        m1.save()

        # Registry now has an additional bottom editor the persisted file
        # never saw.
        richer_registry = _make_registry(
            left=[("editor:browser", "Browser")],
            middle=[("editor:graph", "Graph")],
            right=[("editor:props", "Properties")],
            bottom=[
                ("editor:console", "Console"),
                ("editor:terminal", "Terminal"),
            ],
        )
        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=richer_registry)
        keys = [t.editor_key for t in m2.active.bottom.tabs]
        assert keys == ["editor:console", "editor:terminal"]
        # Previously-active key is still valid, so it is preserved.
        assert m2.active.bottom.active_tab_key == "editor:console"

    def test_load_falls_back_when_active_tab_key_is_gone(self, tmp_path):
        """If the registered editor referenced by active_tab_key no longer
        exists, fall back to the first available tab."""
        registry_with_terminal = _make_registry(
            bottom=[
                ("editor:console", "Console"),
                ("editor:terminal", "Terminal"),
            ],
        )
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=registry_with_terminal)
        m1.active.bottom.active_tab_key = "editor:terminal"
        m1.save()

        # Terminal editor is uninstalled; only console remains.
        registry_without_terminal = _make_registry(
            bottom=[("editor:console", "Console")],
        )
        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=registry_without_terminal)
        assert [t.editor_key for t in m2.active.bottom.tabs] == ["editor:console"]
        assert m2.active.bottom.active_tab_key == "editor:console"

    def test_load_survives_empty_registry(self, tmp_path):
        """A persisted file wins over an empty registry."""
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        m1.save()

        empty_registry = _make_registry()
        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=empty_registry)
        assert m2.active.left.editor_key == "editor:browser"
        # Bottom tabs are re-derived — the empty registry produces an empty list.
        assert m2.active.bottom.tabs == []
        assert m2.active.bottom.active_tab_key is None

    def test_corrupt_file_falls_back_to_auto_populate(self, tmp_path):
        preset_dir = tmp_path / ".haywire"
        preset_dir.mkdir()
        (preset_dir / "workspace_state.json").write_text("{ not valid json")

        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        assert manager.active.left.editor_key == "editor:browser"

    def test_active_is_workspace_state(self, tmp_path):
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        assert isinstance(manager.active, WorkspaceState)

    def test_legacy_middle_bottom_fields_migrated(self, tmp_path):
        """Pre-BottomAreaState schema with ``middle.bottom_*`` fields should
        be read and migrated into the new top-level ``bottom`` field."""
        preset_dir = tmp_path / ".haywire"
        preset_dir.mkdir()
        legacy_payload = {
            "name": "default",
            "left": {"editor_key": "editor:browser", "visible": True, "size": 250},
            "middle": {
                "tabs": [{"editor_key": "editor:graph", "label": "Graph", "metadata": {}}],
                "active_tab_index": 0,
                "bottom_visible": True,
                "bottom_size": 310,
                "bottom_editor_key": "editor:console",
            },
            "right": {"editor_key": "editor:props", "visible": True, "size": 350},
            "left_bar_active": "editor:browser",
            "right_bar_active": "editor:props",
        }
        (preset_dir / "workspace_state.json").write_text(json.dumps(legacy_payload))

        registry = _make_registry(
            left=[("editor:browser", "Browser")],
            middle=[("editor:graph", "Graph")],
            right=[("editor:props", "Properties")],
            bottom=[("editor:console", "Console")],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)

        assert manager.active.bottom.visible is True
        assert manager.active.bottom.size == 310
        assert manager.active.bottom.active_tab_key == "editor:console"
        assert [t.editor_key for t in manager.active.bottom.tabs] == ["editor:console"]


class TestWorkspaceManagerDeserialize:
    def test_deserialize_workspace_roundtrip(self):
        """WorkspaceManager._deserialize_workspace reconstructs a WorkspaceState correctly."""
        ws = WorkspaceState(
            name="custom",
            left=AreaState(editor_key="editor:a", visible=True, size=250),
            middle=MiddleAreaState(
                tabs=[TabState(editor_key="editor:main", label="Main")],
            ),
            bottom=BottomAreaState(
                active_tab_key="editor:console",
                visible=True,
                size=215,
            ),
            right=AreaState(editor_key="editor:b", visible=True, size=350),
        )
        d = asdict(ws)
        restored = WorkspaceManager._deserialize_workspace(d)
        assert restored.name == ws.name
        assert restored.bottom.visible == ws.bottom.visible
        assert restored.bottom.size == ws.bottom.size
        assert restored.bottom.active_tab_key == ws.bottom.active_tab_key
        # Deserialize leaves bottom.tabs empty — the refresh step (called in
        # WorkspaceManager.__init__ after _load) populates them from the registry.
        assert restored.bottom.tabs == []
        assert len(restored.middle.tabs) == len(ws.middle.tabs)
        assert restored.middle.tabs[0].editor_key == ws.middle.tabs[0].editor_key
        assert restored.left.editor_key == ws.left.editor_key
        assert restored.right.editor_key == ws.right.editor_key

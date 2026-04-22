# tests/ui/test_workspace_state.py
"""
Tests for WorkspaceState serialization and WorkspaceManager.
"""

import json

from dataclasses import asdict

from haywire.ui.editor.identity import OpenBehavior
from haywire.ui.workspace.workspace_state import (
    SlotState,
    TabState,
    MainSlotState,
    BottomSlotState,
    WorkspaceState,
)
from haywire.ui.workspace.manager import WorkspaceManager


# ---------------------------------------------------------------------------
# WorkspaceState serialization tests
# ---------------------------------------------------------------------------


class TestWorkspaceStateSerialization:
    def test_slot_state_asdict(self):
        state = SlotState(active_tab_key="graph_editor", visible=True, size=300)
        d = asdict(state)
        assert d == {"active_tab_key": "graph_editor", "visible": True, "size": 300}

    def test_tab_state_asdict(self):
        state = TabState(editor_key="graph_editor", label="My Graph", metadata={"foo": 1})
        d = asdict(state)
        assert d["editor_key"] == "graph_editor"
        assert d["label"] == "My Graph"
        assert d["metadata"] == {"foo": 1}

    def test_tab_state_tab_id_is_editor_key_when_no_payload(self):
        state = TabState(editor_key="graph_editor", label="My Graph")
        assert state.payload is None
        assert state.tab_id == "graph_editor"

    def test_tab_state_tab_id_composes_editor_key_and_payload(self):
        state = TabState(
            editor_key="graph_editor",
            label="My Graph",
            metadata={"payload": "/path/to/a.haywire"},
        )
        assert state.payload == "/path/to/a.haywire"
        assert state.tab_id == "graph_editor::/path/to/a.haywire"

    def test_main_slot_state_asdict(self):
        state = MainSlotState()
        d = asdict(state)
        assert "tabs" in d
        assert "active_tab_key" in d

    def test_bottom_slot_state_asdict(self):
        state = BottomSlotState()
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
        assert "main" in d
        assert "bottom" in d
        assert "right" in d

    def test_workspace_state_roundtrip(self):
        """Serializing then deserializing WorkspaceState fields preserves data."""
        ws = WorkspaceState(name="My WS")
        d = asdict(ws)
        assert d["name"] == "My WS"
        assert d["left"]["active_tab_key"] is None  # no studio strings in core
        assert d["right"]["active_tab_key"] is None

    def test_default_workspace_state(self):
        ws = WorkspaceState()
        assert ws.name == "default"
        assert ws.left.active_tab_key is None  # generic — no studio strings
        assert ws.right.active_tab_key is None
        assert ws.main.tabs[0].editor_key is None  # consistent with other key fields
        assert ws.bottom.tabs == []
        assert ws.bottom.active_tab_key is None


# ---------------------------------------------------------------------------
# WorkspaceManager tests
# ---------------------------------------------------------------------------


class _FakeIdentity:
    def __init__(self, label: str, opens: OpenBehavior = OpenBehavior.REQUIRED):
        self.label = label
        self.opens = opens


class _FakeEditorClass:
    def __init__(self, label: str, opens: OpenBehavior = OpenBehavior.REQUIRED):
        self.class_identity = _FakeIdentity(label, opens)


class _FakeEditorRegistry:
    """Minimal EditorTypeRegistry stand-in for WorkspaceManager tests."""

    def __init__(self, by_slot: dict[str, dict[str, _FakeEditorClass]]):
        self._by_slot = by_slot

    def get_by_default_slot(self, slot: str) -> dict[str, _FakeEditorClass]:
        return dict(self._by_slot.get(slot, {}))


def _make_registry(**slots) -> _FakeEditorRegistry:
    """Build a fake registry from slot -> [(key, label) | (key, label, opens)] pairs."""
    by_slot: dict[str, dict[str, _FakeEditorClass]] = {}
    for slot, entries in slots.items():
        by_slot[slot] = {}
        for entry in entries:
            if len(entry) == 2:
                key, label = entry
                opens = OpenBehavior.REQUIRED
            else:
                key, label, opens = entry
            by_slot[slot][key] = _FakeEditorClass(label, opens)
    return _FakeEditorRegistry(by_slot)


class TestWorkspaceManagerAutoPopulate:
    def test_auto_populates_when_no_file(self, tmp_path):
        registry = _make_registry(
            left=[("editor:browser", "Browser")],
            main=[("editor:graph", "Graph"), ("editor:library", "Library")],
            right=[("editor:props", "Properties")],
            bottom=[("editor:console", "Console")],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)

        assert manager.active.left.active_tab_key == "editor:browser"
        assert manager.active.right.active_tab_key == "editor:props"
        # Bottom slot is retracted by default but its tab roster is populated
        # from the registry on every load.
        assert manager.active.bottom.visible is False
        assert [t.editor_key for t in manager.active.bottom.tabs] == ["editor:console"]
        assert manager.active.bottom.active_tab_key == "editor:console"

        labels = [t.label for t in manager.active.main.tabs]
        keys = [t.editor_key for t in manager.active.main.tabs]
        assert keys == ["editor:graph", "editor:library"]
        assert labels == ["Graph", "Library"]

    def test_auto_populate_handles_empty_registry(self, tmp_path):
        registry = _make_registry()
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)

        assert manager.active.left.active_tab_key is None
        assert manager.active.left.visible is False
        assert manager.active.right.active_tab_key is None
        assert manager.active.right.visible is False
        assert manager.active.bottom.tabs == []
        assert manager.active.bottom.active_tab_key is None
        assert len(manager.active.main.tabs) == 1
        assert manager.active.main.tabs[0].editor_key is None

    def test_auto_populate_partial_slots(self, tmp_path):
        registry = _make_registry(
            main=[("editor:graph", "Graph")],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)

        assert manager.active.left.active_tab_key is None
        assert manager.active.right.active_tab_key is None
        assert manager.active.bottom.tabs == []
        assert manager.active.main.tabs[0].editor_key == "editor:graph"

    def test_auto_populate_does_not_write_file(self, tmp_path):
        registry = _make_registry(left=[("editor:a", "A")])
        WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        assert not (tmp_path / ".haywire" / "workspace_state.json").exists()

    def test_auto_populate_with_multiple_bottom_editors(self, tmp_path):
        """Every bottom-slot editor becomes a tab; first is active by default."""
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

    def test_auto_populate_skips_on_payload_main_editors(self, tmp_path):
        """Main-slot auto-populate must exclude opens='on_payload' editors."""
        registry = _make_registry(
            main=[
                ("editor:required", "Required", OpenBehavior.REQUIRED),
                ("editor:doc", "Document", OpenBehavior.ON_PAYLOAD),
            ],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        keys = [t.editor_key for t in manager.active.main.tabs]
        assert keys == ["editor:required"]

    def test_auto_populate_skips_on_context_main_editors(self, tmp_path):
        """Main-slot auto-populate must exclude opens='on_context' editors."""
        registry = _make_registry(
            main=[
                ("editor:required", "Required", OpenBehavior.REQUIRED),
                ("editor:ctx", "Contextual", OpenBehavior.ON_CONTEXT),
            ],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        keys = [t.editor_key for t in manager.active.main.tabs]
        assert keys == ["editor:required"]

    def test_auto_populate_main_all_on_payload_leaves_empty(self, tmp_path):
        """When every main editor is on_payload, main tab list has one empty placeholder."""
        registry = _make_registry(
            main=[
                ("editor:doc_a", "Doc A", OpenBehavior.ON_PAYLOAD),
                ("editor:doc_b", "Doc B", OpenBehavior.ON_PAYLOAD),
            ],
        )
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        # Matches the existing empty-registry contract: one placeholder TabState.
        assert len(manager.active.main.tabs) == 1
        assert manager.active.main.tabs[0].editor_key is None


class TestWorkspaceManagerPersistence:
    def _registry(self) -> _FakeEditorRegistry:
        return _make_registry(
            left=[("editor:browser", "Browser")],
            main=[("editor:graph", "Graph")],
            right=[("editor:props", "Properties")],
            bottom=[("editor:console", "Console")],
        )

    def test_save_writes_file(self, tmp_path):
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        manager.save()

        state_file = tmp_path / ".haywire" / "workspace_state.json"
        assert state_file.exists()

        data = json.loads(state_file.read_text())
        assert data["left"]["active_tab_key"] == "editor:browser"
        # payload-less main tabs (required singletons) are stripped on save —
        # they are re-derived from the registry on the next load.
        assert data["main"]["tabs"] == []
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
        assert m2.active.left.active_tab_key == "editor:browser"

    def test_load_refreshes_bottom_tabs_from_registry(self, tmp_path):
        """A newly-installed bottom editor should appear after a reload even
        though the persisted file predates it."""
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        m1.save()

        # Registry now has an additional bottom editor the persisted file
        # never saw.
        richer_registry = _make_registry(
            left=[("editor:browser", "Browser")],
            main=[("editor:graph", "Graph")],
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
        assert m2.active.left.active_tab_key == "editor:browser"
        # Bottom tabs are re-derived — the empty registry produces an empty list.
        assert m2.active.bottom.tabs == []
        assert m2.active.bottom.active_tab_key is None

    def test_corrupt_file_falls_back_to_auto_populate(self, tmp_path):
        preset_dir = tmp_path / ".haywire"
        preset_dir.mkdir()
        (preset_dir / "workspace_state.json").write_text("{ not valid json")

        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        assert manager.active.left.active_tab_key == "editor:browser"

    def test_active_is_workspace_state(self, tmp_path):
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        assert isinstance(manager.active, WorkspaceState)

    def test_save_strips_payload_less_main_tabs(self, tmp_path):
        """Save must not persist main tabs without a payload — they are
        re-derived from the registry on load, same pattern as bottom."""
        manager = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        # Add a payload-less tab (would be a `required` singleton) and a
        # payload-carrying tab (an `on_payload` document).
        manager.active.main.tabs = [
            TabState(editor_key="editor:required", label="Required"),
            TabState(
                editor_key="editor:graph",
                label="loop.haywire",
                metadata={"payload": "/tmp/loop.haywire"},
            ),
        ]
        manager.active.main.active_tab_key = "editor:graph::/tmp/loop.haywire"
        manager.save()

        data = json.loads((tmp_path / ".haywire" / "workspace_state.json").read_text())
        main_tabs = data["main"]["tabs"]
        assert len(main_tabs) == 1
        assert main_tabs[0]["editor_key"] == "editor:graph"
        assert main_tabs[0]["metadata"]["payload"] == "/tmp/loop.haywire"

    def test_load_injects_missing_required_main_tabs(self, tmp_path):
        """If a `required` main editor has no persisted tab, inject it on load."""
        # Save with only a payload-carrying main tab persisted.
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        m1.active.main.tabs = [
            TabState(
                editor_key="editor:graph",
                label="loop.haywire",
                metadata={"payload": "/tmp/loop.haywire"},
            ),
        ]
        m1.active.main.active_tab_key = "editor:graph::/tmp/loop.haywire"
        m1.save()

        # On load, registry still has the required "editor:graph" — it must be
        # injected in addition to the persisted payload-carrying tab.
        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        keys = [t.editor_key for t in m2.active.main.tabs]
        # editor:graph REQUIRED tab + the persisted payload tab
        assert keys.count("editor:graph") == 2
        # One is payload-less, one carries the path.
        payloads = [t.payload for t in m2.active.main.tabs]
        assert None in payloads
        assert "/tmp/loop.haywire" in payloads

    def test_load_drops_payload_tabs_whose_editor_is_unregistered(self, tmp_path):
        """A persisted on_payload tab whose editor is gone from registry is skipped."""
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        m1.active.main.tabs = [
            TabState(
                editor_key="editor:unknown",
                label="gone.haywire",
                metadata={"payload": "/tmp/gone.haywire"},
            ),
        ]
        m1.save()

        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=self._registry())
        keys = [t.editor_key for t in m2.active.main.tabs]
        assert "editor:unknown" not in keys

    def test_load_only_on_payload_registry_restores_payload_tabs(self, tmp_path):
        """A persisted payload tab whose editor is opens=on_payload is restored."""
        registry = _make_registry(
            main=[("editor:graph", "Graph", OpenBehavior.ON_PAYLOAD)],
        )
        m1 = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        m1.active.main.tabs = [
            TabState(
                editor_key="editor:graph",
                label="a.haywire",
                metadata={"payload": "/tmp/a.haywire"},
            ),
            TabState(
                editor_key="editor:graph",
                label="b.haywire",
                metadata={"payload": "/tmp/b.haywire"},
            ),
        ]
        m1.active.main.active_tab_key = "editor:graph::/tmp/b.haywire"
        m1.save()

        m2 = WorkspaceManager(project_path=tmp_path, editor_registry=registry)
        payloads = sorted(t.payload or "" for t in m2.active.main.tabs)
        assert payloads == ["/tmp/a.haywire", "/tmp/b.haywire"]
        assert m2.active.main.active_tab_key == "editor:graph::/tmp/b.haywire"


class TestWorkspaceManagerDeserialize:
    def test_deserialize_workspace_roundtrip(self):
        """WorkspaceManager._deserialize_workspace reconstructs a WorkspaceState correctly."""
        ws = WorkspaceState(
            name="custom",
            left=SlotState(active_tab_key="editor:a", visible=True, size=250),
            main=MainSlotState(
                tabs=[TabState(editor_key="editor:main", label="Main")],
            ),
            bottom=BottomSlotState(
                active_tab_key="editor:console",
                visible=True,
                size=215,
            ),
            right=SlotState(active_tab_key="editor:b", visible=True, size=350),
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
        assert len(restored.main.tabs) == len(ws.main.tabs)
        assert restored.main.tabs[0].editor_key == ws.main.tabs[0].editor_key
        assert restored.left.active_tab_key == ws.left.active_tab_key
        assert restored.right.active_tab_key == ws.right.active_tab_key

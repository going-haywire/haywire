# tests/ui/test_workspace_state.py
"""Tests for the simplified WorkspaceManager (dumb file I/O)."""

import json
from haywire.ui.workspace.manager import WorkspaceManager


class TestWorkspaceManagerLoad:
    def test_load_returns_empty_dict_when_no_file(self, tmp_path):
        wm = WorkspaceManager(project_path=tmp_path)
        assert wm.snapshot == {}

    def test_load_reads_json_file(self, tmp_path):
        state_file = tmp_path / ".haywire" / "workspace_state.json"
        state_file.parent.mkdir()
        state_file.write_text(json.dumps({"haystack": "default", "left": {"active_key": "ed:a"}}))
        wm = WorkspaceManager(project_path=tmp_path)
        assert wm.snapshot["haystack"] == "default"
        assert wm.snapshot["left"]["active_key"] == "ed:a"

    def test_corrupt_file_falls_back_to_empty(self, tmp_path):
        state_file = tmp_path / ".haywire" / "workspace_state.json"
        state_file.parent.mkdir()
        state_file.write_text("{ not valid json")
        wm = WorkspaceManager(project_path=tmp_path)
        assert wm.snapshot == {}


class TestWorkspaceManagerSave:
    def test_save_writes_json_file(self, tmp_path):
        wm = WorkspaceManager(project_path=tmp_path)
        snapshot = {
            "haystack": "default",
            "left": {"active_key": "ed:a", "visible": True, "size": 250, "editors": []},
        }
        wm.save(snapshot)
        state_file = tmp_path / ".haywire" / "workspace_state.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["haystack"] == "default"
        assert data["left"]["active_key"] == "ed:a"

    def test_save_creates_haywire_dir(self, tmp_path):
        wm = WorkspaceManager(project_path=tmp_path)
        assert not (tmp_path / ".haywire").exists()
        wm.save({"haystack": "x"})
        assert (tmp_path / ".haywire").exists()

    def test_save_updates_snapshot(self, tmp_path):
        wm = WorkspaceManager(project_path=tmp_path)
        wm.save({"haystack": "my_stack"})
        assert wm.snapshot["haystack"] == "my_stack"

    def test_roundtrip(self, tmp_path):
        wm1 = WorkspaceManager(project_path=tmp_path)
        payload = {
            "haystack": "proj",
            "left": {"active_key": "ed:browser", "visible": False, "size": 200, "editors": []},
            "main": {
                "active_key": "ed:graph::/tmp/a.haywire",
                "editors": [{"key": "ed:graph", "payload": "/tmp/a.haywire", "label": "a.haywire"}],
            },
            "bottom": {"active_key": "ed:console", "visible": True, "size": 300, "editors": []},
            "right": {"active_key": "ed:props", "visible": True, "size": 350, "editors": []},
        }
        wm1.save(payload)
        wm2 = WorkspaceManager(project_path=tmp_path)
        assert wm2.snapshot == payload

"""Persistence — free functions for per-haystack TOML I/O."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary workspace with haystacks/ and graphs/ subdirectories."""
    (tmp_path / "haystacks").mkdir()
    (tmp_path / "graphs").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# dump_haystack
# ---------------------------------------------------------------------------


def test_dump_haystack_writes_toml_at_expected_path(tmp_workspace):
    from haybale_haystack.persistence import dump_haystack
    from haybale_haystack.graph_entry import GraphEntry

    g = MagicMock()
    p = tmp_workspace / "graphs" / "test.haywire"
    p.write_text("dummy")
    entry = GraphEntry(graph=g, editor=MagicMock(), path=p, unsaved=False)

    state = MagicMock()
    state.all_entries.return_value = [entry]

    dump_haystack(state, workspace_root=tmp_workspace, name="myset")

    expected = tmp_workspace / "haystacks" / "myset.toml"
    assert expected.exists()
    content = expected.read_text()
    assert "test.haywire" in content


def test_dump_creates_haystacks_dir_if_missing(tmp_path):
    """haystacks/ dir is created on demand when it doesn't exist yet."""
    from haybale_haystack.persistence import dump_haystack
    from haybale_haystack.graph_entry import GraphEntry

    (tmp_path / "graphs").mkdir()
    p = tmp_path / "graphs" / "x.haywire"
    p.write_text("")
    entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=p, unsaved=False)

    state = MagicMock()
    state.all_entries.return_value = [entry]

    dump_haystack(state, workspace_root=tmp_path, name="auto")

    assert (tmp_path / "haystacks" / "auto.toml").exists()


def test_dump_skips_unsaved_entries(tmp_workspace):
    """Entries with path=None (untitled) are excluded from the TOML."""
    from haybale_haystack.persistence import dump_haystack
    from haybale_haystack.graph_entry import GraphEntry

    entry_unsaved = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=None, unsaved=True)

    state = MagicMock()
    state.all_entries.return_value = [entry_unsaved]

    dump_haystack(state, workspace_root=tmp_workspace, name="empty")

    import toml

    data = toml.loads((tmp_workspace / "haystacks" / "empty.toml").read_text())
    assert data["graphs"] == []


def test_dump_includes_execute_flag_for_running_entries(tmp_workspace):
    from haybale_haystack.persistence import dump_haystack
    from haybale_haystack.graph_entry import GraphEntry

    g = MagicMock()
    p = tmp_workspace / "graphs" / "running.haywire"
    p.write_text("")

    entry = GraphEntry(graph=g, editor=MagicMock(), path=p, unsaved=False)
    # Mark it as currently executing
    entry.interpreter = MagicMock()
    entry.interpreter.is_executing = True

    state = MagicMock()
    state.all_entries.return_value = [entry]

    dump_haystack(state, workspace_root=tmp_workspace, name="exec")

    import toml

    data = toml.loads((tmp_workspace / "haystacks" / "exec.toml").read_text())
    graphs = data["graphs"]
    assert len(graphs) == 1
    assert graphs[0]["execute"] is True


def test_dump_stores_active_graph_as_relative_path(tmp_workspace):
    """active_path is stored under haystack.active_graph as a relative path."""
    from haybale_haystack.persistence import dump_haystack
    from haybale_haystack.graph_entry import GraphEntry

    p = tmp_workspace / "graphs" / "active.haywire"
    p.write_text("")
    entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=p, unsaved=False)

    state = MagicMock()
    state.all_entries.return_value = [entry]

    dump_haystack(state, workspace_root=tmp_workspace, name="withactive", active_path=p)

    import toml

    data = toml.loads((tmp_workspace / "haystacks" / "withactive.toml").read_text())
    assert data["haystack"]["active_graph"] == "graphs/active.haywire"


def test_dump_omits_active_graph_key_when_none(tmp_workspace):
    """When active_path is None the active_graph key is absent from TOML."""
    from haybale_haystack.persistence import dump_haystack

    state = MagicMock()
    state.all_entries.return_value = []

    dump_haystack(state, workspace_root=tmp_workspace, name="noactive")

    import toml

    data = toml.loads((tmp_workspace / "haystacks" / "noactive.toml").read_text())
    assert "active_graph" not in data.get("haystack", {})


def test_dump_stores_paths_relative_to_workspace(tmp_workspace):
    """Graph paths in TOML are relative to workspace_root, not absolute."""
    from haybale_haystack.persistence import dump_haystack
    from haybale_haystack.graph_entry import GraphEntry

    p = tmp_workspace / "graphs" / "sub.haywire"
    p.write_text("")
    entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=p, unsaved=False)

    state = MagicMock()
    state.all_entries.return_value = [entry]

    dump_haystack(state, workspace_root=tmp_workspace, name="relpaths")

    import toml

    data = toml.loads((tmp_workspace / "haystacks" / "relpaths.toml").read_text())
    # Must be relative, not absolute
    assert not Path(data["graphs"][0]["path"]).is_absolute()
    assert data["graphs"][0]["path"] == "graphs/sub.haywire"


# ---------------------------------------------------------------------------
# load_haystack
# ---------------------------------------------------------------------------


def test_load_haystack_returns_none_for_missing_file(tmp_workspace):
    from haybale_haystack.persistence import load_haystack

    result = load_haystack(MagicMock(), workspace_root=tmp_workspace, name="nonexistent")
    assert result is None


def test_load_haystack_skips_missing_graphs(tmp_workspace):
    """Graphs listed in the TOML that no longer exist on disk are skipped."""
    import toml
    from haybale_haystack.persistence import load_haystack

    toml_data = {
        "haystack": {"name": "ghost"},
        "graphs": [{"path": "graphs/ghost.haywire", "execute": False}],
    }
    (tmp_workspace / "haystacks" / "ghost.toml").write_text(toml.dumps(toml_data))

    state = MagicMock()
    result = load_haystack(state, workspace_root=tmp_workspace, name="ghost")
    # open_graph should NOT be called for the missing file
    state.open_graph.assert_not_called()
    assert result is None


def test_load_haystack_opens_existing_graphs(tmp_workspace):
    """Graphs that exist on disk are opened via state.open_graph."""
    import toml
    from haybale_haystack.persistence import load_haystack

    p = tmp_workspace / "graphs" / "real.haywire"
    p.write_text("")

    toml_data = {
        "haystack": {"name": "real"},
        "graphs": [{"path": "graphs/real.haywire", "execute": False}],
    }
    (tmp_workspace / "haystacks" / "real.toml").write_text(toml.dumps(toml_data))

    state = MagicMock()
    load_haystack(state, workspace_root=tmp_workspace, name="real")
    state.open_graph.assert_called_once_with(p)


def test_load_haystack_starts_execution_when_flag_set(tmp_workspace):
    """Graphs with execute=true have start_execution() called on their entry."""
    import toml
    from haybale_haystack.persistence import load_haystack

    p = tmp_workspace / "graphs" / "exec.haywire"
    p.write_text("")

    toml_data = {
        "haystack": {"name": "execset"},
        "graphs": [{"path": "graphs/exec.haywire", "execute": True}],
    }
    (tmp_workspace / "haystacks" / "execset.toml").write_text(toml.dumps(toml_data))

    state = MagicMock()
    entry_mock = MagicMock()
    state.open_graph.return_value = entry_mock

    load_haystack(state, workspace_root=tmp_workspace, name="execset")
    entry_mock.start_execution.assert_called_once()


def test_load_haystack_returns_active_path(tmp_workspace):
    """load_haystack returns the active_graph path (absolute) when present."""
    import toml
    from haybale_haystack.persistence import load_haystack

    p = tmp_workspace / "graphs" / "act.haywire"
    p.write_text("")

    toml_data = {
        "haystack": {"name": "withact", "active_graph": "graphs/act.haywire"},
        "graphs": [{"path": "graphs/act.haywire", "execute": False}],
    }
    (tmp_workspace / "haystacks" / "withact.toml").write_text(toml.dumps(toml_data))

    state = MagicMock()
    state.open_graph.return_value = MagicMock()
    active = load_haystack(state, workspace_root=tmp_workspace, name="withact")

    assert active == tmp_workspace / "graphs" / "act.haywire"


# ---------------------------------------------------------------------------
# list_haystacks
# ---------------------------------------------------------------------------


def test_list_haystacks_returns_names(tmp_workspace):
    from haybale_haystack.persistence import list_haystacks

    (tmp_workspace / "haystacks" / "alpha.toml").write_text("")
    (tmp_workspace / "haystacks" / "beta.toml").write_text("")
    (tmp_workspace / "haystacks" / "ignore.txt").write_text("")  # non-toml ignored

    names = list_haystacks(workspace_root=tmp_workspace)
    assert set(names) == {"alpha", "beta"}


def test_list_haystacks_returns_empty_when_dir_missing(tmp_path):
    from haybale_haystack.persistence import list_haystacks

    # No haystacks/ dir — should return []
    names = list_haystacks(workspace_root=tmp_path)
    assert names == []


# ---------------------------------------------------------------------------
# delete_haystack
# ---------------------------------------------------------------------------


def test_delete_haystack_removes_file(tmp_workspace):
    from haybale_haystack.persistence import delete_haystack

    (tmp_workspace / "haystacks" / "todel.toml").write_text("")
    assert delete_haystack(workspace_root=tmp_workspace, name="todel") is True
    assert not (tmp_workspace / "haystacks" / "todel.toml").exists()


def test_delete_haystack_returns_false_for_missing(tmp_workspace):
    from haybale_haystack.persistence import delete_haystack

    assert delete_haystack(workspace_root=tmp_workspace, name="nope") is False


# ---------------------------------------------------------------------------
# rename_haystack
# ---------------------------------------------------------------------------


def test_rename_haystack_moves_file(tmp_workspace):
    from haybale_haystack.persistence import rename_haystack
    import toml

    toml_data = {"haystack": {"name": "old"}, "graphs": []}
    (tmp_workspace / "haystacks" / "old.toml").write_text(toml.dumps(toml_data))

    result = rename_haystack(workspace_root=tmp_workspace, old_name="old", new_name="new")
    assert result is True
    assert not (tmp_workspace / "haystacks" / "old.toml").exists()
    assert (tmp_workspace / "haystacks" / "new.toml").exists()


def test_rename_haystack_updates_name_in_toml(tmp_workspace):
    """The name field inside the TOML is updated to the new name."""
    from haybale_haystack.persistence import rename_haystack
    import toml

    toml_data = {"haystack": {"name": "old"}, "graphs": []}
    (tmp_workspace / "haystacks" / "old.toml").write_text(toml.dumps(toml_data))

    rename_haystack(workspace_root=tmp_workspace, old_name="old", new_name="renamed")

    data = toml.loads((tmp_workspace / "haystacks" / "renamed.toml").read_text())
    assert data["haystack"]["name"] == "renamed"


def test_rename_haystack_returns_false_when_src_missing(tmp_workspace):
    from haybale_haystack.persistence import rename_haystack

    assert rename_haystack(workspace_root=tmp_workspace, old_name="ghost", new_name="x") is False


def test_rename_haystack_returns_false_when_dst_exists(tmp_workspace):
    from haybale_haystack.persistence import rename_haystack

    (tmp_workspace / "haystacks" / "a.toml").write_text("")
    (tmp_workspace / "haystacks" / "b.toml").write_text("")

    assert rename_haystack(workspace_root=tmp_workspace, old_name="a", new_name="b") is False


# ---------------------------------------------------------------------------
# run_settings persistence
# ---------------------------------------------------------------------------


def test_dump_writes_run_table_when_autorestart_set(tmp_workspace):
    import toml
    from haybale_haystack.persistence import dump_haystack
    from haybale_haystack.graph_entry import GraphEntry

    p = tmp_workspace / "graphs" / "r.haywire"
    p.write_text("")
    entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=p, unsaved=False)
    entry.run_settings.autorestart = True

    state = MagicMock()
    state.all_entries.return_value = [entry]

    dump_haystack(state, workspace_root=tmp_workspace, name="rs")

    data = toml.loads((tmp_workspace / "haystacks" / "rs.toml").read_text())
    assert data["graphs"][0]["run"] == {"autorestart": True}


def test_dump_omits_run_table_when_default(tmp_workspace):
    import toml
    from haybale_haystack.persistence import dump_haystack
    from haybale_haystack.graph_entry import GraphEntry

    p = tmp_workspace / "graphs" / "d.haywire"
    p.write_text("")
    entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=p, unsaved=False)
    # autorestart left at default False -> sparse to_dict() is empty

    state = MagicMock()
    state.all_entries.return_value = [entry]

    dump_haystack(state, workspace_root=tmp_workspace, name="dd")

    data = toml.loads((tmp_workspace / "haystacks" / "dd.toml").read_text())
    assert "run" not in data["graphs"][0]


def test_load_restores_autorestart_onto_entry(tmp_workspace):
    """load_haystack applies the [graphs.run] table to entry.run_settings."""
    import toml
    from haybale_haystack.persistence import load_haystack
    from haybale_haystack.graph_entry import GraphEntry

    gpath = tmp_workspace / "graphs" / "g.haywire"
    gpath.write_text("")
    toml_doc = {
        "haystack": {"name": "ld"},
        "graphs": [{"path": "graphs/g.haywire", "execute": False, "run": {"autorestart": True}}],
    }
    (tmp_workspace / "haystacks" / "ld.toml").write_text(toml.dumps(toml_doc))

    opened = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=gpath, unsaved=False)

    state = MagicMock()
    state.open_graph.return_value = opened

    load_haystack(state, workspace_root=tmp_workspace, name="ld")

    assert opened.run_settings.autorestart is True


def test_load_tolerates_missing_run_table(tmp_workspace):
    """Old haystacks without [graphs.run] load with defaults, no error."""
    import toml
    from haybale_haystack.persistence import load_haystack
    from haybale_haystack.graph_entry import GraphEntry

    gpath = tmp_workspace / "graphs" / "g2.haywire"
    gpath.write_text("")
    toml_doc = {
        "haystack": {"name": "old"},
        "graphs": [{"path": "graphs/g2.haywire", "execute": False}],
    }
    (tmp_workspace / "haystacks" / "old.toml").write_text(toml.dumps(toml_doc))

    opened = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=gpath, unsaved=False)
    state = MagicMock()
    state.open_graph.return_value = opened

    load_haystack(state, workspace_root=tmp_workspace, name="old")

    assert opened.run_settings.autorestart is False


def test_load_skips_graph_whose_autostart_fails(tmp_workspace, caplog):
    """A graph marked execute=true that fails to compile is skipped, not fatal,
    and loading continues for the rest."""
    import logging
    import toml
    from haybale_haystack.persistence import load_haystack
    from haybale_haystack.graph_entry import GraphEntry
    from haywire.core.execution.compile_result import CompileResult

    g1 = tmp_workspace / "graphs" / "ok.haywire"
    g1.write_text("")
    g2 = tmp_workspace / "graphs" / "bad.haywire"
    g2.write_text("")
    toml_doc = {
        "haystack": {"name": "mix"},
        "graphs": [
            {"path": "graphs/bad.haywire", "execute": True},
            {"path": "graphs/ok.haywire", "execute": False},
        ],
    }
    (tmp_workspace / "haystacks" / "mix.toml").write_text(toml.dumps(toml_doc))

    bad_entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=g2, unsaved=False)
    bad_entry.start_execution = MagicMock(return_value=CompileResult(ok=False, error="broken graph"))
    ok_entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=g1, unsaved=False)

    state = MagicMock()
    # open_graph is called once per listed graph, in file order
    state.open_graph.side_effect = [bad_entry, ok_entry]

    with caplog.at_level(logging.WARNING):
        load_haystack(state, workspace_root=tmp_workspace, name="mix")

    # both graphs were opened; the bad one's failed autostart did not raise
    assert state.open_graph.call_count == 2
    assert any("broken graph" in r.message or "bad.haywire" in r.message for r in caplog.records)

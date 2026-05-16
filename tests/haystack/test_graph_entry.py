"""GraphEntry — dataclass tests."""

from pathlib import Path
from unittest.mock import MagicMock


def test_graph_entry_default_unsaved():
    from haybale_haystack.graph_entry import GraphEntry

    g = MagicMock()
    e = MagicMock()
    entry = GraphEntry(graph=g, editor=e, path=None, unsaved=True)
    assert entry.unsaved is True
    assert entry.path is None
    assert entry.interpreter is None


def test_binding_id_uses_path_when_set():
    from haybale_haystack.graph_entry import GraphEntry

    p = Path("/tmp/foo.haywire")
    entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=p, unsaved=False)
    assert entry.binding_id == str(p)


def test_binding_id_uses_unsaved_id_for_unsaved():
    from haybale_haystack.graph_entry import GraphEntry

    entry = GraphEntry(
        graph=MagicMock(),
        editor=MagicMock(),
        path=None,
        unsaved=True,
        _unsaved_id="__unsaved_1__",
    )
    assert entry.binding_id == "__unsaved_1__"


def test_display_name_uses_path_stem_when_set():
    from haybale_haystack.graph_entry import GraphEntry

    entry = GraphEntry(
        graph=MagicMock(),
        editor=MagicMock(),
        path=Path("/tmp/MyName.haywire"),
        unsaved=False,
    )
    # display_name returns path.stem — the filename without the .haywire extension.
    assert entry.display_name == "MyName"


def test_display_name_falls_back_to_graph_name():
    from haybale_haystack.graph_entry import GraphEntry

    g = MagicMock()
    g.name = "MyGraph"
    entry = GraphEntry(graph=g, editor=MagicMock(), path=None, unsaved=True)
    assert entry.display_name == "MyGraph"


def test_display_name_falls_back_to_untitled():
    from haybale_haystack.graph_entry import GraphEntry

    g = MagicMock(spec=[])  # no .name attribute
    entry = GraphEntry(graph=g, editor=MagicMock(), path=None, unsaved=True)
    assert entry.display_name == "Untitled"


def test_is_executing_false_when_no_interpreter():
    from haybale_haystack.graph_entry import GraphEntry

    entry = GraphEntry(graph=MagicMock(), editor=MagicMock())
    assert entry.is_executing is False


def test_is_executing_true_when_interpreter_is_executing():
    from haybale_haystack.graph_entry import GraphEntry

    interp = MagicMock()
    interp.is_executing = True
    entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), interpreter=interp)
    assert entry.is_executing is True


def test_stop_execution_noop_when_not_executing():
    from haybale_haystack.graph_entry import GraphEntry

    entry = GraphEntry(graph=MagicMock(), editor=MagicMock())
    # Should not raise
    entry.stop_execution()
    assert entry.interpreter is None


def test_stop_execution_clears_interpreter():
    from haybale_haystack.graph_entry import GraphEntry

    interp = MagicMock()
    interp.is_executing = True
    entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), interpreter=interp)
    entry.stop_execution()
    interp.stop_execution.assert_called_once()
    assert entry.interpreter is None


def test_graph_entry_save_delegates_to_haystack():
    """entry.save() calls haystack._save_entry(self, save_as=...).

    The method is a thin shim — most logic lives in HaystackState.
    """
    from haybale_haystack.graph_entry import GraphEntry

    captured = {}

    class _FakeHaystack:
        def _save_entry(self, entry, save_as=None):
            captured["entry"] = entry
            captured["save_as"] = save_as
            return None  # no rename

    fake = _FakeHaystack()
    entry = GraphEntry(graph=object(), editor=object(), haystack=fake)
    result = entry.save()

    assert captured["entry"] is entry
    assert captured["save_as"] is None
    assert result is None


def test_graph_entry_save_propagates_new_binding_id():
    """When _save_entry returns a new binding_id (rename case),
    entry.save() returns it untouched."""
    from haybale_haystack.graph_entry import GraphEntry

    class _FakeHaystack:
        def _save_entry(self, entry, save_as=None):
            return "new-id-from-save-as"

    entry = GraphEntry(graph=object(), editor=object(), haystack=_FakeHaystack())
    assert entry.save(save_as=Path("/tmp/x.haywire")) == "new-id-from-save-as"


def test_graph_entry_holds_haystack_back_reference():
    """GraphEntry carries a reference to its owning HaystackState.

    Used by GraphEntry.save() to delegate persistence back. The
    reference is required (kw-only) on construction; tests use a
    sentinel object since the contract is only that it round-trips.
    """
    from haybale_haystack.graph_entry import GraphEntry

    sentinel_haystack = object()
    fake_graph = object()
    fake_editor = object()

    entry = GraphEntry(
        graph=fake_graph,
        editor=fake_editor,
        haystack=sentinel_haystack,
    )
    assert entry.haystack is sentinel_haystack

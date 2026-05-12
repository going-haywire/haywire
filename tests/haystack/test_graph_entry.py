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


def test_entry_id_uses_path_when_set():
    from haybale_haystack.graph_entry import GraphEntry

    p = Path("/tmp/foo.haywire")
    entry = GraphEntry(graph=MagicMock(), editor=MagicMock(), path=p, unsaved=False)
    assert entry.entry_id == str(p)


def test_entry_id_uses_unsaved_id_for_unsaved():
    from haybale_haystack.graph_entry import GraphEntry

    entry = GraphEntry(
        graph=MagicMock(),
        editor=MagicMock(),
        path=None,
        unsaved=True,
        _unsaved_id="__unsaved_1__",
    )
    assert entry.entry_id == "__unsaved_1__"


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

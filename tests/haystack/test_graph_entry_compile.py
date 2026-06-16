"""GraphEntry.compile() / start() split."""

from unittest.mock import MagicMock, patch

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def _make_entry():
    from haybale_haystack.graph_entry import GraphEntry

    return GraphEntry(graph=MagicMock(), editor=MagicMock())


def test_compile_success_returns_ok_and_sets_interpreter():
    from haybale_haystack.graph_entry import GraphEntry  # noqa: F401

    entry = _make_entry()
    fake_interp = MagicMock()
    with (
        patch("haybale_haystack.graph_entry.Interpreter", return_value=fake_interp),
        patch("haybale_haystack.graph_entry.get_library_state_container", return_value=MagicMock()),
    ):
        result = entry.compile()

    assert result.ok is True
    assert result.error is None
    assert entry.interpreter is fake_interp
    fake_interp.load_graph.assert_called_once_with(entry.graph)
    # compile() must NOT start execution
    fake_interp.start_execution.assert_not_called()


def test_compile_failure_returns_error_and_clears_interpreter():
    entry = _make_entry()
    fake_interp = MagicMock()
    fake_interp.load_graph.side_effect = RuntimeError("Graph validation failed: boom")
    with (
        patch("haybale_haystack.graph_entry.Interpreter", return_value=fake_interp),
        patch("haybale_haystack.graph_entry.get_library_state_container", return_value=MagicMock()),
    ):
        result = entry.compile()

    assert result.ok is False
    assert "boom" in (result.error or "")
    # a failed compile must not leave a half-loaded interpreter behind
    assert entry.interpreter is None


def test_start_dispatches_begin_play():
    entry = _make_entry()
    fake_interp = MagicMock()
    entry.interpreter = fake_interp
    entry.start()
    fake_interp.start_execution.assert_called_once()


def test_start_noop_without_interpreter():
    entry = _make_entry()
    # no interpreter compiled yet — must not raise
    entry.start()


def test_start_execution_compiles_then_starts():
    entry = _make_entry()
    fake_interp = MagicMock()
    with (
        patch("haybale_haystack.graph_entry.Interpreter", return_value=fake_interp),
        patch("haybale_haystack.graph_entry.get_library_state_container", return_value=MagicMock()),
    ):
        result = entry.start_execution()

    assert result.ok is True
    fake_interp.load_graph.assert_called_once_with(entry.graph)
    fake_interp.start_execution.assert_called_once()


def test_start_execution_returns_failure_and_does_not_start():
    entry = _make_entry()
    fake_interp = MagicMock()
    fake_interp.load_graph.side_effect = RuntimeError("bad graph")
    with (
        patch("haybale_haystack.graph_entry.Interpreter", return_value=fake_interp),
        patch("haybale_haystack.graph_entry.get_library_state_container", return_value=MagicMock()),
    ):
        result = entry.start_execution()

    assert result.ok is False
    fake_interp.start_execution.assert_not_called()


def test_start_execution_noop_when_already_executing():
    entry = _make_entry()
    running = MagicMock()
    running.is_executing = True
    entry.interpreter = running
    result = entry.start_execution()
    assert result.ok is True  # already running counts as success

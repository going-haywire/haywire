# tests/execution/test_compile_result.py
import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def test_compile_result_ok_has_no_error():
    from haywire.core.execution.compile_result import CompileResult

    r = CompileResult(ok=True, error=None)
    assert r.ok is True
    assert r.error is None


def test_compile_result_failure_carries_message():
    from haywire.core.execution.compile_result import CompileResult

    r = CompileResult(ok=False, error="Graph validation failed: no event nodes")
    assert r.ok is False
    assert r.error == "Graph validation failed: no event nodes"


def test_compile_result_is_frozen():
    import dataclasses
    from haywire.core.execution.compile_result import CompileResult

    r = CompileResult(ok=True, error=None)
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        r.ok = False  # type: ignore[misc]

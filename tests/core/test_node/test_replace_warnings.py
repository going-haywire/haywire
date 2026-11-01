"""NodeWrapperState.replace_warnings swaps one kind and keeps the rest."""

from haywire.core.node.node_warning import NodeWarning
from haywire.core.node.node_wrapper import NodeWrapperState


def _w(message: str, kind: str) -> NodeWarning:
    return NodeWarning(message=message, source_version=None, kind=kind)


def test_replace_warnings_keeps_other_kinds() -> None:
    state = NodeWrapperState()
    other = _w("compat", "compatibility")
    state.add_warning(other)
    assert state.replace_warnings("model", [_w("a", "model")]) is True
    assert state.replace_warnings("model", [_w("a", "model")]) is False
    assert state.replace_warnings("model", [_w("b", "model"), _w("c", "model")]) is True
    assert [w.message for w in state.warnings] == ["compat", "b", "c"]
    assert state.replace_warnings("model", []) is True
    assert state.warnings == [other]
    assert state.replace_warnings("model", []) is False


def test_wrapper_replace_warnings_locks_and_redraws_on_change_only() -> None:
    import threading

    from haywire.core.node.node_wrapper import NodeWrapper

    wrapper = NodeWrapper.__new__(NodeWrapper)
    wrapper._state = NodeWrapperState()

    class SpyLock:
        def __init__(self) -> None:
            self._inner = threading.RLock()
            self.depth = 0

        def __enter__(self) -> None:
            self._inner.acquire()
            self.depth += 1

        def __exit__(self, *a: object) -> None:
            self.depth -= 1
            self._inner.release()

    lock = SpyLock()
    wrapper._lock = lock  # type: ignore[assignment]
    redraws: list[int] = []
    wrapper.redraw = lambda: redraws.append(lock.depth)  # type: ignore[method-assign]

    assert wrapper.replace_warnings("model", [_w("a", "model")]) is True
    assert wrapper.replace_warnings("model", [_w("a", "model")]) is False
    assert redraws == [0]  # one redraw, issued after the lock was released

"""A save of a helper and the node modules importing it reloads each module once, and fresh (#221).

The file watcher dispatches the files saved within one debounce window as one
batch, whose events share one ``reloaded_modules`` set per registry. These tests
drive a real ``BaseRegistry`` on a real package through the real handler; only
the debounce timer is fired by hand.
"""

from __future__ import annotations

import sys
import threading
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from watchdog.events import FileModifiedEvent

from haywire.core.library import file_watcher
from haywire.core.library.file_watcher import LibraryFileHandler
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry

pytestmark = pytest.mark.unit

_PKG = "reload_batch_pkg"


class _Registry(BaseRegistry[Any]):
    def _class_filter(self, cls):
        return cls.__name__.startswith("Good")

    def _register_class(self, cls, library_identity=None):
        return None

    def _unregister_class(self, registry_key):
        return None


def _write_package(root: Path, value: int) -> None:
    (root / "__init__.py").write_text("")
    (root / "helper.py").write_text(f"VALUE = {value}\n")
    (root / "nodes" / "__init__.py").write_text("")
    for name in ("a", "b"):
        (root / "nodes" / f"{name}.py").write_text(
            f"from {_PKG}.helper import VALUE\n\n\nclass Good{name.upper()}:\n    value = VALUE\n"
        )


@pytest.fixture
def package(tmp_path, monkeypatch):
    root = tmp_path / _PKG
    (root / "nodes").mkdir(parents=True)
    _write_package(root, value=1)
    monkeypatch.syspath_prepend(str(tmp_path))
    # Rewrites within one second would otherwise be served from a stale .pyc.
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    yield root
    for name in [m for m in sys.modules if m == _PKG or m.startswith(_PKG + ".")]:
        del sys.modules[name]


@pytest.fixture
def manual_timers(monkeypatch):
    """The handler's debounce timer, run out by hand on the test thread."""
    started: list[SimpleNamespace] = []

    def make(interval, function, args=None):
        timer = SimpleNamespace(function=function, cancelled=False, start=lambda: None)
        timer.cancel = lambda: setattr(timer, "cancelled", True)
        started.append(timer)
        return timer

    monkeypatch.setattr(file_watcher, "threading", SimpleNamespace(Timer=make, Lock=threading.Lock))

    def fire():
        for timer in [t for t in started if not t.cancelled]:
            timer.cancelled = True
            timer.function()

    return fire


@pytest.fixture
def wired(package, manual_timers):
    identity = LibraryIdentity(label="batch", name="batch", folder_path=str(package), module_name=_PKG)
    registry = _Registry()
    registry.add_folder(str(package / "nodes"), identity)

    reloads: Counter[str] = Counter()
    scan = registry.module_scan_for_classes
    reload_helper = registry._reload_unmanaged_module

    def counting_scan(module_name, *args, **kwargs):
        if kwargs.get("force_reload"):
            reloads[module_name] += 1
        return scan(module_name, *args, **kwargs)

    def counting_reload_helper(module_name, *args, **kwargs):
        reloads[module_name] += 1
        return reload_helper(module_name, *args, **kwargs)

    registry.module_scan_for_classes = counting_scan  # type: ignore[method-assign]
    registry._reload_unmanaged_module = counting_reload_helper  # type: ignore[method-assign]

    handler = LibraryFileHandler()
    handler.add_folder_mapping(str(package / "nodes"), identity, registry, debounce_delay=0.05)
    handler.add_root_fallback(str(package), identity, [registry], debounce_delay=0.05)
    yield SimpleNamespace(handler=handler, reloads=reloads, fire=manual_timers)
    handler.cleanup()


def _save(wired, package: Path, *relative: str) -> None:
    _write_package(package, value=2)
    for path in relative:
        wired.handler.on_modified(FileModifiedEvent(str(package / path)))
    wired.fire()


def _values() -> list[int]:
    return [sys.modules[f"{_PKG}.nodes.a"].GoodA.value, sys.modules[f"{_PKG}.nodes.b"].GoodB.value]


def test_a_helper_saved_with_its_dependents_reloads_each_module_once(wired, package):
    _save(wired, package, "helper.py", "nodes/a.py", "nodes/b.py")

    assert wired.reloads == {f"{_PKG}.helper": 1, f"{_PKG}.nodes.a": 1, f"{_PKG}.nodes.b": 1}
    assert _values() == [2, 2]


def test_a_dependent_reloaded_before_its_helper_is_reloaded_again_after_it(wired, package):
    """Saved in this order, a node module's own event comes first; skipping it at the
    helper's event would leave it holding the helper's old values.
    """
    _save(wired, package, "nodes/a.py", "nodes/b.py", "helper.py")

    assert wired.reloads == {f"{_PKG}.helper": 1, f"{_PKG}.nodes.a": 2, f"{_PKG}.nodes.b": 2}
    assert _values() == [2, 2]


def test_separate_windows_reload_again(wired, package):
    _save(wired, package, "helper.py")
    _save(wired, package, "nodes/a.py")

    assert wired.reloads == {f"{_PKG}.helper": 1, f"{_PKG}.nodes.a": 2, f"{_PKG}.nodes.b": 1}

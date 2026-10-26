"""Hot-reload failures that used to reach only the logger land in the error ledger."""

import sys
import types
from typing import Any, cast

import pytest

from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry
from haywire.core.registry.dependency_graph import DependencyGraph
from haywire.core.registry.events import FileChangeEvent, FileEventType

pytestmark = pytest.mark.unit


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=20)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


def _identity():
    return LibraryIdentity(label="testlib", name="testlib", folder_path="/lib", module_name="testlib")


def _entries(ledger):
    return list(ledger.query().entries)


class _Registry(BaseRegistry[Any]):
    def _class_filter(self, cls):
        if cls.__name__ == "Boom":
            raise RuntimeError("filter exploded")
        return cls.__name__.startswith("Good")

    def _register_class(self, cls, library_identity=None):
        return None

    def _unregister_class(self, registry_key):
        return None


def _event(path="/lib/mod.py"):
    return FileChangeEvent(
        file_path=path, event_type=FileEventType.MODIFIED, library_identity=_identity(), timestamp=0.0
    )


def test_a_failing_registry_subscriber_is_recorded_and_the_batch_continues(ledger):
    reg = _Registry()
    reached = []

    class _Bad:
        def event_dispatcher(self, event):
            raise RuntimeError("subscriber exploded")

    class _Good:
        def event_dispatcher(self, event):
            reached.append(event)

    reg.add_registry_subscriber(cast(Any, _Bad()))
    reg.add_registry_subscriber(cast(Any, _Good()))
    reg._notify_registry_subscribers(_event())

    assert len(reached) == 1
    (entry,) = _entries(ledger)
    assert entry.operation == "Hot reload"
    assert entry.library_identity.label == "testlib"


def test_a_failing_class_filter_is_recorded_and_discovery_continues(ledger, tmp_path, monkeypatch):
    (tmp_path / "reload_boundary_mod.py").write_text("class Boom: pass\nclass GoodOne: pass\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "reload_boundary_mod", raising=False)
    try:
        found, _ = _Registry().module_scan_for_classes(
            "reload_boundary_mod", _identity(), _Registry()._class_filter
        )
    finally:
        sys.modules.pop("reload_boundary_mod", None)

    assert [c.__name__ for c in found] == ["GoodOne"]
    (entry,) = _entries(ledger)
    assert entry.operation == "Hot reload"
    assert entry.error_context["module_name"] == "reload_boundary_mod"


def test_an_unparseable_dependency_source_is_recorded(ledger, tmp_path, monkeypatch):
    src = tmp_path / "broken_dep.py"
    src.write_text("def (:\n")
    fake = types.ModuleType("broken_dep")
    fake.__file__ = str(src)
    monkeypatch.setitem(sys.modules, "broken_dep", fake)

    assert DependencyGraph()._extract_direct_dependencies("broken_dep", ["broken"]) == set()

    (entry,) = _entries(ledger)
    assert entry.operation == "Hot reload"
    assert entry.error_context["module_name"] == "broken_dep"


def test_an_unresolvable_relative_import_is_recorded(ledger, monkeypatch):
    # A non-int level makes the arithmetic raise inside the guarded block.
    assert DependencyGraph()._resolve_relative_import("pkg.mod", "x", "bad") is None  # type: ignore[arg-type]

    (entry,) = _entries(ledger)
    assert entry.operation == "Hot reload"
    assert entry.error_context["module_name"] == "pkg.mod"


def test_a_helper_reload_failure_without_a_source_event_is_recorded(ledger, monkeypatch):
    reg = _Registry()
    broken = types.ModuleType("helper_boundary_mod")
    monkeypatch.setitem(sys.modules, "helper_boundary_mod", broken)  # no spec: reload raises

    reg._reload_unmanaged_module("helper_boundary_mod", _identity(), None)

    (entry,) = _entries(ledger)
    assert entry.operation == "Hot reload"
    assert entry.error_context["module_name"] == "helper_boundary_mod"

"""``ComponentRegistry`` is the kind-agnostic half of the registry contract."""

import inspect

import pytest

pytestmark = pytest.mark.unit


class _Element:
    """Minimal ``RegisteredClass``: a class_identity with a ``hidden`` flag."""

    class class_identity:  # noqa: N801 - stands in for a BaseIdentity
        hidden = False
        label = "Element"

    class class_library:  # noqa: N801
        label = "testlib"


class _HiddenElement(_Element):
    class class_identity:  # noqa: N801
        hidden = True
        label = "Hidden"


def _identity():
    """A throwaway LibraryIdentity — LifeCycleEvent requires one."""
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(label="testlib")


def _event(registry_key="k"):
    """A CLASS_ADDED event. ``affected_class`` and ``library_identity`` are required."""
    from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType

    return LifeCycleEvent(
        registry_key=registry_key,
        event_type=LifeCycleEventType.CLASS_ADDED,
        affected_class=_Element,
        library_identity=_identity(),
    )


def _registry():
    """A concrete ComponentRegistry with the folder abstracts stubbed out."""
    from haywire.core.registry.component import ComponentRegistry

    class _Fake(ComponentRegistry):
        def add_folder(self, folder_path, library_identity, exclude_patterns=None):
            self._folder_to_library[folder_path] = library_identity

        def remove_folder(self, folder_path, library_identity, exclude_patterns=None):
            del self._folder_to_library[folder_path]

        def event_dispatcher(self, event):
            return None

    return _Fake()


def test_read_api_reports_registered_elements():
    reg = _registry()
    assert reg.get("k") is None
    assert reg.has("k") is False

    reg._classes["k"] = _Element
    assert reg.get("k") is _Element
    assert reg.has("k") is True
    assert reg.list_names() == ["k"]


def test_list_visible_names_drops_hidden_elements():
    reg = _registry()
    reg._classes["shown"] = _Element
    reg._classes["hidden"] = _HiddenElement

    assert reg.list_visible_names() == ["shown"]
    assert set(reg.list_names()) == {"shown", "hidden"}


def test_queued_events_reach_batch_subscribers_then_drain():
    from haywire.core.registry.lifecycle_event import LifeCycleEvent

    reg = _registry()
    seen: list[list[LifeCycleEvent]] = []
    reg.add_batch_event_subscriber(lambda batch: seen.append(list(batch)))

    reg._queue_lifecycle_event(_event())
    reg._notify_batch_event_subscribers()

    assert [e.registry_key for e in seen[0]] == ["k"]
    assert reg._lifecycle_event_queue == []


def test_last_event_survives_the_queue_drain():
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    reg = _registry()
    reg._queue_lifecycle_event(_event())
    reg._notify_batch_event_subscribers()

    assert reg.get_lastevent("k").event_type is LifeCycleEventType.CLASS_ADDED
    assert reg.get_lastevent("absent") is None


def test_a_subscriber_that_raises_does_not_stop_the_others():
    """The error branch logs ``event.file_path``, so pass a real event."""
    from haywire.core.registry.events import FileChangeEvent, FileEventType

    reg = _registry()
    reached = []

    class _Boom:
        def event_dispatcher(self, event):
            raise RuntimeError("boom")

    class _Ok:
        def event_dispatcher(self, event):
            reached.append(event)

    reg.add_registry_subscriber(_Boom())
    reg.add_registry_subscriber(_Ok())
    reg._notify_registry_subscribers(
        FileChangeEvent(
            file_path="/x.py",
            event_type=FileEventType.MODIFIED,
            library_identity=_identity(),
            timestamp=0.0,
        )
    )

    assert len(reached) == 1


def test_base_is_free_of_module_reload_machinery():
    """The point of the split: no sys.modules/importlib on the shared base.

    A document registry inherits this class, and must not carry a reload
    path that only makes sense for Python modules. Checked against the parsed
    code rather than the text, so the docstring may still name what it excludes.
    """
    import ast

    from haywire.core.registry import component

    tree = ast.parse(inspect.getsource(component))
    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.Import):
            names = [alias.name for alias in stmt.names]
        elif isinstance(stmt, ast.ImportFrom):
            names = [stmt.module or ""] + [alias.name for alias in stmt.names]
        else:
            continue
        assert not [n for n in names if n in ("sys", "importlib") or "dependency_graph" in n], names

    # Docstrings are not code; strip them before scanning for attribute access.
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            assert f"{node.value.id}.{node.attr}" != "sys.modules"


def test_folder_registration_is_abstract():
    from haywire.core.registry.component import ComponentRegistry

    assert getattr(ComponentRegistry.add_folder, "__isabstractmethod__", False)
    assert getattr(ComponentRegistry.remove_folder, "__isabstractmethod__", False)


def test_baseregistry_still_satisfies_the_contract():
    """The class-backed registry is one implementation of the new base."""
    from haywire.core.registry.base import BaseRegistry
    from haywire.core.registry.component import ComponentRegistry

    assert issubclass(BaseRegistry, ComponentRegistry)
    for name in ("get", "has", "list_names", "list_visible_names", "get_lastevent"):
        assert hasattr(BaseRegistry, name)

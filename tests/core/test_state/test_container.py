"""Unit tests for LibraryStateContainer."""

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state import AppState
from haywire.core.state.container import LibraryStateContainer
from haywire.core.state.registry import LibraryStateRegistry


def make_lib_identity(lib_id: str = "midi") -> LibraryIdentity:
    return LibraryIdentity(
        id=lib_id,
        label=lib_id.capitalize(),
        version="0.0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        dependencies=[],
        tags=[],
        module_name=f"haybale_{lib_id}",
        folder_path="",
    )


def make_added_event(cls: type, lib_id: LibraryIdentity) -> LifeCycleEvent:
    return LifeCycleEvent(
        registry_key=cls.class_identity.registry_key,
        event_type=LifeCycleEventType.CLASS_ADDED,
        affected_class=cls,
        library_identity=lib_id,
    )


def make_removed_event(cls: type, lib_id: LibraryIdentity) -> LifeCycleEvent:
    return LifeCycleEvent(
        registry_key=cls.class_identity.registry_key,
        event_type=LifeCycleEventType.CLASS_REMOVED,
        affected_class=cls,
        library_identity=lib_id,
    )


class TestLibraryStateContainer:
    def test_class_added_event_creates_instance_and_calls_on_enable(self):
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(LibraryStateRegistry())
        lib_id = make_lib_identity()
        container._mark_library_enabled(lib_id.id)

        # Subscribe container to registry events.
        reg.add_batch_event_subscriber(container.on_lifecycle_events)

        # Register the class — this would normally trigger event emission, but
        # _register_class doesn't emit by itself. Drive the container directly.
        reg._register_class(MyState, lib_id)
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])

        assert MyState in container
        assert isinstance(container[MyState], MyState)
        assert calls == ["enable"]

    def test_class_removed_event_calls_on_disable_and_drops_instance(self):
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

            def on_disable(self) -> None:
                calls.append("disable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(LibraryStateRegistry())
        lib_id = make_lib_identity()
        container._mark_library_enabled(lib_id.id)

        reg._register_class(MyState, lib_id)
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])

        assert MyState not in container
        assert calls == ["enable", "disable"]

    def test_missing_on_enable_is_fine(self):
        """LibraryStates without on_enable are still instantiated."""

        class NoHooks(AppState):
            pass

        container = LibraryStateContainer(LibraryStateRegistry())
        lib_id = make_lib_identity()
        container._mark_library_enabled(lib_id.id)
        reg = LibraryStateRegistry()
        reg._register_class(NoHooks, lib_id)

        # Should not raise.
        container.on_lifecycle_events([make_added_event(NoHooks, lib_id)])
        assert NoHooks in container

    def test_getitem_raises_keyerror_when_not_registered(self):
        from haywire.core.state.identity import LibraryStateClassIdentity

        class Missing(AppState):
            pass

        # Stamp class_identity so the lookup goes through to the dict —
        # the dict is empty, so we get the informative KeyError. (Without
        # class_identity, the failure mode is AttributeError, which is
        # the documented "caller passed an unregistered class" contract
        # breach, not the case this test is exercising.)
        Missing.class_identity = LibraryStateClassIdentity(
            class_name="Missing",
            module=__name__,
            registry_id="Missing",
            registry_key="test:state:Missing",
            label="Missing",
        )

        container = LibraryStateContainer(LibraryStateRegistry())
        with pytest.raises(KeyError):
            _ = container[Missing]

    def test_get_returns_none_when_not_registered(self):
        from haywire.core.state.identity import LibraryStateClassIdentity

        class Missing(AppState):
            pass

        Missing.class_identity = LibraryStateClassIdentity(
            class_name="Missing",
            module=__name__,
            registry_id="Missing",
            registry_key="test:state:Missing",
            label="Missing",
        )

        container = LibraryStateContainer(LibraryStateRegistry())
        assert container.get(Missing) is None

    def test_class_reloaded_event_swaps_instance_with_disable_then_enable(self):
        """Hot-reload = disable old + enable new. Old class's on_disable fires
        before the new class is instantiated."""
        calls: list[str] = []

        class V1(AppState):
            def on_enable(self) -> None:
                calls.append("v1-enable")

            def on_disable(self) -> None:
                calls.append("v1-disable")

        # Simulate the registry's behaviour: emit a CLASS_RELOADED event whose
        # affected_class is the NEW version.
        class V2(AppState):
            def on_enable(self) -> None:
                calls.append("v2-enable")

            def on_disable(self) -> None:
                calls.append("v2-disable")

        # Hand-build matching identities so the same registry_key lands on both
        # — that's the hot-reload contract (same key, new class object).
        from haywire.core.state.identity import LibraryStateClassIdentity

        ident = LibraryStateClassIdentity(
            class_name="V",
            module=__name__,
            registry_id="V",
            registry_key="midi:state:V",
            label="V",
        )
        V1.class_identity = ident
        V2.class_identity = ident

        container = LibraryStateContainer(LibraryStateRegistry())
        lib_id = make_lib_identity()
        container._mark_library_enabled(lib_id.id)

        # Initial enable.
        container.on_lifecycle_events([make_added_event(V1, lib_id)])
        assert calls == ["v1-enable"]

        # Hot-reload event: registry_key matches, affected_class is now V2.
        reload_event = LifeCycleEvent(
            registry_key="midi:state:V",
            event_type=LifeCycleEventType.CLASS_RELOADED,
            affected_class=V2,
            library_identity=lib_id,
        )
        container.on_lifecycle_events([reload_event])

        assert calls == ["v1-enable", "v1-disable", "v2-enable"]
        # The instance is now of the new class.
        assert isinstance(container[V2], V2)


class TestEnabledLibraryIdsFilter:
    """The container's on_lifecycle_events filter drops events for libraries
    it has not been told about via on_library_enabled / _mark_library_enabled.
    This prevents the M1 load-order race: state classes from a library being
    instantiated mid-enable, before the rest of its components (types, nodes)
    are registered."""

    def test_event_for_unknown_library_is_dropped(self):
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(LibraryStateRegistry())
        lib_id = make_lib_identity("unmarked")
        reg._register_class(MyState, lib_id)
        # Deliberately DO NOT call _mark_library_enabled.

        container.on_lifecycle_events([make_added_event(MyState, lib_id)])

        assert MyState not in container
        assert calls == []

    def test_event_for_marked_library_is_processed(self):
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(LibraryStateRegistry())
        lib_id = make_lib_identity("marked")
        reg._register_class(MyState, lib_id)
        container._mark_library_enabled(lib_id.id)

        container.on_lifecycle_events([make_added_event(MyState, lib_id)])

        assert MyState in container
        assert calls == ["enable"]

    def test_filter_isolates_libraries_in_same_batch(self):
        """A single on_lifecycle_events call carrying events from multiple
        libraries — only events for marked libraries are processed."""
        calls: list[str] = []

        class MarkedState(AppState):
            def on_enable(self) -> None:
                calls.append("marked")

        class UnmarkedState(AppState):
            def on_enable(self) -> None:
                calls.append("unmarked")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(LibraryStateRegistry())
        marked = make_lib_identity("marked")
        unmarked = make_lib_identity("unmarked")
        reg._register_class(MarkedState, marked)
        reg._register_class(UnmarkedState, unmarked)
        container._mark_library_enabled(marked.id)

        container.on_lifecycle_events(
            [
                make_added_event(MarkedState, marked),
                make_added_event(UnmarkedState, unmarked),
            ]
        )

        assert MarkedState in container
        assert UnmarkedState not in container
        assert calls == ["marked"]


class TestOnLibraryEnabledCatchUp:
    """on_library_enabled queries the state registry for classes belonging to
    the library and dispatches synthetic CLASS_ADDED events for each — the
    catch-up step that runs after a library finishes enabling."""

    def test_catch_up_instantiates_app_state_classes(self):
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("midi")
        reg._register_class(MyState, lib_id)

        # Stand-in BaseLibrary: only `identity` is read.
        class FakeLibrary:
            identity = lib_id

        container.on_library_enabled(FakeLibrary())

        assert MyState in container
        assert calls == ["enable"]

    def test_catch_up_marks_library_enabled_for_subsequent_events(self):
        """After catch-up, hot-reload events for the library pass the filter."""
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

            def on_disable(self) -> None:
                calls.append("disable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("midi")
        reg._register_class(MyState, lib_id)

        class FakeLibrary:
            identity = lib_id

        container.on_library_enabled(FakeLibrary())
        assert calls == ["enable"]

        # A subsequent CLASS_REMOVED event for the same library passes the
        # filter (the catch-up added the library id to _enabled_library_ids).
        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])
        assert calls == ["enable", "disable"]

    def test_catch_up_with_no_classes_is_a_noop_but_marks_library(self):
        """A library that registered no state classes still gets its id
        added to _enabled_library_ids — so any future hot-reload events
        for it pass the filter."""
        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("stateless")

        class FakeLibrary:
            identity = lib_id

        container.on_library_enabled(FakeLibrary())

        assert lib_id.id in container._enabled_library_ids

    def test_catch_up_is_idempotent_for_already_added_classes(self):
        """Calling on_library_enabled twice doesn't double-fire on_enable."""
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("midi")
        reg._register_class(MyState, lib_id)

        class FakeLibrary:
            identity = lib_id

        container.on_library_enabled(FakeLibrary())
        container.on_library_enabled(FakeLibrary())

        assert calls == ["enable"]

    def test_catch_up_only_processes_classes_for_the_given_library(self):
        """When two libraries have state classes in the registry, catch-up
        for one must not touch the other's classes."""
        calls: list[str] = []

        class MidiState(AppState):
            def on_enable(self) -> None:
                calls.append("midi")

        class AudioState(AppState):
            def on_enable(self) -> None:
                calls.append("audio")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        midi = make_lib_identity("midi")
        audio = make_lib_identity("audio")
        reg._register_class(MidiState, midi)
        reg._register_class(AudioState, audio)

        class MidiLib:
            identity = midi

        container.on_library_enabled(MidiLib())

        assert MidiState in container
        assert AudioState not in container
        assert calls == ["midi"]


class TestOnLibraryDisabled:
    """on_library_disabled drops the library id from _enabled_library_ids
    so subsequent events for the library are filtered out — including the
    CLASS_ADDED events fired during a re-enable, which must be ignored so
    the catch-up step is what re-instantiates state classes."""

    def test_disabled_library_id_is_dropped_from_filter_set(self):
        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("midi")

        class FakeLibrary:
            identity = lib_id

        container.on_library_enabled(FakeLibrary())
        assert lib_id.id in container._enabled_library_ids

        container.on_library_disabled(FakeLibrary())
        assert lib_id.id not in container._enabled_library_ids

    def test_events_after_disable_are_dropped(self):
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("midi")
        reg._register_class(MyState, lib_id)

        class FakeLibrary:
            identity = lib_id

        container.on_library_enabled(FakeLibrary())
        assert calls == ["enable"]

        # The container's _add_app_class is idempotent, so we tear down
        # first to make the regression visible.
        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])
        container.on_library_disabled(FakeLibrary())

        # Now any subsequent event for this library must be dropped.
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        assert MyState not in container
        # on_enable did NOT fire again.
        assert calls == ["enable"]

    def test_disable_then_reenable_runs_catch_up_again(self):
        """The full disable→re-enable cycle: state classes get re-instantiated
        by the catch-up step, not by the per-folder CLASS_ADDED events fired
        during the re-enable's _attach_to_registries."""
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

            def on_disable(self) -> None:
                calls.append("disable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("midi")
        reg._register_class(MyState, lib_id)

        class FakeLibrary:
            identity = lib_id

        # First enable.
        container.on_library_enabled(FakeLibrary())
        assert calls == ["enable"]

        # Disable: CLASS_REMOVED event fires (filter still admits it because
        # the library is still in _enabled_library_ids at that moment), then
        # the post-disable callback drops the library from the set.
        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])
        container.on_library_disabled(FakeLibrary())
        assert calls == ["enable", "disable"]
        assert MyState not in container

        # Re-enable. In production, the CLASS_ADDED events fire during
        # _attach_to_registries — the filter drops them (library no longer
        # marked enabled). Then on_library_enabled runs catch-up and
        # re-instantiates.
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        # Filter dropped the event; nothing yet.
        assert MyState not in container
        assert calls == ["enable", "disable"]

        # Now the catch-up runs (post-enable callback fires).
        container.on_library_enabled(FakeLibrary())
        assert MyState in container
        assert calls == ["enable", "disable", "enable"]

    def test_disable_of_unknown_library_is_a_noop(self):
        """on_library_disabled is idempotent — calling with an id not in
        the set is a no-op rather than an error."""
        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("never-enabled")

        class FakeLibrary:
            identity = lib_id

        # Should not raise.
        container.on_library_disabled(FakeLibrary())
        assert lib_id.id not in container._enabled_library_ids


class TestBindToLifecycle:
    """bind_to_lifecycle subscribes the container to the three event
    channels it reacts to. Tests use mock library_registries because the
    real LibraryRegistry needs a full DI environment."""

    def test_subscribes_to_state_registry_batch_events(self):
        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        from unittest.mock import MagicMock

        library_registry = MagicMock()
        container.bind_to_lifecycle(library_registry)

        assert container.on_lifecycle_events in reg._batch_event_subscribers

    def test_registers_library_enabled_callback(self):
        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        from unittest.mock import MagicMock

        library_registry = MagicMock()
        container.bind_to_lifecycle(library_registry)

        library_registry.add_library_enabled_callback.assert_called_once_with(container.on_library_enabled)

    def test_registers_library_disabled_callback(self):
        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        from unittest.mock import MagicMock

        library_registry = MagicMock()
        container.bind_to_lifecycle(library_registry)

        library_registry.add_library_disabled_callback.assert_called_once_with(container.on_library_disabled)

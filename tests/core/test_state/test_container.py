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
    def test_class_added_event_creates_instance_without_on_enable(self):
        """CLASS_ADDED only instantiates — on_enable is deferred to on_library_enabled."""
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity()

        reg._register_class(MyState, lib_id)
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])

        # Instance exists and is reachable immediately.
        assert MyState in container
        assert isinstance(container[MyState], MyState)
        # on_enable has NOT fired yet — deferred to on_library_enabled.
        assert calls == []

    def test_on_library_enabled_calls_on_enable_on_existing_instance(self):
        """on_library_enabled is the second phase: it calls on_enable on the
        already-instantiated instance."""
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity()
        reg._register_class(MyState, lib_id)

        # Phase 1: instantiate.
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        assert calls == []

        # Phase 2: enable.
        class FakeLibrary:
            identity = lib_id

        container.on_library_enabled(FakeLibrary())
        assert calls == ["enable"]

    def test_class_removed_event_calls_on_disable_and_drops_instance(self):
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

            def on_disable(self) -> None:
                calls.append("disable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity()
        container._mark_library_enabled(lib_id.id)

        reg._register_class(MyState, lib_id)
        # Phase 1+2 together (library already marked enabled).
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])

        class FakeLibrary:
            identity = lib_id

        container.on_library_enabled(FakeLibrary())
        assert calls == ["enable"]

        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])

        assert MyState not in container
        assert calls == ["enable", "disable"]

    def test_missing_on_enable_is_fine(self):
        """LibraryStates without on_enable are still instantiated."""

        class NoHooks(AppState):
            pass

        container = LibraryStateContainer(LibraryStateRegistry())
        lib_id = make_lib_identity()
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
        before the new class is instantiated. CLASS_RELOADED calls on_enable
        immediately because the library is already fully enabled."""
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

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity()

        reg._register_class(V1, lib_id)

        # Phase 1: instantiate V1.
        container.on_lifecycle_events([make_added_event(V1, lib_id)])
        assert calls == []

        # Phase 2: enable V1 (library fully loaded).
        class FakeLibrary:
            identity = lib_id

        container.on_library_enabled(FakeLibrary())
        assert calls == ["v1-enable"]

        # Hot-reload event: CLASS_RELOADED fires on an already-enabled library,
        # so on_enable runs immediately for the new instance.
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
    """_enabled_library_ids gates on_enable calls, not instantiation.

    CLASS_ADDED always instantiates (instance reachable immediately via
    ctx.app_data). on_enable fires in on_library_enabled, and only then
    does the library id enter _enabled_library_ids — so CLASS_REMOVED /
    CLASS_RELOADED events for not-yet-fully-enabled libraries are dropped."""

    def test_class_added_for_unknown_library_still_instantiates(self):
        """CLASS_ADDED instantiates regardless of _enabled_library_ids —
        the instance must be reachable before on_library_enabled fires."""
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("unmarked")
        reg._register_class(MyState, lib_id)
        # Deliberately DO NOT call _mark_library_enabled.

        container.on_lifecycle_events([make_added_event(MyState, lib_id)])

        # Instance exists — the two-phase model guarantees this.
        assert MyState in container
        # on_enable has NOT fired — library not yet marked enabled.
        assert calls == []

    def test_on_enable_fires_only_after_on_library_enabled(self):
        """on_enable is deferred: CLASS_ADDED instantiates, on_library_enabled enables."""
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("marked")
        reg._register_class(MyState, lib_id)

        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        assert MyState in container
        assert calls == []  # not yet

        class FakeLibrary:
            identity = lib_id

        container.on_library_enabled(FakeLibrary())
        assert calls == ["enable"]  # now

    def test_class_removed_for_unknown_library_is_dropped(self):
        """CLASS_REMOVED for a library not in _enabled_library_ids is ignored —
        there is nothing to tear down for a not-yet-enabled library."""
        calls: list[str] = []

        class MyState(AppState):
            def on_disable(self) -> None:
                calls.append("disable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("unmarked")
        reg._register_class(MyState, lib_id)

        # Instantiate but do NOT enable.
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        assert MyState in container

        # CLASS_REMOVED without the library being marked enabled — dropped.
        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])
        # Instance is still there (event was dropped).
        assert MyState in container
        assert calls == []

    def test_class_added_from_two_libraries_both_instantiate(self):
        """CLASS_ADDED from both a marked and an unmarked library both create
        instances — instantiation is unconditional."""
        calls: list[str] = []

        class MarkedState(AppState):
            def on_enable(self) -> None:
                calls.append("marked")

        class UnmarkedState(AppState):
            def on_enable(self) -> None:
                calls.append("unmarked")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        marked = make_lib_identity("marked")
        unmarked = make_lib_identity("unmarked")
        reg._register_class(MarkedState, marked)
        reg._register_class(UnmarkedState, unmarked)

        container.on_lifecycle_events(
            [
                make_added_event(MarkedState, marked),
                make_added_event(UnmarkedState, unmarked),
            ]
        )

        # Both instantiated, neither enabled yet.
        assert MarkedState in container
        assert UnmarkedState in container
        assert calls == []

        # Enabling only the marked library calls on_enable only for it.
        class FakeMarked:
            identity = marked

        container.on_library_enabled(FakeMarked())
        assert calls == ["marked"]
        assert UnmarkedState in container  # still there, just not enabled


class TestOnLibraryEnabledCatchUp:
    """on_library_enabled calls on_enable on already-instantiated state
    instances and marks the library id so CLASS_REMOVED / CLASS_RELOADED
    events for it pass the filter in on_lifecycle_events."""

    def test_on_library_enabled_enables_instantiated_classes(self):
        """Two-phase: CLASS_ADDED instantiates, on_library_enabled enables."""
        calls: list[str] = []

        class MyState(AppState):
            def on_enable(self) -> None:
                calls.append("enable")

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("midi")
        reg._register_class(MyState, lib_id)

        # Phase 1: CLASS_ADDED instantiates (fired during library.enable()).
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        assert MyState in container
        assert calls == []

        class FakeLibrary:
            identity = lib_id

        # Phase 2: on_library_enabled enables (fired after library.enable() returns).
        container.on_library_enabled(FakeLibrary())
        assert calls == ["enable"]

    def test_on_library_enabled_marks_library_for_subsequent_events(self):
        """After on_library_enabled, CLASS_REMOVED / CLASS_RELOADED pass the filter."""
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

        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        container.on_library_enabled(FakeLibrary())
        assert calls == ["enable"]

        # CLASS_REMOVED now passes the filter.
        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])
        assert calls == ["enable", "disable"]

    def test_on_library_enabled_with_no_classes_still_marks_library(self):
        """A library with no state classes still gets its id added to
        _enabled_library_ids so future CLASS_RELOADED events pass the filter."""
        reg = LibraryStateRegistry()
        container = LibraryStateContainer(reg)
        lib_id = make_lib_identity("stateless")

        class FakeLibrary:
            identity = lib_id

        container.on_library_enabled(FakeLibrary())

        assert lib_id.id in container._enabled_library_ids

    def test_on_library_enabled_twice_does_not_double_fire_on_enable(self):
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

        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        container.on_library_enabled(FakeLibrary())
        container.on_library_enabled(FakeLibrary())

        assert calls == ["enable"]

    def test_on_library_enabled_only_enables_its_own_library_classes(self):
        """Enabling one library does not call on_enable for another library's classes."""
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

        # Both instantiated via CLASS_ADDED.
        container.on_lifecycle_events([make_added_event(MidiState, midi)])
        container.on_lifecycle_events([make_added_event(AudioState, audio)])

        class MidiLib:
            identity = midi

        # Only midi library enabled.
        container.on_library_enabled(MidiLib())

        assert MidiState in container
        assert AudioState in container  # instantiated, just not enabled
        assert calls == ["midi"]


class TestOnLibraryDisabled:
    """on_library_disabled drops the library id from _enabled_library_ids
    so CLASS_REMOVED / CLASS_RELOADED events for the library are subsequently
    filtered out."""

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

    def test_class_removed_after_disable_is_dropped(self):
        """CLASS_REMOVED after on_library_disabled is filtered — nothing to tear
        down for a disabled library (instances already removed by the CLASS_REMOVED
        that fired before on_library_disabled)."""
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

        # Full enable cycle.
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        container.on_library_enabled(FakeLibrary())
        assert calls == ["enable"]

        # Disable: CLASS_REMOVED fires while library is still marked enabled,
        # then on_library_disabled drops the id.
        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])
        container.on_library_disabled(FakeLibrary())
        assert calls == ["enable", "disable"]
        assert MyState not in container

        # A second CLASS_REMOVED (spurious) is now dropped.
        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])
        assert calls == ["enable", "disable"]  # no extra disable

    def test_disable_then_reenable_two_phase(self):
        """Full disable → re-enable cycle using the two-phase model.

        Re-enable sequence in production:
          1. library.enable() → _attach_to_registries() fires CLASS_ADDED
             → instance re-created immediately (phase 1).
          2. _fire_library_enabled() → on_library_enabled() calls on_enable
             (phase 2).
        """
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

        # First enable — two phases.
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        container.on_library_enabled(FakeLibrary())
        assert calls == ["enable"]

        # Disable.
        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])
        container.on_library_disabled(FakeLibrary())
        assert calls == ["enable", "disable"]
        assert MyState not in container

        # Re-enable — phase 1: CLASS_ADDED re-instantiates immediately.
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        assert MyState in container  # instance exists
        assert calls == ["enable", "disable"]  # on_enable not yet

        # Re-enable — phase 2: on_library_enabled calls on_enable.
        container.on_library_enabled(FakeLibrary())
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

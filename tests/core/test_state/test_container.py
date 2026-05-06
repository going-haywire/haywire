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
        container = LibraryStateContainer()
        lib_id = make_lib_identity()

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
        container = LibraryStateContainer()
        lib_id = make_lib_identity()

        reg._register_class(MyState, lib_id)
        container.on_lifecycle_events([make_added_event(MyState, lib_id)])
        container.on_lifecycle_events([make_removed_event(MyState, lib_id)])

        assert MyState not in container
        assert calls == ["enable", "disable"]

    def test_missing_on_enable_is_fine(self):
        """LibraryStates without on_enable are still instantiated."""

        class NoHooks(AppState):
            pass

        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg = LibraryStateRegistry()
        reg._register_class(NoHooks, lib_id)

        # Should not raise.
        container.on_lifecycle_events([make_added_event(NoHooks, lib_id)])
        assert NoHooks in container

    def test_getitem_raises_keyerror_when_not_registered(self):
        class Missing(AppState):
            pass

        container = LibraryStateContainer()
        with pytest.raises(KeyError):
            _ = container[Missing]

    def test_get_returns_none_when_not_registered(self):
        class Missing(AppState):
            pass

        container = LibraryStateContainer()
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

        container = LibraryStateContainer()
        lib_id = make_lib_identity()

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

"""Unit tests for the AppDataNamespace proxy."""

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state import (
    AppState,
    LibraryStateContainer,
    LibraryStateRegistry,
)
from haywire.core.state.data_namespace import AppDataNamespace


def make_lib_identity() -> LibraryIdentity:
    return LibraryIdentity(
        id="midi",
        label="Midi",
        version="0.0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        dependencies=[],
        tags=[],
        module_name="haybale_midi",
        folder_path="",
    )


class TestAppDataNamespace:
    def test_getitem_returns_instance(self):
        class MidiPool(AppState):
            def __init__(self) -> None:
                self.devices: list[str] = ["dev0"]

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg._register_class(MidiPool, lib_id)
        container.on_lifecycle_events(
            [
                LifeCycleEvent(
                    registry_key=MidiPool.class_identity.registry_key,
                    event_type=LifeCycleEventType.CLASS_ADDED,
                    affected_class=MidiPool,
                    library_identity=lib_id,
                )
            ]
        )

        ns = AppDataNamespace(container)
        result = ns[MidiPool]
        assert isinstance(result, MidiPool)
        assert result.devices == ["dev0"]

    def test_getitem_raises_for_unregistered_class(self):
        class NotRegistered(AppState):
            pass

        ns = AppDataNamespace(LibraryStateContainer())
        with pytest.raises(KeyError):
            _ = ns[NotRegistered]

    def test_get_returns_none_for_unregistered_class(self):
        class NotRegistered(AppState):
            pass

        ns = AppDataNamespace(LibraryStateContainer())
        assert ns.get(NotRegistered) is None

    def test_live_lookup_after_swap(self):
        """Each access reads the current container state — no caching."""
        from haywire.core.state.identity import LibraryStateClassIdentity

        class V1(AppState):
            tag = "v1"

        class V2(AppState):
            tag = "v2"

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
        ns = AppDataNamespace(container)

        container.on_lifecycle_events(
            [
                LifeCycleEvent(
                    registry_key="midi:state:V",
                    event_type=LifeCycleEventType.CLASS_ADDED,
                    affected_class=V1,
                    library_identity=lib_id,
                )
            ]
        )
        assert ns[V1].tag == "v1"

        # Hot-reload: V2 replaces V1 under the same registry_key.
        container.on_lifecycle_events(
            [
                LifeCycleEvent(
                    registry_key="midi:state:V",
                    event_type=LifeCycleEventType.CLASS_RELOADED,
                    affected_class=V2,
                    library_identity=lib_id,
                )
            ]
        )
        # V1 is no longer in the container.
        assert ns.get(V1) is None
        # New access via V2 returns the new instance.
        assert ns[V2].tag == "v2"

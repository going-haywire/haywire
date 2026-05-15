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
                super().__init__()
                self.devices: list[str] = ["dev0"]

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(LibraryStateRegistry())
        lib_id = make_lib_identity()
        container._mark_library_enabled(lib_id.id)
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
        from haywire.core.state.identity import LibraryStateClassIdentity

        class NotRegistered(AppState):
            pass

        # Stamp class_identity so the lookup goes through to the dict.
        NotRegistered.class_identity = LibraryStateClassIdentity(
            class_name="NotRegistered",
            module=__name__,
            registry_id="NotRegistered",
            registry_key="test:state:NotRegistered",
            label="NotRegistered",
        )

        ns = AppDataNamespace(LibraryStateContainer(LibraryStateRegistry()))
        with pytest.raises(KeyError):
            _ = ns[NotRegistered]

    def test_get_returns_none_for_unregistered_class(self):
        from haywire.core.state.identity import LibraryStateClassIdentity

        class NotRegistered(AppState):
            pass

        NotRegistered.class_identity = LibraryStateClassIdentity(
            class_name="NotRegistered",
            module=__name__,
            registry_id="NotRegistered",
            registry_key="test:state:NotRegistered",
            label="NotRegistered",
        )

        ns = AppDataNamespace(LibraryStateContainer(LibraryStateRegistry()))
        assert ns.get(NotRegistered) is None

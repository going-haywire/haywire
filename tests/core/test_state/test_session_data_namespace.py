"""Unit tests for SessionDataNamespace — the per-session typed proxy."""

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state import (
    LibraryStateContainer,
    LibraryStateRegistry,
    SessionState,
)
from haywire.core.state.data_namespace import SessionDataNamespace


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


class TestSessionDataNamespace:
    def test_getitem_returns_per_session_instance(self):
        class TimelineCursor(SessionState):
            position = 0.0

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(LibraryStateRegistry())
        lib_id = make_lib_identity()
        container._mark_library_enabled(lib_id.id)
        reg._register_class(TimelineCursor, lib_id)
        container.on_lifecycle_events(
            [
                LifeCycleEvent(
                    registry_key=TimelineCursor.class_identity.registry_key,
                    event_type=LifeCycleEventType.CLASS_ADDED,
                    affected_class=TimelineCursor,
                    library_identity=lib_id,
                )
            ]
        )
        container.attach_session("s1")
        container.attach_session("s2")

        ns_s1 = SessionDataNamespace(container, "s1")
        ns_s2 = SessionDataNamespace(container, "s2")

        assert isinstance(ns_s1[TimelineCursor], TimelineCursor)
        assert isinstance(ns_s2[TimelineCursor], TimelineCursor)
        assert ns_s1[TimelineCursor] is not ns_s2[TimelineCursor]
        assert ns_s1[TimelineCursor].session_id == "s1"
        assert ns_s2[TimelineCursor].session_id == "s2"

    def test_getitem_raises_keyerror_for_unregistered(self):
        from haywire.core.state.identity import LibraryStateClassIdentity

        class NotRegistered(SessionState):
            pass

        NotRegistered.class_identity = LibraryStateClassIdentity(
            class_name="NotRegistered",
            module=__name__,
            registry_id="NotRegistered",
            registry_key="test:state:NotRegistered_a",
            label="NotRegistered",
        )

        ns = SessionDataNamespace(LibraryStateContainer(LibraryStateRegistry()), "anysid")
        with pytest.raises(KeyError):
            _ = ns[NotRegistered]

    def test_get_returns_none_for_missing(self):
        from haywire.core.state.identity import LibraryStateClassIdentity

        class NotRegistered(SessionState):
            pass

        NotRegistered.class_identity = LibraryStateClassIdentity(
            class_name="NotRegistered",
            module=__name__,
            registry_id="NotRegistered",
            registry_key="test:state:NotRegistered_b",
            label="NotRegistered",
        )

        ns = SessionDataNamespace(LibraryStateContainer(LibraryStateRegistry()), "anysid")
        assert ns.get(NotRegistered) is None

    def test_contains_reflects_per_session_membership(self):
        class Cursor(SessionState):
            pass

        reg = LibraryStateRegistry()
        container = LibraryStateContainer(LibraryStateRegistry())
        lib_id = make_lib_identity()
        container._mark_library_enabled(lib_id.id)
        reg._register_class(Cursor, lib_id)
        container.on_lifecycle_events(
            [
                LifeCycleEvent(
                    registry_key=Cursor.class_identity.registry_key,
                    event_type=LifeCycleEventType.CLASS_ADDED,
                    affected_class=Cursor,
                    library_identity=lib_id,
                )
            ]
        )
        container.attach_session("s1")

        ns_s1 = SessionDataNamespace(container, "s1")
        ns_s2 = SessionDataNamespace(container, "s2")  # not attached
        assert Cursor in ns_s1
        assert Cursor not in ns_s2

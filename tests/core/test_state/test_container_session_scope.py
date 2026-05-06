"""Unit tests for LibraryStateContainer's two-scope behavior.

Covers:
  - AppState classes still work as before (regression).
  - SessionState classes are dispatched to per-session storage.
  - `attach_session(sid)` instantiates one of every registered SessionState
    class for that session, calling on_enable each time, and stamping session_id.
  - `detach_session(sid)` calls on_disable on every per-session instance and
    drops them.
  - CLASS_ADDED for a SessionState class (while sessions are already attached)
    fans out — one instance per known session.
  - CLASS_REMOVED for a SessionState class drops every per-session instance,
    calling on_disable on each.
  - CLASS_RELOADED for a SessionState class disables every old per-session
    instance, then enables a new one with the new class.
  - `get_session(cls, sid)` and `get_session_optional(cls, sid)` return what
    was stored.
  - Direct LibraryState subclasses (bypassing AppState/SessionState) are
    logged-and-ignored rather than silently dropped.
"""

import logging

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state import (
    AppState,
    LibraryState,
    LibraryStateContainer,
    LibraryStateRegistry,
    SessionState,
)
from haywire.core.state.identity import LibraryStateClassIdentity


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


class TestAppScopeRegression:
    def test_app_state_class_still_creates_singleton(self):
        class Pool(AppState):
            pass

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg._register_class(Pool, lib_id)

        container.on_lifecycle_events([make_added_event(Pool, lib_id)])
        assert Pool in container
        assert container[Pool] is container[Pool]  # singleton


class TestSessionAttachDetach:
    def test_attach_then_class_added_creates_one_instance_per_session(self):
        calls: list[tuple[str, str]] = []

        class TimelineCursor(SessionState):
            def on_enable(self) -> None:
                calls.append(("enable", self.session_id))

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()

        # Attach two sessions BEFORE class is registered.
        container.attach_session("s1")
        container.attach_session("s2")

        # Now register and add the SessionState class.
        reg._register_class(TimelineCursor, lib_id)
        container.on_lifecycle_events([make_added_event(TimelineCursor, lib_id)])

        # One instance per session.
        i1 = container.get_session(TimelineCursor, "s1")
        i2 = container.get_session(TimelineCursor, "s2")
        assert isinstance(i1, TimelineCursor)
        assert isinstance(i2, TimelineCursor)
        assert i1 is not i2
        # session_id stamped before on_enable.
        assert i1.session_id == "s1"
        assert i2.session_id == "s2"
        assert sorted(calls) == [("enable", "s1"), ("enable", "s2")]

    def test_class_added_then_attach_creates_instance(self):
        calls: list[str] = []

        class Cursor(SessionState):
            def on_enable(self) -> None:
                calls.append(self.session_id)

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()

        # Register class first; no sessions yet.
        reg._register_class(Cursor, lib_id)
        container.on_lifecycle_events([make_added_event(Cursor, lib_id)])
        assert calls == []  # no instance, no session

        # Attach a session — instance is created.
        container.attach_session("only")
        assert isinstance(container.get_session(Cursor, "only"), Cursor)
        assert calls == ["only"]

    def test_detach_session_calls_on_disable_and_drops_instances(self):
        calls: list[tuple[str, str]] = []

        class Cursor(SessionState):
            def on_enable(self) -> None:
                calls.append(("enable", self.session_id))

            def on_disable(self) -> None:
                calls.append(("disable", self.session_id))

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg._register_class(Cursor, lib_id)
        container.on_lifecycle_events([make_added_event(Cursor, lib_id)])
        container.attach_session("s1")

        container.detach_session("s1")
        assert container.get_session_optional(Cursor, "s1") is None
        assert ("disable", "s1") in calls

    def test_get_session_optional_returns_none_for_missing(self):
        class Cursor(SessionState):
            pass

        container = LibraryStateContainer()
        assert container.get_session_optional(Cursor, "nope") is None


class TestSessionScopeHotReload:
    def test_class_removed_drops_all_per_session_instances(self):
        calls: list[tuple[str, str]] = []

        class Cursor(SessionState):
            def on_enable(self) -> None:
                calls.append(("enable", self.session_id))

            def on_disable(self) -> None:
                calls.append(("disable", self.session_id))

        reg = LibraryStateRegistry()
        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        reg._register_class(Cursor, lib_id)
        container.on_lifecycle_events([make_added_event(Cursor, lib_id)])
        container.attach_session("s1")
        container.attach_session("s2")

        container.on_lifecycle_events([make_removed_event(Cursor, lib_id)])

        assert container.get_session_optional(Cursor, "s1") is None
        assert container.get_session_optional(Cursor, "s2") is None
        assert ("disable", "s1") in calls
        assert ("disable", "s2") in calls

    def test_class_reloaded_swaps_per_session_instances(self):
        calls: list[tuple[str, str]] = []

        ident = LibraryStateClassIdentity(
            class_name="V",
            module=__name__,
            registry_id="V",
            registry_key="midi:state:V",
            label="V",
        )

        class V1(SessionState):
            def on_enable(self) -> None:
                calls.append(("v1-enable", self.session_id))

            def on_disable(self) -> None:
                calls.append(("v1-disable", self.session_id))

        class V2(SessionState):
            def on_enable(self) -> None:
                calls.append(("v2-enable", self.session_id))

            def on_disable(self) -> None:
                calls.append(("v2-disable", self.session_id))

        V1.class_identity = ident
        V2.class_identity = ident

        container = LibraryStateContainer()
        lib_id = make_lib_identity()
        container.on_lifecycle_events([make_added_event(V1, lib_id)])
        container.attach_session("s1")
        # Initial enable.
        assert ("v1-enable", "s1") in calls

        # Hot-reload: same registry_key, new class.
        reload_event = LifeCycleEvent(
            registry_key="midi:state:V",
            event_type=LifeCycleEventType.CLASS_RELOADED,
            affected_class=V2,
            library_identity=lib_id,
        )
        container.on_lifecycle_events([reload_event])

        # Old V1 instance disabled, new V2 instance enabled (still session "s1").
        assert ("v1-disable", "s1") in calls
        assert ("v2-enable", "s1") in calls
        new_inst = container.get_session(V2, "s1")
        assert isinstance(new_inst, V2)
        assert new_inst.session_id == "s1"


class TestDirectLibraryStateSubclass:
    def test_class_added_for_direct_library_state_subclass_is_logged_and_ignored(self, caplog):
        class Bad(LibraryState):
            pass

        Bad.class_identity = LibraryStateClassIdentity(
            class_name="Bad",
            module=__name__,
            registry_id="Bad",
            registry_key="midi:state:Bad",
            label="Bad",
        )

        container = LibraryStateContainer()
        lib_id = make_lib_identity()

        with caplog.at_level(logging.WARNING):
            container.on_lifecycle_events([make_added_event(Bad, lib_id)])

        assert any("Bad" in record.message for record in caplog.records)
        assert any("midi:state:Bad" in record.getMessage() for record in caplog.records)
        assert Bad not in container._app
        assert Bad not in container._sessions

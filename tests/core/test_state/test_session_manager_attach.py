"""Tests verifying SessionManager calls container.attach_session / detach_session
around session creation / removal."""

from unittest.mock import MagicMock

from haywire.core.state import LibraryStateContainer, SessionState
from haywire.ui.session_manager import SessionManager


class TestSessionManagerAttachDetach:
    def _make_session_kwargs(self, container: LibraryStateContainer) -> dict:
        """Build kwargs that satisfy Session.__init__."""
        project_state = MagicMock()
        project_state.library_state_container = container
        return {"project_state": project_state, "workspace_manager": MagicMock()}

    def test_create_session_attaches_to_container(self):
        container = LibraryStateContainer()
        manager = SessionManager(container=container)

        session = manager.create_session(**self._make_session_kwargs(container))

        assert session.session_id in container._known_session_ids

    def test_remove_session_detaches_from_container(self):
        container = LibraryStateContainer()
        manager = SessionManager(container=container)
        session = manager.create_session(**self._make_session_kwargs(container))

        manager.remove_session(session.session_id)

        assert session.session_id not in container._known_session_ids

    def test_session_state_class_visible_after_attach(self):
        """A SessionState registered before session creation gets an instance per session."""
        from haywire.core.state.identity import LibraryStateClassIdentity

        calls: list[str] = []

        class TimelineCursor(SessionState):
            def on_enable(self) -> None:
                calls.append(self.session_id)

        TimelineCursor.class_identity = LibraryStateClassIdentity(
            class_name="TimelineCursor",
            module=__name__,
            registry_id="TimelineCursor",
            registry_key="test:state:TimelineCursor",
            label="TimelineCursor",
        )

        # Plant the SessionState class directly onto the container so we don't
        # need the registry plumbing for this unit test. (Integration test
        # exercises the registry path in Task 8.)
        container = LibraryStateContainer()
        key = TimelineCursor.class_identity.registry_key
        container._sessions[key] = {}
        container._class_by_registry_key[key] = TimelineCursor

        manager = SessionManager(container=container)
        session = manager.create_session(**self._make_session_kwargs(container))

        # on_enable fired for the new session.
        assert calls == [session.session_id]
        # Container has an instance for this session (dict keyed by registry_key).
        assert key in container._sessions
        assert session.session_id in container._sessions[key]

    def test_remove_session_calls_on_disable(self):
        from haywire.core.state.identity import LibraryStateClassIdentity

        calls: list[str] = []

        class Cursor(SessionState):
            def on_disable(self) -> None:
                calls.append(self.session_id)

        Cursor.class_identity = LibraryStateClassIdentity(
            class_name="Cursor",
            module=__name__,
            registry_id="Cursor",
            registry_key="test:state:Cursor_dis",
            label="Cursor",
        )

        container = LibraryStateContainer()
        key = Cursor.class_identity.registry_key
        container._sessions[key] = {}
        container._class_by_registry_key[key] = Cursor

        manager = SessionManager(container=container)
        session = manager.create_session(**self._make_session_kwargs(container))

        manager.remove_session(session.session_id)
        assert calls == [session.session_id]

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
        calls: list[str] = []

        class TimelineCursor(SessionState):
            def on_enable(self) -> None:
                calls.append(self.session_id)

        # Plant the SessionState class directly onto the container so we don't
        # need the registry plumbing for this unit test. (Integration test
        # exercises the registry path in Task 8.)
        container = LibraryStateContainer()
        container._sessions[TimelineCursor] = {}

        manager = SessionManager(container=container)
        session = manager.create_session(**self._make_session_kwargs(container))

        # on_enable fired for the new session.
        assert calls == [session.session_id]
        # Container has an instance for this session.
        assert TimelineCursor in container._sessions
        assert session.session_id in container._sessions[TimelineCursor]

    def test_remove_session_calls_on_disable(self):
        calls: list[str] = []

        class Cursor(SessionState):
            def on_disable(self) -> None:
                calls.append(self.session_id)

        container = LibraryStateContainer()
        container._sessions[Cursor] = {}
        manager = SessionManager(container=container)
        session = manager.create_session(**self._make_session_kwargs(container))

        manager.remove_session(session.session_id)
        assert calls == [session.session_id]

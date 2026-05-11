"""End-to-end: full LibrarySystemService + SessionManager + SessionState pipeline.

Verifies that registering a SessionState class through the registry's public
API path, attaching a session via SessionManager, and reading via
SessionDataNamespace all work end-to-end with the actual DI graph.
"""

import pytest
from unittest.mock import MagicMock

from haywire.core.di.config import LibrarySystemService, create_haywire_injector
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType,
)
from haywire.core.state import (
    LibraryStateContainer,
    LibraryStateRegistry,
    SessionState,
)
from haywire.core.state.data_namespace import SessionDataNamespace
from haywire.core.session.session_manager import SessionManager


@pytest.mark.integration
class TestSessionStateIntegration:
    def test_register_then_attach_then_access_then_detach(self):
        """Full lifecycle: register class, attach session, on_enable, access, detach, on_disable."""
        injector = create_haywire_injector()
        service = LibrarySystemService(injector)
        service.initialize()

        registry = injector.get(LibraryStateRegistry)
        container = injector.get(LibraryStateContainer)

        calls: list[tuple[str, str]] = []

        class TimelineCursor(SessionState):
            position: float = 0.0

            def on_enable(self) -> None:
                calls.append(("enable", self.session_id))

            def on_disable(self) -> None:
                calls.append(("disable", self.session_id))

        # Build a minimal LibraryIdentity for this test "library".
        lib_id = LibraryIdentity(
            id="testlib",
            label="Test Library",
            version="0.0.1",
            description="",
            url="",
            help_url="",
            author="",
            author_url="",
            dependencies=[],
            tags=[],
            module_name="testlib",
            folder_path="",
        )

        # Mark the test library as enabled so the container's event filter
        # admits its events. In production this happens via
        # LibraryRegistry.on_library_enabled after library.enable() returns;
        # this test bypasses LibraryRegistry and drives events directly.
        container._mark_library_enabled(lib_id.id)

        # Register the class via the same path a real library would use.
        key = registry._register_class(TimelineCursor, lib_id)
        assert key is not None

        # Simulate the registry emitting CLASS_ADDED for the SessionState class.
        added_event = LifeCycleEvent(
            registry_key=key,
            event_type=LifeCycleEventType.CLASS_ADDED,
            affected_class=TimelineCursor,
            library_identity=lib_id,
        )
        registry._lifecycle_event_queue.append(added_event)
        registry._notify_batch_event_subscribers()

        # No sessions yet — no instances exist.
        assert calls == []

        # Construct a SessionManager wired to this container.
        manager = SessionManager(container=container)
        project_state = MagicMock()
        project_state.library_state_container = container
        session = manager.create_session(
            project_state=project_state,
            workspace_manager=MagicMock(),
        )

        # on_enable fired for this session.
        assert calls == [("enable", session.session_id)]

        # Access via SessionDataNamespace.
        ns = SessionDataNamespace(container, session.session_id)
        instance = ns[TimelineCursor]
        assert isinstance(instance, TimelineCursor)
        assert instance.session_id == session.session_id

        # Tear down — on_disable fires.
        manager.remove_session(session.session_id)
        assert ("disable", session.session_id) in calls
        # Container no longer has an instance for this session.
        assert ns.get(TimelineCursor) is None

"""Tests that LibraryStateContainer stamps the `session` weakref before on_enable.

The dead-weakref / post-cleanup case is covered by unit tests in
``test_app_state_broadcast.py::test_session_state_signal_emit_silent_when_session_gone``.
"""

from unittest.mock import MagicMock

from haywire.core.state.base import SessionState


def test_container_stamps_session_weakref_on_session_state():
    """When the container instantiates a SessionState for a session, it must
    stamp `self.session = weakref.ref(session)` before on_enable runs."""
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.state.container import LibraryStateContainer
    from haywire.core.state.identity import LibraryStateClassIdentity
    from haywire.core.state.registry import LibraryStateRegistry

    seen_session = []

    class MyState(SessionState):
        class_identity = LibraryStateClassIdentity(
            registry_id="MyState",
            registry_key="test:lib:MyState",
            label="MyState",
            class_name="MyState",
            module=__name__,
        )
        class_library = LibraryIdentity(
            id="test:lib",
            label="test",
            version="0",
            description="",
            url="",
            help_url="",
            author="",
            author_url="",
            folder_path="",
            module_name="test_lib",
            dependencies=[],
            tags=[],
        )

        def on_enable(self) -> None:
            # The weakref must be set by now.
            seen_session.append(self.session())

    container = LibraryStateContainer(LibraryStateRegistry())
    container._mark_library_enabled("test:lib")
    container._class_by_registry_key["test:lib:MyState"] = MyState
    container._sessions["test:lib:MyState"] = {}

    fake_session = MagicMock()
    container.attach_session_with_ref("session-1", fake_session)

    assert seen_session == [fake_session]

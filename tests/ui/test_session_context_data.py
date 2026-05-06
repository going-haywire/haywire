"""Tests for SessionContext.data — the LibraryState access path."""

from haywire.core.state import (
    LibraryState,
    LibraryStateContainer,
)
from haywire.core.state.data_namespace import DataNamespace
from haywire.ui.context import SessionContext


class FakeApp:
    """Minimal IProjectState stub for SessionContext construction."""

    def __init__(self, container: LibraryStateContainer) -> None:
        self.library_state_container = container


class TestSessionContextData:
    def test_session_context_exposes_data_namespace(self):
        container = LibraryStateContainer()
        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert isinstance(ctx.data, DataNamespace)

    def test_session_context_data_resolves_to_container(self):
        class Pool(LibraryState):
            value: int = 42

        container = LibraryStateContainer()
        # Manually plant an instance so we don't need full registry wiring here.
        instance = Pool()
        container._instances_by_class[Pool] = instance

        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert ctx.data[Pool] is instance

    def test_session_context_no_longer_has_metadata(self):
        """metadata field was removed in favour of LibraryState."""
        container = LibraryStateContainer()
        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert not hasattr(ctx, "metadata")

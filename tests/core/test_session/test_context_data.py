"""Tests for SessionContext.app_data (AppState) and SessionContext.data (SessionState)."""

from haywire.core.state import (
    AppState,
    LibraryStateContainer,
)
from haywire.core.state.data_namespace import AppDataNamespace, SessionDataNamespace
from haywire.core.session.context import SessionContext


class FakeApp:
    """Minimal IProjectState stub for SessionContext construction."""

    def __init__(self, container: LibraryStateContainer) -> None:
        self.library_state_container = container


class TestSessionContextAppData:
    def test_session_context_exposes_app_data_namespace(self):
        container = LibraryStateContainer()
        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert isinstance(ctx.app_data, AppDataNamespace)

    def test_app_data_resolves_to_container(self):
        from haywire.core.state.identity import LibraryStateClassIdentity

        class Pool(AppState):
            value: int = 42

        Pool.class_identity = LibraryStateClassIdentity(
            class_name="Pool",
            module=__name__,
            registry_id="Pool",
            registry_key="test:state:Pool",
            label="Pool",
        )

        container = LibraryStateContainer()
        instance = Pool()
        container._app[Pool.class_identity.registry_key] = instance
        container._class_by_registry_key[Pool.class_identity.registry_key] = Pool

        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert ctx.app_data[Pool] is instance


class TestSessionContextSessionData:
    def test_session_context_exposes_data_namespace_bound_to_session_id(self):
        container = LibraryStateContainer()
        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert isinstance(ctx.data, SessionDataNamespace)
        # Internal: namespace knows its session_id.
        assert ctx.data._session_id == "s1"

    def test_session_context_no_longer_has_metadata(self):
        """metadata field removed in v1; this is the regression test."""
        container = LibraryStateContainer()
        app = FakeApp(container)
        ctx = SessionContext(session_id="s1", app=app)  # type: ignore[arg-type]

        assert not hasattr(ctx, "metadata")

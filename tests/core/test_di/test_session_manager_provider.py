"""Test that provide_session_manager wires SessionManager via DI and ambient context."""


def test_provider_returns_session_manager():
    """The provider returns a SessionManager configured with the container."""
    import haywire.core.di.context as ctx_mod

    ctx_mod._session_manager = None

    from haywire.core.di.config import HaywireModule
    from haywire.core.session.session_manager import SessionManager
    from haywire.core.state import LibraryStateContainer, LibraryStateRegistry

    container = LibraryStateContainer(LibraryStateRegistry())
    module = HaywireModule(workspace_root="/tmp/test")
    sm = module.provide_session_manager(container)

    assert isinstance(sm, SessionManager)
    assert sm._container is container


def test_provider_publishes_to_ambient_context():
    """The provider also publishes the instance via set_session_manager."""
    import haywire.core.di.context as ctx_mod

    ctx_mod._session_manager = None

    from haywire.core.di.config import HaywireModule
    from haywire.core.di.context import get_session_manager
    from haywire.core.state import LibraryStateContainer, LibraryStateRegistry

    container = LibraryStateContainer(LibraryStateRegistry())
    module = HaywireModule(workspace_root="/tmp/test")
    sm = module.provide_session_manager(container)

    assert get_session_manager() is sm

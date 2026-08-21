"""Test that the DI providers wire SignalDispatcher + SessionManager
via DI and ambient context."""


def test_provider_returns_session_manager():
    """The provider returns a SessionManager configured with the container."""
    import haywire.core.di.context as ctx_mod

    ctx_mod._session_manager = None
    ctx_mod._signal_dispatcher = None

    from haywire.core.di.config import HaywireModule
    from haywire.core.session.session_manager import SessionManager
    from haywire.core.state import LibraryStateContainer, LibraryStateRegistry

    container = LibraryStateContainer(LibraryStateRegistry())
    module = HaywireModule(workspace_root="/tmp/test")
    dispatcher = module.provide_signal_dispatcher(container)
    sm = module.provide_session_manager(dispatcher, container)

    assert isinstance(sm, SessionManager)
    assert sm._container is container
    assert sm._dispatcher is dispatcher


def test_provider_publishes_to_ambient_context():
    """The provider also publishes the instance via set_session_manager."""
    import haywire.core.di.context as ctx_mod

    ctx_mod._session_manager = None
    ctx_mod._signal_dispatcher = None

    from haywire.core.di.config import HaywireModule
    from haywire.core.di.context import get_session_manager
    from haywire.core.state import LibraryStateContainer, LibraryStateRegistry

    container = LibraryStateContainer(LibraryStateRegistry())
    module = HaywireModule(workspace_root="/tmp/test")
    dispatcher = module.provide_signal_dispatcher(container)
    sm = module.provide_session_manager(dispatcher, container)

    assert get_session_manager() is sm


def test_dispatcher_provider_publishes_and_binds_container():
    """provide_signal_dispatcher publishes ambiently AND stamps the container.

    The container binding lives in the provider rather than in
    SignalDispatcher.__init__ so the dispatcher stays dependency-free.
    """
    import haywire.core.di.context as ctx_mod

    ctx_mod._signal_dispatcher = None

    from haywire.core.di.config import HaywireModule
    from haywire.core.di.context import get_signal_dispatcher
    from haywire.core.signals import SignalDispatcher
    from haywire.core.state import LibraryStateContainer, LibraryStateRegistry

    container = LibraryStateContainer(LibraryStateRegistry())
    module = HaywireModule(workspace_root="/tmp/test")
    dispatcher = module.provide_signal_dispatcher(container)

    assert isinstance(dispatcher, SignalDispatcher)
    assert get_signal_dispatcher() is dispatcher
    assert container._dispatcher_ref is not None
    assert container._dispatcher_ref() is dispatcher

# haywire/core/di/context.py
"""
Ambient context for app-scoped singletons.

Set once at startup by DI providers; read by deep entity constructors that cannot
receive these via constructor injection::

    self._node_factory = get_node_factory()   # read (entity constructors)
    set_node_factory(factory)                  # write (DI providers only)
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..node.factory import NodeFactory
    from ..adapter.factory import AdapterFactory
    from ..types.registry import TypeRegistry
    from ..settings import SettingsRegistry
    from ..session.session_manager import SessionManager
    from ..signals import SignalDispatcher
    from ..state import LibraryStateContainer
    from ..errors.ledger import ErrorLedger
    from ..farmhand.activity import ActivityTracker


# Module-level globals (not ContextVar): these are true app-wide singletons that must
# be reachable from any thread, including the watchdog file-watcher thread used for
# hot-reload. ContextVar broke hot-reload (a reload captured a different ContextVar
# instance than the rest of the app).
_node_factory: Optional["NodeFactory"] = None
_adapter_factory: Optional["AdapterFactory"] = None
_type_registry: Optional["TypeRegistry"] = None
_settings_registry: Optional["SettingsRegistry"] = None
_session_manager: Optional["SessionManager"] = None
_signal_dispatcher: Optional["SignalDispatcher"] = None
_workspace_root: Optional[Path] = None
_library_state_container: Optional["LibraryStateContainer"] = None
# Process-wide diagnostic buffers, deliberately NOT reset on injector/hot-reload
# rebuilds (unlike the singletons above) — a reload must not erase the record of
# what happened before it. Both are "observable stores": lazily constructed on
# first access, they own a listener list that an app-side bridge turns into a
# cross-session signal. See errors/ledger.py and farmhand/activity.py.
_error_ledger: Optional["ErrorLedger"] = None
_activity_tracker: Optional["ActivityTracker"] = None


# ---------------------------------------------------------------------------
# Setters — called by DI providers at startup
# ---------------------------------------------------------------------------


def set_node_factory(factory: "NodeFactory") -> None:
    global _node_factory
    _node_factory = factory


def set_adapter_factory(factory: "AdapterFactory") -> None:
    global _adapter_factory
    _adapter_factory = factory


def set_type_registry(registry: "TypeRegistry") -> None:
    global _type_registry
    _type_registry = registry


def set_settings_registry(registry: "SettingsRegistry") -> None:
    global _settings_registry
    _settings_registry = registry


def set_session_manager(manager: "SessionManager") -> None:
    global _session_manager
    _session_manager = manager


def set_signal_dispatcher(dispatcher: "SignalDispatcher") -> None:
    global _signal_dispatcher
    _signal_dispatcher = dispatcher


def set_workspace_root(path) -> None:
    """Set the ambient workspace root. Accepts str or Path."""
    global _workspace_root
    _workspace_root = Path(path)


def set_library_state_container(container: "LibraryStateContainer") -> None:
    global _library_state_container
    _library_state_container = container


def set_error_ledger(ledger: Optional["ErrorLedger"]) -> None:
    """Replace the ambient ledger; ``None`` restores lazy construction.

    Provided for isolation — pass a fresh ``ErrorLedger()`` to sever a test
    from process-wide diagnostic state, then ``None`` (or the snapshot taken
    beforehand) to restore it.
    """
    global _error_ledger
    _error_ledger = ledger


def set_activity_tracker(tracker: Optional["ActivityTracker"]) -> None:
    """Replace the ambient activity tracker; ``None`` restores lazy construction.

    Same contract as :func:`set_error_ledger` — the two diagnostic buffers are
    deliberately identical in shape.
    """
    global _activity_tracker
    _activity_tracker = tracker


# ---------------------------------------------------------------------------
# Getters — called by entity constructors
# ---------------------------------------------------------------------------


def get_node_factory() -> "NodeFactory":
    if _node_factory is None:
        raise RuntimeError(
            "NodeFactory not set in ambient context. Ensure DI is initialised before constructing nodes."
        )
    return _node_factory


def get_adapter_factory() -> "AdapterFactory":
    if _adapter_factory is None:
        raise RuntimeError(
            "AdapterFactory not set in ambient context. Ensure DI is initialised before constructing edges."
        )
    return _adapter_factory


def get_type_registry() -> "TypeRegistry":
    if _type_registry is None:
        raise RuntimeError(
            "TypeRegistry not set in ambient context. Ensure DI is initialised before constructing nodes."
        )
    return _type_registry


def get_settings_registry() -> "SettingsRegistry":
    if _settings_registry is None:
        raise RuntimeError(
            "SettingsRegistry not set in ambient context. "
            "Ensure DI is initialised before constructing nodes."
        )
    return _settings_registry


def get_session_manager() -> "SessionManager":
    if _session_manager is None:
        raise RuntimeError(
            "SessionManager not set in ambient context. "
            "Ensure HaywireApp has been initialised before requesting it."
        )
    return _session_manager


def get_signal_dispatcher() -> "SignalDispatcher":
    """The process-wide signal fan-out channel.

    Read by emitters that own no peer of their own and cannot receive one by
    injection — ``FarmhandContext.broadcast`` (constructed per MCP call) and
    the studio's error/activity bridges. Code holding a ``SignalPeer`` should
    use ``peer.publish(...)`` instead; code holding an ``AppState`` already has
    the per-container weakref, which is isolated where this global is not.
    """
    if _signal_dispatcher is None:
        raise RuntimeError(
            "SignalDispatcher not set in ambient context. "
            "Ensure HaywireApp has been initialised before requesting it."
        )
    return _signal_dispatcher


def get_workspace_root() -> Path:
    if _workspace_root is None:
        raise RuntimeError(
            "workspace_root not set in ambient context. "
            "Ensure HaywireApp has been initialised before requesting it."
        )
    return _workspace_root


def get_library_state_container() -> "LibraryStateContainer":
    if _library_state_container is None:
        raise RuntimeError(
            "LibraryStateContainer not set in ambient context. "
            "Ensure HaywireApp has been initialised before requesting it."
        )
    return _library_state_container


def get_error_ledger() -> "ErrorLedger":
    """Return the ambient ledger, lazily creating the process-wide default."""
    global _error_ledger
    if _error_ledger is None:
        from ..errors.ledger import ErrorLedger

        _error_ledger = ErrorLedger()
    return _error_ledger


def activity_tracker() -> "ActivityTracker":
    """Return the ambient Farmhand activity tracker, lazily creating the default.

    Lazy on purpose: constructing at import time would build the tracker before
    ``ActivitySettings`` is registered, which is what forced the tracker to
    re-resolve its history cap on every append.

    Named without a ``get_`` prefix, unlike its neighbours, because that is the
    name every existing call site already uses.
    """
    global _activity_tracker
    if _activity_tracker is None:
        from ..farmhand.activity import ActivityTracker

        _activity_tracker = ActivityTracker()
    return _activity_tracker

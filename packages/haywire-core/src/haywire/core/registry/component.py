"""The registry contract shared by class-backed and file-backed registries.

``ComponentRegistry`` owns what every registry does regardless of what it
stores: the key→element map, which library claimed which folder, the
lifecycle-event queue and its two subscriber lists, and the read API
consumers use. Module reload, ``sys.modules`` and ``importlib`` belong to
``BaseRegistry`` alone.
"""

from typing import Dict, Generic, List, Optional, cast
from abc import abstractmethod
import logging

from ..library.identity import LibraryIdentity
from .events import FileChangeEvent, HotReloadRegistry, T
from .identity import BaseIdentity
from .lifecycle_event import LifeCycleEvent, LifeCycleBatchCallback

logger = logging.getLogger(__name__)


class ComponentRegistry(HotReloadRegistry, Generic[T]):
    """Storage, folder bookkeeping and lifecycle notification for one component kind.

    Generic over ``T``, the element type a concrete registry stores. A
    subclass decides where elements come from: ``BaseRegistry`` imports them
    from Python modules, a document registry parses them from files.
    """

    def __init__(self):
        self._classes: Dict[str, type[T]] = {}  # registry_key -> class

        # stores the last life-cycle event for each class that has been processed
        # it keeps track of what was the last event type for each class,
        # even those that have been removed
        # registry_key -> event
        self._regkey_to_last_lifecycle_event: Dict[str, LifeCycleEvent] = {}

        # folder_path -> library_identity
        self._folder_to_library: Dict[str, LibraryIdentity] = {}

        # Queue of events to process after reload
        self._lifecycle_event_queue: List[LifeCycleEvent] = []

        # Other registries that depend on this one
        self._registry_subscribers: List[HotReloadRegistry] = []
        # Direct consumers (factories, etc.)
        self._batch_event_subscribers: List[LifeCycleBatchCallback] = []

        self.logger = logging.getLogger(__name__)

    # ============================================================================
    # Folder registration
    # ============================================================================

    @abstractmethod
    def add_folder(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """Scan ``folder_path`` and register everything it holds.

        Called by the library when it is enabled.

        Args:
            folder_path: Path to the folder to scan.
            exclude_patterns: Filename patterns to exclude.
        """
        pass

    @abstractmethod
    def remove_folder(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """Unregister everything ``folder_path`` contributed.

        Called by the library when it is disabled.

        Args:
            folder_path: Path to the folder to remove.
            exclude_patterns: Filename patterns to exclude.
        """
        pass

    # ============================================================================
    # Read API
    # ============================================================================

    def get(self, registry_key: str) -> type[T] | None:
        """Retrieve a registered class by its haywire registry_key"""
        return self._classes.get(registry_key)

    def has(self, registry_key: str) -> bool:
        """Check if a class is registered"""
        return registry_key in self._classes

    def list_names(self) -> list[str]:
        """List all classes registry_keys in this registry."""
        return list(self._classes.keys())

    def list_visible_names(self) -> list[str]:
        """List registry_keys of non-hidden classes.
        for those offered as a choice in author-facing selection UIs (menus, pickers).
        """
        return [
            key for key, cls in self._classes.items() if not cast(BaseIdentity, cls.class_identity).hidden
        ]

    def get_lastevent(self, registry_key: str) -> LifeCycleEvent | None:
        """Return the most recent lifecycle event for ``registry_key``, or ``None``.

        Survives removal: a key unregistered by a failed reload still reports
        the event that removed it.
        """
        return self._regkey_to_last_lifecycle_event.get(registry_key)

    # ============================================================================
    # Hot Reload Callback Management
    # ============================================================================

    def add_batch_event_subscriber(self, callback: LifeCycleBatchCallback) -> None:
        """
        Register a customer callback to be notified of hot reload events.

        Customer callbacks are invoked immediately after a class is reloaded,
        added, or removed. They receive a LifeCycleEvent batch with complete context.

        Args:
            callback: Function to call on life cycle events with signature:
                     (event: List[LifeCycleEvent]) -> None
        """
        if callback not in self._batch_event_subscribers:
            self._batch_event_subscribers.append(callback)
            self.logger.debug(
                f"Registered customer callback: {getattr(callback, '__name__', repr(callback))}"
            )

    def remove_batch_event_subscriber(self, callback: LifeCycleBatchCallback) -> None:
        """
        Unregister a customer callback.

        Args:
            callback: The callback to remove
        """
        if callback in self._batch_event_subscribers:
            self._batch_event_subscribers.remove(callback)
            self.logger.debug(f"Removed customer callback: {getattr(callback, '__name__', repr(callback))}")

    def add_registry_subscriber(self, registry: HotReloadRegistry) -> None:
        """
        Register another registry to be notified of hot reload events.

        Registry subscribers are invoked after customer callbacks and receive
        complete FileChangeEvent information for their own processing.

        Args:
            registry: Another registry that needs to react to changes in this registry
        """
        if registry not in self._registry_subscribers:
            self._registry_subscribers.append(registry)
            self.logger.debug(
                f"{self.__class__.__name__}: Registered registry subscriber: {registry.__class__.__name__}"
            )

    def remove_registry_subscriber(self, registry: HotReloadRegistry) -> None:
        """
        Unregister a registry subscriber.

        Args:
            registry: The registry to unsubscribe
        """
        if registry in self._registry_subscribers:
            self._registry_subscribers.remove(registry)
            self.logger.debug(f"Removed registry subscriber: {registry.__class__.__name__}")

    def _queue_lifecycle_event(self, event: LifeCycleEvent) -> None:
        """
        Queues a hot reload event.

        This method is called internally during hot reload operations.
        Errors in individual callbacks are logged but don't stop generation of events.

        Args:
            event: The hot reload event with complete context
        """
        self._regkey_to_last_lifecycle_event[event.registry_key] = event

        self._lifecycle_event_queue.append(event)

    def _notify_batch_event_subscribers(self) -> None:
        """
        Batch notify all customer callbacks about hot reload events.

        This method is called internally during hot reload operations.

        Callbacks receive the complete event information.:

        """

        for callback in self._batch_event_subscribers[:]:
            callback(self._lifecycle_event_queue)

        self._lifecycle_event_queue.clear()

    def _notify_registry_subscribers(self, event: FileChangeEvent) -> None:
        """
        Notify all registry subscribers about a hot reload event.

        This method is called after customer callbacks have been notified.
        Registry subscribers receive the complete event information and can
        perform their own dependency analysis and reloading.

        Args:
            event: The file change event that triggered the reload
        """
        for registry in self._registry_subscribers[:]:
            try:
                registry.event_dispatcher(event)
            except Exception as e:
                self.logger.error(
                    f"Registry subscriber '{registry.__class__.__name__}' "
                    f"callback failed for {event.file_path}: {e}",
                    exc_info=True,
                )

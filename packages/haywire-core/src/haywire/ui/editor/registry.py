# packages/haywire-core/src/haywire/ui/editor_framework/registry.py
"""
EditorTypeRegistry for managing editor type registrations.

Extends BaseRegistry for hot-reload support, folder scanning, lifecycle
events, dependency tracking, and snapshot rollback.
"""

import inspect
import logging
from typing import Dict, List

from haywire.core.registry.base import BaseRegistry
from haywire.core.registry.lifecycle_event import LifeCycleEventCallback
from haywire.core.library.identity import LibraryIdentity

from .base import BaseEditor

logger = logging.getLogger(__name__)


class EditorTypeRegistry(BaseRegistry):
    """
    Registry of editor types.

    Extends BaseRegistry for hot-reload support, folder scanning, lifecycle
    events, dependency tracking, and snapshot rollback. Provided as a DI
    singleton by HaywireModule.

    Libraries register editors via add_folder() in register_components().
    Built-in framework editors are bootstrapped via register_builtin_editors()
    called from the DI provider, analogous to register_builtin_settings().
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._lifecycle_event_subscribers: Dict[str, List[LifeCycleEventCallback]] = {}

    def _class_filter(self, cls) -> bool:
        """Return True if cls is a valid, decorated BaseEditor subclass."""
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, BaseEditor)
                and cls is not BaseEditor
                and hasattr(cls, "class_identity")
            )
        except TypeError:
            return False

    def _register_class(self, cls: type[BaseEditor], library_identity: LibraryIdentity) -> "str | None":
        """Register an editor class by its registry_key."""
        registry_key = cls.class_identity.registry_key
        logger.debug(f"EditorTypeRegistry: Registering '{registry_key}' ({cls.__name__})")
        return super()._register(registry_key, cls, library_identity)

    def _unregister_class(self, registry_key: str) -> "type[BaseEditor] | None":
        """Unregister an editor class by its registry_key."""
        return super()._unregister(registry_key)

    def get_by_key(self, registry_key: str) -> "type[BaseEditor] | None":
        """Find an editor class by its full registry_key.

        Used by AppShell to resolve workspace editor_key strings to actual
        editor classes. WorkspaceState stores full registry_key values.

        Args:
            registry_key: Full key as computed by the @editor decorator,
                e.g. 'studio:editor:graph_editor'.

        Returns:
            The editor class, or None if not found.
        """
        return self._classes.get(registry_key)

    def get_by_default_slot(self, slot: str) -> "Dict[str, type[BaseEditor]]":
        """Get all editor classes suggested for a given default slot.

        Args:
            slot: One of 'left', 'right', 'main', 'bottom'.

        Returns:
            Dict mapping registry_key -> editor class, sorted by the editor's
            ``class_identity.order`` (lower = earlier). Equal-order editors
            keep registration order (stable sort), so the slot/bar placement
            is deterministic and independent of library load order.
        """
        matching = [(k, v) for k, v in self._classes.items() if v.class_identity.default_slot == slot]
        matching.sort(key=lambda kv: kv[1].class_identity.order)
        return dict(matching)

    # ------------------------------------------------------------------
    # Per-key event subscription (mirrors NodeFactory.add_event_subscriber)
    # ------------------------------------------------------------------

    def add_event_subscriber(self, registry_key: str, callback: LifeCycleEventCallback) -> None:
        """Register a callback for lifecycle events of a specific registry_key.

        Used by EditorWrapper to self-subscribe for hot-reload notifications
        without going through the slot. Mirrors NodeFactory's per-key API.
        """
        self._lifecycle_event_subscribers.setdefault(registry_key, []).append(callback)

    def remove_event_subscriber(self, registry_key: str, callback: LifeCycleEventCallback) -> None:
        """Unregister a per-key callback."""
        if registry_key in self._lifecycle_event_subscribers:
            if callback in self._lifecycle_event_subscribers[registry_key]:
                self._lifecycle_event_subscribers[registry_key].remove(callback)
                if not self._lifecycle_event_subscribers[registry_key]:
                    del self._lifecycle_event_subscribers[registry_key]

    def _notify_batch_event_subscribers(self) -> None:
        """Override to dispatch per-key callbacks after batch fan-out.

        Order: batch subscribers first (preserving existing semantics), then
        per-key callbacks for every event in the queue. The queue is cleared
        by the super() call, so we copy events first.
        """
        events = list(self._lifecycle_event_queue)
        super()._notify_batch_event_subscribers()
        for event in events:
            callbacks = self._lifecycle_event_subscribers.get(event.registry_key, [])
            for cb in callbacks:
                try:
                    cb(event)
                except Exception as exc:
                    logger.error(
                        f"EditorTypeRegistry: per-key subscriber for '{event.registry_key}' raised: {exc}",
                        exc_info=True,
                    )

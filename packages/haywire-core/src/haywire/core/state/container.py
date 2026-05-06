"""LibraryStateContainer — owns the LibraryState instance pool.

Subscribes to LibraryStateRegistry batch lifecycle events. Mirrors the
NodeRegistry → NodeFactory pattern: registry holds classes, container holds
instances.

See docs/documentation/architecture/library_state.md §3.
"""

from __future__ import annotations

import logging
from typing import TypeVar

from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.core.state.base import LibraryState

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=LibraryState)


class LibraryStateContainer:
    """Holds live LibraryState instances, keyed by class.

    Wired to a LibraryStateRegistry via add_batch_event_subscriber:

        registry.add_batch_event_subscriber(container.on_lifecycle_events)

    The container reacts to:
      - CLASS_ADDED       → instantiate, store, call on_enable
      - CLASS_REMOVED     → call on_disable, drop instance
      - CLASS_RELOADED    → call on_disable on old, replace, call on_enable on new
    Failure events are logged and ignored.
    """

    def __init__(self) -> None:
        # Keyed by registry_key for events; instance map keyed by class for
        # ergonomic ctx.data[Cls] lookup. Both are kept in sync.
        self._instances_by_class: dict[type[LibraryState], LibraryState] = {}
        self._class_by_registry_key: dict[str, type[LibraryState]] = {}

    # ------------------------------------------------------------------
    # Public lookup API — used by DataNamespace
    # ------------------------------------------------------------------

    def __getitem__(self, cls: type[T]) -> T:
        try:
            return self._instances_by_class[cls]  # type: ignore[return-value]
        except KeyError:
            raise KeyError(
                f"No LibraryState instance registered for class {cls.__name__}. "
                f"Either the owning library is not enabled, or the class is not "
                f"a registered LibraryState subclass."
            ) from None

    def get(self, cls: type[T]) -> T | None:
        return self._instances_by_class.get(cls)  # type: ignore[return-value]

    def __contains__(self, cls: type) -> bool:
        return cls in self._instances_by_class

    # ------------------------------------------------------------------
    # Lifecycle event handler — registered with LibraryStateRegistry
    # ------------------------------------------------------------------

    def on_lifecycle_events(self, events: list[LifeCycleEvent]) -> None:
        """Process a batch of lifecycle events from LibraryStateRegistry."""
        for event in events:
            try:
                self._dispatch(event)
            except Exception as exc:
                logger.error(
                    "LibraryStateContainer error handling %s: %s",
                    event,
                    exc,
                    exc_info=True,
                )

    def _dispatch(self, event: LifeCycleEvent) -> None:
        et = event.event_type
        if et is LifeCycleEventType.CLASS_ADDED:
            self._add(event)
        elif et is LifeCycleEventType.CLASS_REMOVED:
            self._remove(event)
        elif et is LifeCycleEventType.CLASS_RELOADED:
            self._reload(event)
        # Other event types (NOT_FOUND, FAILED, INSTANTIATED, etc.) are
        # ignored — they don't change the instance pool.

    def _add(self, event: LifeCycleEvent) -> None:
        cls = event.affected_class
        if cls is None:
            return
        if cls in self._instances_by_class:
            return  # Idempotent.
        instance = cls()
        self._instances_by_class[cls] = instance
        self._class_by_registry_key[event.registry_key] = cls
        self._call_on_enable(instance)

    def _remove(self, event: LifeCycleEvent) -> None:
        cls = self._class_by_registry_key.pop(event.registry_key, None)
        if cls is None:
            return
        instance = self._instances_by_class.pop(cls, None)
        if instance is not None:
            self._call_on_disable(instance)

    def _reload(self, event: LifeCycleEvent) -> None:
        # Drop the OLD instance (whatever class is currently mapped to this
        # registry_key), then add the new one.
        old_cls = self._class_by_registry_key.pop(event.registry_key, None)
        if old_cls is not None:
            old_instance = self._instances_by_class.pop(old_cls, None)
            if old_instance is not None:
                self._call_on_disable(old_instance)

        new_cls = event.affected_class
        if new_cls is None:
            return
        new_instance = new_cls()
        self._instances_by_class[new_cls] = new_instance
        self._class_by_registry_key[event.registry_key] = new_cls
        self._call_on_enable(new_instance)

    @staticmethod
    def _call_on_enable(instance: LibraryState) -> None:
        hook = getattr(instance, "on_enable", None)
        if callable(hook):
            try:
                hook()
            except Exception as exc:
                logger.error("%s.on_enable raised: %s", type(instance).__name__, exc, exc_info=True)

    @staticmethod
    def _call_on_disable(instance: LibraryState) -> None:
        hook = getattr(instance, "on_disable", None)
        if callable(hook):
            try:
                hook()
            except Exception as exc:
                logger.error("%s.on_disable raised: %s", type(instance).__name__, exc, exc_info=True)

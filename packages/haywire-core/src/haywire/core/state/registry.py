"""LibraryStateRegistry — class registry for LibraryState subclasses.

Holds *classes*, not instances. The companion LibraryStateContainer subscribes
to this registry's batch lifecycle events and manages instance lifecycle.

Same shape as NodeRegistry, PanelRegistry, etc.: inherits hot-reload,
dependency-graph, and folder-scan machinery from BaseRegistry.
"""

from __future__ import annotations

import inspect
import logging

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry
from haywire.core.state.base import AppState, LibraryState, SessionState
from haywire.core.state.identity import LibraryStateClassIdentity

logger = logging.getLogger(__name__)

_MARKER_BASES: tuple[type, ...] = (LibraryState, AppState, SessionState)


class LibraryStateRegistry(BaseRegistry):
    """Registry for LibraryState classes.

    Registry key format: '{library_id}:state:{class_name}'.
    """

    def __init__(self) -> None:
        super().__init__()
        # registry_key -> library_id. Maintained alongside BaseRegistry._classes
        # so get_classes_for_library can answer in O(n) without peeking at
        # base-registry internals (_regkey_to_last_lifecycle_event would also
        # work but isn't populated when tests call _register_class directly).
        self._regkey_to_library_id: dict[str, str] = {}

    def _class_filter(self, cls: type) -> bool:
        try:
            return inspect.isclass(cls) and issubclass(cls, LibraryState) and cls not in _MARKER_BASES
        except TypeError:
            return False

    def _register_class(self, cls: type[LibraryState], library_identity: LibraryIdentity) -> str | None:
        """Attach a class_identity if missing, then delegate to BaseRegistry._register."""
        if not hasattr(cls, "class_identity"):
            registry_key = f"{library_identity.id}:state:{cls.__name__}"
            cls.class_identity = LibraryStateClassIdentity(
                registry_id=cls.__name__,
                registry_key=registry_key,
                label=cls.__name__,
                class_name=cls.__name__,
                module=cls.__module__,
            )

        registry_key = cls.class_identity.registry_key

        # Idempotency: if already registered, return the existing key.
        if self.has(registry_key) and self.get(registry_key) is cls:
            return registry_key

        result = super()._register(registry_key, cls, library_identity)
        if result is not None:
            self._regkey_to_library_id[result] = library_identity.id
        return result

    def _unregister_class(self, registry_key: str) -> type | None:
        self._regkey_to_library_id.pop(registry_key, None)
        return super()._unregister(registry_key)

    def get_classes_for_library(self, library_identity: LibraryIdentity) -> dict[str, type[LibraryState]]:
        """Return all registered state classes that belong to *library_identity*.

        Used by ``LibraryStateContainer.on_library_enabled`` to catch up
        after a library finishes enabling: query this registry for every
        state class the library contributed, then process them as if
        ``CLASS_ADDED`` events had fired.

        Filters by ``library_identity.id`` (string comparison, not object
        identity) so hot-reload of the identity object doesn't cause
        false misses.

        Args:
            library_identity: The library to filter by.

        Returns:
            dict mapping ``registry_key`` → class. Empty if the library
            has registered no state classes (or if it isn't enabled at all).
        """
        target_id = library_identity.id
        result: dict[str, type[LibraryState]] = {}
        for registry_key, lib_id in self._regkey_to_library_id.items():
            if lib_id != target_id:
                continue
            cls = self._classes.get(registry_key)
            if cls is None:
                # Class was registered then removed — skip.
                continue
            result[registry_key] = cls
        return result

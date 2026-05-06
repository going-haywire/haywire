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
from haywire.core.state.base import LibraryState
from haywire.core.state.identity import LibraryStateClassIdentity

logger = logging.getLogger(__name__)


class LibraryStateRegistry(BaseRegistry):
    """Registry for LibraryState classes.

    Registry key format: '{library_id}:state:{class_name}'.
    """

    def _class_filter(self, cls: type) -> bool:
        try:
            return inspect.isclass(cls) and issubclass(cls, LibraryState) and cls is not LibraryState
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

        return super()._register(registry_key, cls, library_identity)

    def _unregister_class(self, registry_key: str) -> type | None:
        return super()._unregister(registry_key)

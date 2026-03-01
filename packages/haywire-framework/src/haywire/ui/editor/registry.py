# packages/haywire-framework/src/haywire/ui/editor_framework/registry.py
"""
EditorTypeRegistry for managing editor type registrations.

Extends BaseRegistry for hot-reload support, folder scanning, lifecycle
events, dependency tracking, and snapshot rollback.
"""

import inspect
import logging
from typing import Optional, Dict

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .base import BaseEditor


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

    def _class_filter(self, cls) -> bool:
        """Return True if cls is a valid, decorated BaseEditor subclass."""
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, BaseEditor)
                and cls is not BaseEditor
                and hasattr(cls, 'class_identity')
            )
        except TypeError:
            return False

    def _register_class(
        self, cls: type, library_identity: Optional[LibraryIdentity] = None
    ) -> 'str | None':
        """Register an editor class by its registry_key."""
        registry_key = cls.class_identity.registry_key
        logging.debug(f"EditorTypeRegistry: Registering '{registry_key}' ({cls.__name__})")
        return super()._register(registry_key, cls, library_identity)

    def _unregister_class(self, registry_key: str) -> 'type | None':
        """Unregister an editor class by its registry_key."""
        return super()._unregister(registry_key)

    def get_by_id(self, registry_id: str) -> 'type | None':
        """Find an editor class by its short registry_id (ignores library prefix).

        Used by AppShell to resolve workspace editor_key strings (short IDs)
        to actual editor classes.

        Args:
            registry_id: Short ID as set in @editor(registry_id=...).

        Returns:
            The editor class, or None if not found.
        """
        for cls in self._classes.values():
            if cls.class_identity.registry_id == registry_id:
                return cls
        return None

    def get_by_default_area(self, area: str) -> Dict[str, type]:
        """Get all editor classes suggested for a given default area.

        Args:
            area: One of 'left', 'middle', 'right', 'bottom'.

        Returns:
            Dict mapping registry_key -> editor class.
        """
        return {
            k: v for k, v in self._classes.items()
            if v.class_identity.default_area == area
        }

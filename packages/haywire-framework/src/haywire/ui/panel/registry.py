# packages/haywire-framework/src/haywire/ui/panel/registry.py
"""
PanelRegistry for managing panel registrations.

Extends BaseRegistry and maintains a secondary index by (editor_key, context)
for fast lookup during context-driven panel rendering.
"""

import inspect
import logging
from typing import Dict, List, Optional

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .base import BasePanel


class PanelRegistry(BaseRegistry):
    """
    Registry of panels.

    Extends BaseRegistry for hot-reload support, folder scanning, lifecycle
    events, and snapshot rollback. Provided as a DI singleton by HaywireModule.

    Panels are indexed by (editor_key, context) for fast lookup. When a
    panel class is reloaded (hot-reload), the index is updated automatically
    via the lifecycle event system.
    """

    def __init__(self):
        super().__init__()
        # Secondary index: (editor_key, context) -> sorted list of panel classes
        self._index: Dict[tuple, List[type]] = {}

    def _class_filter(self, cls) -> bool:
        """Return True if cls is a valid, decorated BasePanel subclass."""
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, BasePanel)
                and cls is not BasePanel
                and hasattr(cls, 'class_identity')
            )
        except TypeError:
            return False

    def _register_class(
        self, cls: type, library_identity: Optional[LibraryIdentity] = None
    ) -> 'str | None':
        """Register a panel class and update the (editor_key, context) index."""
        registry_key = cls.class_identity.registry_key
        result = super()._register(registry_key, cls, library_identity)
        if result:
            self._index_panel(cls)
        logging.debug(
            f"PanelRegistry: Registered '{registry_key}' -> "
            f"editor='{cls.class_identity.editor_key}', context='{cls.class_identity.context}'"
        )
        return result

    def _unregister_class(self, registry_key: str) -> 'type | None':
        """Unregister a panel class and remove it from the index."""
        removed = super()._unregister(registry_key)
        if removed:
            self._deindex_panel(removed)
        return removed

    def _index_panel(self, cls: type) -> None:
        """Add cls to the secondary (editor_key, context) index, sorted by order."""
        idx_key = (cls.class_identity.editor_key, cls.class_identity.context)
        if idx_key not in self._index:
            self._index[idx_key] = []
        if cls not in self._index[idx_key]:
            self._index[idx_key].append(cls)
        self._index[idx_key].sort(key=lambda c: c.class_identity.order)

    def _deindex_panel(self, cls: type) -> None:
        """Remove cls from the secondary index."""
        idx_key = (cls.class_identity.editor_key, cls.class_identity.context)
        if idx_key in self._index and cls in self._index[idx_key]:
            self._index[idx_key].remove(cls)

    def get_panels(self, editor_key: str, context: str) -> List[type]:
        """Get all panels for a given editor type and context, sorted by order.

        Args:
            editor_key: Registry key of the editor type.
            context: Context string, e.g. 'node', 'graph', 'edge'.

        Returns:
            List of panel classes sorted by class_identity.order (ascending).
        """
        return list(self._index.get((editor_key, context), []))

    def get_all_for_editor(self, editor_key: str) -> Dict[str, List[type]]:
        """Get all panels for an editor, grouped by context.

        Args:
            editor_key: Registry key of the editor type.

        Returns:
            Dict mapping context string -> sorted list of panel classes.
        """
        result: Dict[str, List[type]] = {}
        for (ek, ctx), panels in self._index.items():
            if ek == editor_key:
                result[ctx] = list(panels)
        return result

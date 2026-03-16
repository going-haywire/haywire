# packages/haywire-core/src/haywire/ui/panel/registry.py
"""
PanelRegistry for managing panel and scope registrations.

Extends BaseRegistry and maintains:
- A secondary index by (editor_key, scope_id) for fast panel lookup.
- A scope index by (editor_id, scope_id) for toolbar metadata.
"""

import inspect
import logging
from typing import Dict, List, Optional

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .base import BasePanel
from .scope import ScopeDescriptor


class PanelRegistry(BaseRegistry):
    """
    Registry of panels and scope descriptors.

    Extends BaseRegistry for hot-reload support, folder scanning, lifecycle
    events, and snapshot rollback. Provided as a DI singleton by HaywireModule.

    Panels are indexed by (editor_key, scope_id) for fast lookup.  A panel
    that declares scope=['my_lib', 'node'] appears in both index entries.

    Scopes are registered separately via register_scope() — typically called
    from BaseLibrary.register_components() before the panels folder is scanned.
    If a panel references a scope_id that has no registered ScopeDescriptor, it
    is still indexed and will appear when panels are queried, but get_scopes()
    will not include that scope in the toolbar.
    """

    def __init__(self):
        super().__init__()
        # (editor_key, scope_id) -> sorted list of panel classes
        self._index: Dict[tuple, List[type]] = {}
        # (editor_id, scope_id) -> ScopeDescriptor
        self._scope_index: Dict[tuple, ScopeDescriptor] = {}

    # ------------------------------------------------------------------
    # Scope registration
    # ------------------------------------------------------------------

    def register_scope(self, editor_id: str, descriptor: ScopeDescriptor) -> None:
        """
        Register a scope descriptor for a given editor.

        Should be called from BaseLibrary.register_components() before
        scanning the panels folder, so scope metadata is available when
        panels referencing that scope are registered.

        Args:
            editor_id:   Registry ID of the editor (e.g. 'properties').
            descriptor:  ScopeDescriptor instance defining the tab.
        """
        key = (editor_id, descriptor.scope_id)
        self._scope_index[key] = descriptor
        logging.debug(
            f"PanelRegistry: Registered scope '{descriptor.scope_id}' "
            f"for editor '{editor_id}'"
        )

    def get_scopes(self, editor_id: str) -> List[ScopeDescriptor]:
        """
        Return all registered scope descriptors for an editor, sorted by order.

        Args:
            editor_id: Registry ID of the editor (e.g. 'properties').

        Returns:
            List of ScopeDescriptor instances sorted by ScopeDescriptor.order.
        """
        result = [
            desc
            for (eid, _), desc in self._scope_index.items()
            if eid == editor_id
        ]
        result.sort(key=lambda d: d.order)
        return result

    # ------------------------------------------------------------------
    # Panel registration (BaseRegistry overrides)
    # ------------------------------------------------------------------

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
        """Register a panel class and update the (editor_key, scope_id) index."""
        registry_key = cls.class_identity.registry_key
        result = super()._register(registry_key, cls, library_identity)
        if result:
            self._index_panel(cls)
        logging.debug(
            f"PanelRegistry: Registered '{registry_key}' -> "
            f"editor='{cls.class_identity.editor_key}', "
            f"scope={cls.class_identity.scope!r}"
        )
        return result

    def _unregister_class(self, registry_key: str) -> 'type | None':
        """Unregister a panel class and remove it from the index."""
        removed = super()._unregister(registry_key)
        if removed:
            self._deindex_panel(removed)
        return removed

    def _index_panel(self, cls: type) -> None:
        """Add cls to the (editor_key, scope_id) index for every declared scope."""
        editor_key = cls.class_identity.editor_key
        for scope_id in cls.class_identity.scope:
            idx_key = (editor_key, scope_id)
            if idx_key not in self._index:
                self._index[idx_key] = []
            if cls not in self._index[idx_key]:
                self._index[idx_key].append(cls)
            self._index[idx_key].sort(key=lambda c: c.class_identity.order)

    def _deindex_panel(self, cls: type) -> None:
        """Remove cls from the index for every declared scope."""
        editor_key = cls.class_identity.editor_key
        for scope_id in cls.class_identity.scope:
            idx_key = (editor_key, scope_id)
            if idx_key in self._index and cls in self._index[idx_key]:
                self._index[idx_key].remove(cls)

    def get_panels(self, editor_key: str, scope_id: str) -> List[type]:
        """
        Get all panels for a given editor and scope, sorted by order.

        Args:
            editor_key: Registry key of the editor type.
            scope_id:   Scope ID string, e.g. 'node', 'graph', 'edge'.

        Returns:
            List of panel classes sorted by class_identity.order (ascending).
        """
        return list(self._index.get((editor_key, scope_id), []))

    def get_all_for_editor(self, editor_key: str) -> Dict[str, List[type]]:
        """
        Get all panels for an editor, grouped by scope_id.

        Args:
            editor_key: Registry key of the editor type.

        Returns:
            Dict mapping scope_id -> sorted list of panel classes.
        """
        result: Dict[str, List[type]] = {}
        for (ek, scope_id), panels in self._index.items():
            if ek == editor_key:
                result[scope_id] = list(panels)
        return result

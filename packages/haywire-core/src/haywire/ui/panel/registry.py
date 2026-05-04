# packages/haywire-core/src/haywire/ui/panel/registry.py
"""
PanelRegistry for managing panel registrations.

Extends BaseRegistry. Panels are looked up via get_panels_for, which
matches a class's @panel(action=..., focus=...) declaration against
an actions_provider (structural isinstance check) and a Focus class
(identity match).
"""

import inspect
import logging
from typing import Any, Iterable, List, Optional

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .panel import Panel

logger = logging.getLogger(__name__)


class PanelRegistry(BaseRegistry):
    """Registry of panels.

    Extends BaseRegistry for hot-reload support, folder scanning, lifecycle
    events, and snapshot rollback. Provided as a DI singleton by HaywireModule.

    Panels declare action= (Protocol/ABC class) and focus= (Focus subclass)
    via the @panel decorator. Hosts call get_panels_for(actions_provider,
    focus) to retrieve panels whose action contract is structurally satisfied
    by the provider AND whose focus matches.
    """

    def __init__(self):
        super().__init__()

    def _class_filter(self, cls) -> bool:
        """Return True if cls is a valid, decorated Panel subclass."""
        try:
            if not inspect.isclass(cls):
                return False
            if not hasattr(cls, "class_identity"):
                return False
            if cls is Panel:
                return False
            return issubclass(cls, Panel)
        except TypeError:
            return False

    def _register_class(self, cls: type, library_identity: Optional[LibraryIdentity] = None) -> "str | None":
        """Register a panel class."""
        registry_key = cls.class_identity.registry_key
        result = super()._register(registry_key, cls, library_identity)
        if result:
            action = getattr(cls.class_identity, "action", None)
            focus = getattr(cls.class_identity, "focus", None)
            logger.debug(
                f"PanelRegistry: Registered '{registry_key}' -> "
                f"action={getattr(action, '__name__', '?')}, "
                f"focus={getattr(focus, '__name__', '?')}"
            )
        return result

    def _unregister_class(self, registry_key: str) -> "type | None":
        """Unregister a panel class."""
        return super()._unregister(registry_key)

    # ------------------------------------------------------------------
    # Contract-centric lookup
    # ------------------------------------------------------------------

    def get_panels_for(
        self,
        actions_provider: Any,
        focus: type,  # Focus subclass
    ) -> List[type]:
        """Return panels whose action contract is satisfied by actions_provider
        AND whose focus matches the given focus class.

        Sorted by class_identity.order (ascending).
        """
        result: List[type] = []
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            action = getattr(identity, "action", None)
            panel_focus = getattr(identity, "focus", None)
            if action is None or panel_focus is None:
                continue
            if panel_focus is not focus:
                continue
            if not isinstance(actions_provider, action):
                continue
            result.append(cls)
        result.sort(key=lambda c: getattr(getattr(c, "class_identity", None), "order", 100))
        return result

    def get_focuses_for(self, actions_provider: Any) -> List[type]:
        """Return the set of focus classes referenced by any panel whose
        action contract is satisfied by actions_provider.
        """
        focuses: List[type] = []
        seen: set[type] = set()
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            action = getattr(identity, "action", None)
            focus = getattr(identity, "focus", None)
            if action is None or focus is None:
                continue
            if focus in seen:
                continue
            if isinstance(actions_provider, action):
                seen.add(focus)
                focuses.append(focus)
        return focuses

    def _all_panel_classes(self) -> Iterable[type]:
        """Iterate all registered panel classes."""
        return self._classes.values()

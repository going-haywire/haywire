# packages/haywire-core/src/haywire/ui/panel/registry.py
"""
PanelRegistry for managing panel registrations.

Extends BaseRegistry. Two query surfaces:
  - get_panels_for_focus(focus): display panels for PropertiesEditor —
    panels with no `action_protocol` whose focus matches.
  - get_panels_for_action(action_protocol, focus): action panels for
    context-menu hosts — panels whose `action_protocol` matches AND
    whose focus matches.
Focus matching is by Focus.id (stable across hot-reload).
"""

import inspect
import logging
from typing import Iterable, List, Set, TYPE_CHECKING

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .base import BasePanel

if TYPE_CHECKING:
    from haywire.core.session.signals import Signal

logger = logging.getLogger(__name__)


class PanelRegistry(BaseRegistry):
    """Registry of panels.

    Provided as a DI singleton by HaywireModule.
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
            if cls is BasePanel:
                return False
            return issubclass(cls, BasePanel)
        except TypeError:
            return False

    def _register_class(self, cls: type[BasePanel], library_identity: LibraryIdentity) -> "str | None":
        registry_key = cls.class_identity.registry_key
        result = super()._register(registry_key, cls, library_identity)
        if result:
            action_protocol = getattr(cls.class_identity, "action_protocol", None)
            focus = getattr(cls.class_identity, "focus", None)
            logger.debug(
                f"PanelRegistry: Registered '{registry_key}' -> "
                f"action_protocol={getattr(action_protocol, '__name__', 'None')}, "
                f"focus={getattr(focus, '__name__', 'None')}"
            )
        return result

    def _unregister_class(self, registry_key: str) -> "type | None":
        return super()._unregister(registry_key)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_panels_for_focus(self, focus: type) -> List[type[BasePanel]]:
        """Display panels for the given focus.

        Returns panels whose ``action_protocol is None`` AND whose
        ``focus.id`` matches the given focus's id. Sorted by ``order``.

        Used by PropertiesEditor (long-lived, focus-routed surface).
        """
        wanted_id = getattr(focus, "id", None)
        result: List[type[BasePanel]] = []
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            if getattr(identity, "action_protocol", None) is not None:
                continue
            panel_focus = getattr(identity, "focus", None)
            if panel_focus is None or getattr(panel_focus, "id", None) != wanted_id:
                continue
            result.append(cls)
        result.sort(key=lambda c: getattr(getattr(c, "class_identity", None), "order", 100))
        return result

    def get_panels_for_action(
        self,
        action_protocol: type,
        focus: type,
    ) -> List[type[BasePanel]]:
        """Action panels for the given (action_protocol, focus) pair.

        Returns panels whose ``action_protocol is action_protocol`` AND
        whose ``focus.id`` matches. Sorted by ``order``.

        Used by context-menu hosts. The host satisfies action_protocol
        structurally; mount-time injection sets ``panel.actions = host``.
        """
        wanted_focus_id = getattr(focus, "id", None)
        result: List[type[BasePanel]] = []
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            # action_protocol uses class identity (not a stable id) because panels and
            # their action protocols are declared in the same library scope and reload
            # together via decorator re-running.
            if getattr(identity, "action_protocol", None) is not action_protocol:
                continue
            panel_focus = getattr(identity, "focus", None)
            if panel_focus is None or getattr(panel_focus, "id", None) != wanted_focus_id:
                continue
            result.append(cls)
        result.sort(key=lambda c: getattr(getattr(c, "class_identity", None), "order", 100))
        return result

    def get_display_focuses(self) -> List[type]:
        """Distinct focuses referenced by display panels (no action_protocol).

        Deduplicated by Focus.id. Used by PropertiesEditor to build its
        focus toolbar.
        """
        focuses: List[type] = []
        seen_ids: set[str] = set()
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            if getattr(identity, "action_protocol", None) is not None:
                continue
            focus = getattr(identity, "focus", None)
            if focus is None:
                continue
            focus_id = getattr(focus, "id", None)
            if focus_id is None or focus_id in seen_ids:
                continue
            seen_ids.add(focus_id)
            focuses.append(focus)
        return focuses

    def get_redraw_signals_for_focus(self, focus: type) -> Set[type["Signal"]]:
        """Union of redraw_on signal types contributed by display panels
        for the given focus.

        Context-menu surfaces are ephemeral (open, draw, dismiss) and do
        not maintain a subscription set; only PropertiesEditor consumes
        this. Matching mirrors get_panels_for_focus.
        """
        wanted_id = getattr(focus, "id", None)
        signals: Set[type["Signal"]] = set()
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            if getattr(identity, "action_protocol", None) is not None:
                continue
            panel_focus = getattr(identity, "focus", None)
            if panel_focus is None or getattr(panel_focus, "id", None) != wanted_id:
                continue
            signals.update(getattr(identity, "redraw_on", ()))
        return signals

    def _all_panel_classes(self) -> Iterable[type]:
        return self._classes.values()

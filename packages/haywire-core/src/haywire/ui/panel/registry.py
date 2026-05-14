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
from typing import Any, Iterable, List, Set, TYPE_CHECKING

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .base import BasePanel

if TYPE_CHECKING:
    from haywire.core.session.events import ContextSignal

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
            if cls is BasePanel:
                return False
            return issubclass(cls, BasePanel)
        except TypeError:
            return False

    def _register_class(self, cls: type[BasePanel], library_identity: LibraryIdentity) -> "str | None":
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
    ) -> List[type[BasePanel]]:
        """Return panels whose action contract is satisfied by actions_provider
        AND whose focus matches the given focus class.

        Focus matching is by ``Focus.id`` (the stable identifier), not by
        class identity — class objects can drift after hot-reload, but ids
        remain stable.

        Sorted by class_identity.order (ascending).
        """
        wanted_id = getattr(focus, "id", None)
        result: List[type[BasePanel]] = []
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            action = getattr(identity, "action", None)
            panel_focus = getattr(identity, "focus", None)
            if action is None or panel_focus is None:
                continue
            if getattr(panel_focus, "id", None) != wanted_id:
                continue
            if not isinstance(actions_provider, action):
                continue
            result.append(cls)
        result.sort(key=lambda c: getattr(getattr(c, "class_identity", None), "order", 100))
        return result

    def get_focuses_for(self, actions_provider: Any) -> List[type]:
        """Return the set of focus classes referenced by any panel whose
        action contract is satisfied by actions_provider.

        Deduplicated by ``Focus.id`` rather than class identity, so a
        single Focus that's been hot-reloaded (and now exists as multiple
        class objects across panels of different reload generations)
        appears once in the result.
        """
        focuses: List[type] = []
        seen_ids: set[str] = set()
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            action = getattr(identity, "action", None)
            focus = getattr(identity, "focus", None)
            if action is None or focus is None:
                continue
            focus_id = getattr(focus, "id", None)
            if focus_id is None or focus_id in seen_ids:
                continue
            if isinstance(actions_provider, action):
                seen_ids.add(focus_id)
                focuses.append(focus)
        return focuses

    def get_redraw_events_for(self, actions_provider: Any) -> Set[type["ContextSignal"]]:
        """Return the union of ``redraw_on`` event types contributed by every
        registered panel whose action contract ``actions_provider`` satisfies.

        Used by editor hosts (via the event-bus redesign — see
        ``internals/speculatives/event_bus_redesign.md``) to compute their
        effective subscription set on the session bus. The host subscribes
        to every event type in the returned set; when any of them publishes
        the host redraws so currently-visible panels re-mount with fresh
        state (panels themselves have no independent dispatch — they ride
        the host's redraw).

        Panels with an empty ``redraw_on`` tuple contribute nothing. Panels
        whose ``action`` is None are skipped (legacy / partially-decorated
        registrations); panels whose action ``isinstance`` check fails for
        ``actions_provider`` are skipped (this host doesn't satisfy their
        contract).

        Args:
            actions_provider: The host instance whose effective subscription
                set we are computing. Typically the editor instance itself,
                which structurally implements one or more action Protocols.

        Returns:
            A set of ``ContextSignal`` subclasses. Empty if no registered
            panel applies to this host.
        """
        events: Set[type["ContextSignal"]] = set()
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            action = getattr(identity, "action", None)
            if action is None:
                continue
            redraw_on = getattr(identity, "redraw_on", ())
            if not redraw_on:
                continue
            if not isinstance(actions_provider, action):
                continue
            events.update(redraw_on)
        return events

    def _all_panel_classes(self) -> Iterable[type]:
        """Iterate all registered panel classes."""
        return self._classes.values()

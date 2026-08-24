# packages/haywire-core/src/haywire/ui/panel/registry.py
"""
PanelRegistry for managing panel registrations.

Extends BaseRegistry. Three query surfaces, all routing on ``Surface.id``:
  - get_panels(surface): the panels on one surface, sorted by order.
  - get_root_surfaces(): surfaces named by some panel's ``surface=`` and by
    no panel's ``hosts=`` — what the properties strip filters down to.
  - get_redraw_signals(surface): the union of ``redraw_on`` across that
    surface's whole ``hosts=`` tree, which a long-lived host subscribes to
    on mount.

All three compare surfaces **by id**, never by class object: ``hosts=`` holds
classes captured at decoration time, and a panel may host a surface from a
library that reloads on its own schedule (docs/adr/0009-surface-id-stable-key.md).
"""

import inspect
import logging
from typing import Dict, Iterable, List, Optional, Set, TYPE_CHECKING

from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity

from .base import BasePanel

if TYPE_CHECKING:
    from haywire.core.signals import Signal
    from haywire.ui.surface import Surface

logger = logging.getLogger(__name__)


class PanelRegistry(BaseRegistry[BasePanel]):
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

    def _register_class(
        self, cls: type[BasePanel], library_identity: Optional[LibraryIdentity] = None
    ) -> "str | None":
        registry_key = cls.class_identity.registry_key
        result = super()._register(registry_key, cls, library_identity)
        if result:
            surface = getattr(cls.class_identity, "surface", None)
            hosts = getattr(cls.class_identity, "hosts", ())
            logger.debug(
                f"PanelRegistry: Registered '{registry_key}' -> "
                f"surface={getattr(surface, 'id', 'None')}, "
                f"hosts=({', '.join(getattr(h, 'id', '?') for h in hosts)})"
            )
            self._report_cycles(cls)
        return result

    def _unregister_class(self, registry_key: str) -> "type[BasePanel] | None":
        return super()._unregister(registry_key)

    # ------------------------------------------------------------------
    # Registration-time validation
    # ------------------------------------------------------------------

    def _report_cycles(self, cls: type[BasePanel]) -> None:
        """Log a warning if ``cls`` closes a cycle in the ``hosts=`` graph.

        **Logged, not rejected.** The graph closes only through
        surface → panels, so a cycle first becomes visible when the *second*
        panel registers; refusing that one would drop a panel from the catalog
        based on which library loaded first, and two libraries each sound
        alone would then fail differently depending on install order.
        Enforcement is the render-time re-entry guard in
        ``BasePanel.render_surface``, which has to exist regardless — so
        reporting here costs nothing and gives the author both signals.
        """
        identity = getattr(cls, "class_identity", None)
        start = getattr(getattr(identity, "surface", None), "id", None)
        if start is None:
            return
        # Walk hosts= edges from this panel's own surface, carrying the panel
        # that contributed each surface id AND the surface *that panel* sits
        # on — the "other edge" of a two-hop cycle, otherwise lost by the
        # time the walk reaches `start` again. Reaching `start` a second time
        # means this registration closed a cycle.
        seen: set[str] = set()
        frontier: list[tuple[str | None, "type[BasePanel] | None", str | None]] = [
            (getattr(h, "id", None), cls, start) for h in getattr(identity, "hosts", ())
        ]
        while frontier:
            current, via, via_surface = frontier.pop()
            if current is None or current in seen:
                continue
            seen.add(current)
            if current == start:
                other_key = getattr(getattr(via, "class_identity", None), "registry_key", via)
                logger.warning(
                    "Panel host cycle: %s sits on surface %r and hosts a chain "
                    "reaching %r again, via %s on surface %r. Both panels still "
                    "register; the render-time re-entry guard refuses to recurse.",
                    getattr(identity, "registry_key", cls.__name__),
                    start,
                    current,
                    other_key,
                    via_surface,
                )
                return
            for other in self._all_panel_classes():
                other_identity = getattr(other, "class_identity", None)
                if other_identity is None:
                    continue
                if getattr(getattr(other_identity, "surface", None), "id", None) != current:
                    continue
                frontier.extend(
                    (getattr(h, "id", None), other, current) for h in getattr(other_identity, "hosts", ())
                )

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_panels(self, surface: type) -> List[type[BasePanel]]:
        """Panels on ``surface``, matched by ``id``, sorted by ``order``.

        The single panel query. There is no display/action fork any more —
        which panels a surface yields depends on the surface id alone.
        """
        wanted_id = getattr(surface, "id", None)
        result: List[type[BasePanel]] = []
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            panel_surface = getattr(identity, "surface", None)
            if panel_surface is None or getattr(panel_surface, "id", None) != wanted_id:
                continue
            result.append(cls)
        result.sort(key=lambda c: getattr(getattr(c, "class_identity", None), "order", 100))
        return result

    def get_root_surfaces(self) -> List[type["Surface"]]:
        """Surfaces named by some panel's ``surface=`` and by no panel's ``hosts=``.

        Deduped by id. Read from the **panel catalog**, never from
        ``_SURFACE_BY_ID``: that map never evicts, so a surface whose library
        was uninstalled would linger there as a ghost tab.

        Root-ness is not by itself the properties strip's filter — menu and
        toolbar surfaces are roots too. The strip additionally requires
        ``presentation`` (ADR-0029); that policy belongs to the one host that
        *discovers* its list rather than naming it.
        """
        hosted_ids: set[str] = set()
        named: Dict[str, type["Surface"]] = {}
        for cls in self._all_panel_classes():
            identity = getattr(cls, "class_identity", None)
            if identity is None:
                continue
            surface = getattr(identity, "surface", None)
            surface_id = getattr(surface, "id", None)
            if surface is not None and surface_id is not None:
                named.setdefault(surface_id, surface)
            for hosted in getattr(identity, "hosts", ()):
                hosted_id = getattr(hosted, "id", None)
                if hosted_id is not None:
                    hosted_ids.add(hosted_id)
        return [surface for surface_id, surface in named.items() if surface_id not in hosted_ids]

    def get_redraw_signals(self, surface: type) -> Set[type["Signal"]]:
        """Union of ``redraw_on`` across ``surface``'s whole ``hosts=`` tree.

        Walks surface → its panels → the surfaces those panels host,
        transitively, visited-set guarded. It has to be static: a long-lived
        host subscribes on mount, before anything has rendered, so a union
        that could only be discovered by rendering would miss every nested
        panel — silently, since a missing subscription looks exactly like a
        signal that never fired.

        Transient hosts (context menus) subscribe to nothing and never call
        this.
        """
        signals: Set[type["Signal"]] = set()
        visited: set[str] = set()
        frontier = [getattr(surface, "id", None)]
        while frontier:
            current = frontier.pop()
            if current is None or current in visited:
                continue
            visited.add(current)
            for cls in self._all_panel_classes():
                identity = getattr(cls, "class_identity", None)
                if identity is None:
                    continue
                panel_surface = getattr(identity, "surface", None)
                if panel_surface is None or getattr(panel_surface, "id", None) != current:
                    continue
                signals.update(getattr(identity, "redraw_on", ()))
                frontier.extend(getattr(h, "id", None) for h in getattr(identity, "hosts", ()))
        return signals

    def _all_panel_classes(self) -> Iterable[type[BasePanel]]:
        return self._classes.values()

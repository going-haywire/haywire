# packages/haywire-core/src/haywire/ui/panel/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from haywire.core.library.identity import LibraryIdentity

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.ui.panel.layout import PanelLayout
    from haywire.ui.panel.identity import PanelIdentity
    from haywire.ui.surface import Surface


class BasePanel(ABC):
    """Base class for panels.

    Subclasses are decorated with `@panel(...)` and inherit from `BasePanel`::

        @panel(
            surface=SelectionMenu,
            label="Delete Selection",
        )
        class DeleteSelectionPanel(BasePanel):
            actions: SelectionActions  # -> type-checker visibility only

            def draw(self, ctx, layout):
                self.actions.delete_selection()

    A panel whose surface declares no ``provides`` needs no ``actions:``
    annotation and leaves ``self.actions`` at ``None``.

    A panel may also *host* surfaces of its own, declaring them with
    ``hosts=`` and rendering one with :meth:`render_surface` inside
    ``draw()``. That is the whole of nesting — menus, submenus, toolbars and
    inspector tabs are the same rule at different depths (ADR-0029).
    """

    # Set by @panel decorator.
    class_identity: ClassVar["PanelIdentity"]
    class_library: ClassVar[LibraryIdentity]

    # Host instance injected at mount time when the panel's surface declares
    # a ``provides`` Protocol the host satisfies. Panels on a surface with no
    # contract leave it as None.
    actions: Any = None

    # Framework-injected by ``render_panel`` (never set by an author — the
    # ``_hw_`` prefix marks framework-owned state; ``hb_*`` is the namespace
    # reserved for authors, see docs/components/nodes/node-canon.md).
    # ``render_surface`` needs both: the registry to query the nested
    # surface's panels, and the host's state bag to pass down.
    _hw_registry: Any = None
    _hw_state_bag: Any = None

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        """Return whether the panel applies given current state."""
        return True

    @abstractmethod
    def draw(
        self,
        ctx: "SessionContext",
        layout: "PanelLayout",
    ) -> None:
        """Render the panel's content. Called only when poll() returned True."""

    def draw_disabled(  # noqa: B027 — the no-op default is the contract, not an oversight
        self,
        ctx: "SessionContext",
        layout: "PanelLayout",
    ) -> None:
        """Render the panel's *inapplicable* state. Called when poll() is False.

        Defaults to a no-op — a panel with no opinion simply vanishes, which
        is what every panel does today. Override to follow the platform
        convention for menus: an inapplicable command greys rather than
        disappearing (``hui.menu_row(..., enabled=False)`` /
        ``hui.submenu_row(..., enabled=False)``).

        This body must not touch the state ``poll()`` gated on — that is the
        whole reason it is a second method rather than a branch inside
        ``draw()``. A panel denied by ``access=`` renders *neither* method:
        a greyed entry advertises what the principal may not have.
        """

    def render_surface(
        self,
        surface: type["Surface"],
        ctx: "SessionContext",
        actions: object | None = None,
    ) -> None:
        """Render ``surface``'s panels here, inside the caller's layout context.

        The nesting call. Pairs with ``host_rendering.render_panel`` — this is
        composition over the same machinery the outer hosts use, not new
        machinery.

        ``actions`` decides the host the nested panels receive:

        ==========  ==========================================  ===============
        Case        What the panel is                           Host passed
        ==========  ==========================================  ===============
        Pipe        arranges layout only (the common case)      ``self.actions``
        Own         implements the surface's Protocol itself    ``self``
        Delegate    neither implements nor received it          ``obj``
        ==========  ==========================================  ===============

        The host is **piped, never inferred** (ADR-0029). The ``isinstance``
        check below validates the object that was *chosen*; it is never a way
        of choosing one — a structural check cannot tell "I implement this"
        from "I accidentally match", and a member-less Protocol matches
        everything.
        """
        from nicegui import ui

        from haywire.ui import elements as hui
        from haywire.ui.panel.host_rendering import (
            _poll_surface,
            _render_path,
            partition_panels,
            render_panel,
            render_path_extended,
        )
        from haywire.ui.panel.layout import PanelLayout

        # 1. Declared? hosts= is what the registry walks for the redraw union
        #    and the root/nested split; rendering outside it makes that tree a
        #    lie. Compared by id, not class object — a panel may host a surface
        #    from another library that reloads on its own schedule (ADR-0009).
        identity = getattr(self, "class_identity", None)
        declared = {getattr(s, "id", None) for s in getattr(identity, "hosts", ())}
        if getattr(surface, "id", None) not in declared:
            hui.error_label(
                f"{type(self).__name__} does not declare hosts={getattr(surface, '__name__', surface)}"
            )
            return

        # 2. Re-entry guard — this IS the cycle enforcement, not a backstop:
        #    registration only logs. The path is per-render, not global; the
        #    same surface may legitimately appear twice side by side.
        if surface.id in _render_path.get():
            hui.error_label(f"Surface {surface.id!r} is already being rendered")
            return

        # 3. Surface gate, under the error boundary like every other poll.
        #    Ahead of host validation: a surface that does not apply right now
        #    has no business complaining about hosts.
        if not _poll_surface(surface, ctx):
            return

        # 4. Host. Piped by default, never inferred.
        host = actions if actions is not None else self.actions
        want = getattr(surface, "provides", None)
        if want is not None and not isinstance(host, want):
            hui.error_label(f"Host {type(host).__name__} does not satisfy {want.__name__}")
            return

        # 5. Shared filter + renderer, unchanged from the outer hosts. Both
        #    lists render interleaved in order, so a menu does not reshuffle
        #    as the selection changes.
        registry = self._hw_registry
        if registry is None:
            hui.error_label(f"{type(self).__name__} has no panel registry to render {surface.id!r} from")
            return
        applies, disabled = partition_panels(registry.get_panels(surface), ctx)
        by_order = sorted(
            [(cls, False) for cls in applies] + [(cls, True) for cls in disabled],
            key=lambda pair: getattr(pair[0].class_identity, "order", 100),
        )
        layout = PanelLayout(ui.element("div"), state_bag=self._hw_state_bag)
        with render_path_extended(surface.id):
            for cls, is_disabled in by_order:
                render_panel(
                    cls,
                    ctx,
                    layout,
                    actions_host=host,
                    registry=registry,
                    disabled=is_disabled,
                )

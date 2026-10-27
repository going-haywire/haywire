from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, ClassVar
import logging

import nicegui.ui as ui

from haywire.core.access import LevelMode
from haywire.core.library.identity import LibraryIdentity
from haywire.core.types import DataPort
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.registry.identity import BaseIdentity

from .. import elements as hui
from ..access_stamp import stamp_requires
from ..widget.interface import IWidget
from ..widget.factory_interface import IWidgetFactory
from ..widget.sizing import stamp_size_declaration
from .nodecard import UINodeCard
from .pin_icons import DEFAULT_PIN_ICONS, PinIconResolver

if TYPE_CHECKING:
    from haywire.core.errors import HaywireException
    from haywire.core.graph.edit_route import EditRoute
    from haywire.core.node.node_warning import NodeWarning
    from haywire.core.settings.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class SkinIdentity(BaseIdentity):
    """Core identifying attributes of a skin"""

    _is_default: bool = False
    _default_priority: int = 0
    _is_error: bool = False
    _error_priority: int = 0


class BaseSkin(ABC):
    """
    Abstract base class for all NodeSkin classes.

    NodeSkin classes define the look and structure of nodes.
    They are cached and reused by the SkinFactory.

    Override ``pin_icons`` with a ``PinIconResolver`` subclass to restyle every
    pin this skin draws; a glyph declared on a port or its type still wins.
    """

    class_identity: ClassVar[SkinIdentity]
    class_library: ClassVar[LibraryIdentity]

    #: Glyph vocabulary for this skin's pins, passed to ``render_pin``.
    pin_icons: ClassVar[PinIconResolver] = DEFAULT_PIN_ICONS

    def __init__(self, widget_factory: IWidgetFactory):
        """
        Initialize the skin with a widget factory.

        Args:
            widget_factory: Factory for creating widget instances
        """
        self._widget_factory: IWidgetFactory = widget_factory
        self._nodeids_widget_instances: dict[str, dict[str, IWidget]] = {}
        # The route each node's card widgets write through, held for the length of one render.
        self._nodeids_routes: dict[str, EditRoute | None] = {}
        # Cleanups a render registers, handed to its card when the render ends.
        self._nodeids_cleanups: dict[str, list[Callable[[], None]]] = {}

    def _render(
        self, wrapper: NodeWrapper, *, on_stage: bool = False, route: EditRoute | None = None
    ) -> UINodeCard:
        """Draw *wrapper*'s card: :meth:`render` into a fresh card.

        ``on_stage`` is forwarded to :meth:`render`. Every widget :meth:`render_widget`
        draws for this card writes through *route*, at level mode ``OPERATE``;
        ``None`` refuses every write.
        """
        self._nodeids_routes[wrapper.node_id] = route

        def draw(card: ui.card) -> None:
            self.render(card, wrapper, on_stage=on_stage)
            self.render_markers(card, wrapper, on_stage=on_stage)

        try:
            return self._render_into_card(wrapper, draw)
        finally:
            self._nodeids_routes.pop(wrapper.node_id, None)

    def _render_into_card(self, wrapper: NodeWrapper, draw: Callable[[ui.card], object]) -> UINodeCard:
        ui_nodeCard: UINodeCard = UINodeCard()
        try:
            # Initialize node_id storage for widget instances
            self._nodeids_widget_instances[wrapper.node_id] = {}
            self._nodeids_cleanups[wrapper.node_id] = []

            draw(ui_nodeCard.get_card())

            ui_nodeCard.set_widget_instances(self._nodeids_widget_instances[wrapper.node_id])
            for callback in self._nodeids_cleanups.pop(wrapper.node_id, []):
                ui_nodeCard.add_cleanup(callback)

            # Clear widget instances for next render
            self._nodeids_widget_instances[wrapper.node_id] = {}

            return ui_nodeCard

        except Exception:
            # What the failed render registered still has to be released.
            for callback in self._nodeids_cleanups.pop(wrapper.node_id, []):
                callback()
            # Clean up any partially created UI elements
            if ui_nodeCard is not None:
                try:
                    # Remove all children and delete the main card
                    ui_card = ui_nodeCard.get_card()
                    ui_card.clear()
                    ui_card.delete()
                except Exception as cleanup_error:
                    logger.error(f"Error during UI cleanup: {cleanup_error}")

            # Re-raise the original exception so the factory can handle it
            raise

    def render_markers(self, card: ui.card, wrapper: NodeWrapper, *, on_stage: bool) -> None:
        """Draw the markers above *card*: the diagnostics badge and the comment badge.

        Called after :meth:`render` for every card, so every skin shows them. The
        default draws both in the patch view and nothing on the stage, a
        performance view. Override it to place them differently, or to draw none.

        Args:
            card: The card :meth:`render` drew into.
            on_stage: True when the card is drawn for a stage view.

        Example::

            def render_markers(self, card, wrapper, *, on_stage):
                pass  # a skin too small for badges
        """
        if on_stage:
            return
        runtime_errors = wrapper.state.get_errors() or []
        deprecation_str = wrapper.node.identity.deprecation_warning
        with card:
            if runtime_errors or wrapper.state.has_warning() or deprecation_str:
                self._render_diagnostics_button(
                    runtime_errors,
                    wrapper.state.warnings,
                    wrapper.node_id,
                    deprecation_str=deprecation_str,
                )
            self._render_comment_badge(wrapper)

    def _render_comment_badge(self, wrapper: NodeWrapper) -> None:
        """A badge for the node's comment, if it has one. Hover to read it.

        Emptiness is the whole visibility rule (ADR 0032) — no companion flag.
        Drawn unconditionally so a note survives folding, where it matters
        most: a folded node is a box with a title.

        The tooltip is built eagerly, unlike a pin's, because there is at most
        one per node and only on nodes that have a comment.
        """
        try:
            comment = (wrapper.node.props.comment or "").strip()
        except Exception:
            return
        if not comment:
            return

        btn = ui.button(icon=hui.icon.message).props("flat dense round")
        btn.classes("text-xl px-2 py-1")
        # Left of the diagnostics badge, which sits at the same offset on the
        # right — so a node with both shows them side by side rather than
        # stacked on top of each other.
        btn.style("position: absolute; top: -25px; right: 32px;")
        btn.props(f'data-node-id="{wrapper.node_id}"')
        # The comment shows in every level mode.
        stamp_requires(btn, LevelMode.VIEW)
        with btn:
            ui.tooltip(comment).classes("text-xs whitespace-normal").style("max-width: 22rem")

    def _render_diagnostics_button(
        self,
        errors: list["HaywireException"],
        warnings: list["NodeWarning"],
        node_id: str,
        deprecation_str: str = "",
    ) -> None:
        """Render a single badge unifying errors and advisory warnings.

        One icon and one count, coloured by highest severity: red for any
        runtime error, amber for advisory-only. Left-click opens the popup;
        right-click falls through to the selection context menu via
        ``data-node-id``.

        Args:
            errors: Runtime errors (fatal — make the node invalid).
            warnings: Advisory NodeWarning records (non-fatal).
            node_id: Node ID used by canvas.vue to resolve the active node.
            deprecation_str: Optional deprecation notice from node identity.
        """
        has_errors = bool(errors)
        # One count covering every diagnostic surfaced in the popup.
        total = len(errors) + len(warnings) + (1 if deprecation_str else 0)

        # Highest severity drives the color: red if any fatal error, else amber.
        color = "red" if has_errors else "amber"

        btn = ui.button(icon=hui.icon.warning, color=color).props("flat dense round")
        btn.classes("text-xl px-2 py-1")
        # Pinned right: drawn after the card body, it has no flow position to fall back on.
        btn.style("position: absolute; top: -25px; right: 0;")
        btn.props(f'data-node-id="{node_id}"')
        # The menu only reads, so it opens in every level mode.
        stamp_requires(btn, LevelMode.VIEW)
        with btn:
            hui.count_badge(total, tone="danger" if has_errors else "warning", floating=True)

            # ui.menu renders on Layer 2 (--hw-bg-elevated) per the design system.
            # Body copy stays quiet (body/dim tokens) — severity lives on the badge
            # icon, not the prose. Messages wrap, so override `truncate`.
            with ui.menu(), ui.column().classes("p-2 gap-1").style("max-width: 22rem"):
                if errors:
                    hui.section_label("Errors")
                    for e in errors:
                        ui.label(e.message).classes("text-sm hw-text-body whitespace-normal")
                if deprecation_str:
                    hui.section_label("Deprecated")
                    ui.label(deprecation_str).classes("text-sm hw-text-body whitespace-normal")
                compatibility = [w for w in warnings if w.kind == "compatibility"]
                if compatibility:
                    hui.section_label("Compatibility warnings")
                    for w in compatibility:
                        ui.label(w.message).classes("text-sm hw-text-body whitespace-normal")
                    ui.label(
                        "Tip: 'Reset Node' re-derives this node from current code "
                        "(note: this discards any dynamically-added ports)."
                    ).classes("text-xs hw-text-dim whitespace-normal")
                previous_setup = [w for w in warnings if w.kind == "previous_setup"]
                if previous_setup:
                    hui.section_label("Settings reset by a code change")
                    for w in previous_setup:
                        ui.label(w.message).classes("text-sm hw-text-body whitespace-normal")
                    ui.label("Right-click the node to restore or discard them.").classes(
                        "text-xs hw-text-dim whitespace-normal"
                    )
                others = [w for w in warnings if w.kind not in ("compatibility", "previous_setup")]
                if others:
                    hui.section_label("Warnings")
                    for w in others:
                        ui.label(w.message).classes("text-sm hw-text-body whitespace-normal")

    @abstractmethod
    def render(self, main_card: ui.card, wrapper: NodeWrapper, *, on_stage: bool) -> UINodeCard:
        """
        Render a node into the main_card.

        Usage:
        ```
        # Set up main card appearance
        main_card.classes().style()

        with main_card:
            # Add UI elements here
        ```
        Args:
            main_card: The NiceGUI ui.card() element to render the node into
            wrapper: The NodeWrapper containing the HaywireNode to render
            on_stage: True when drawing for a stage view. A stage canvas draws the node's
                stage skin (``props.stage_skin``); a skin that suits both views draws its
                stage card here, e.g. expanded and with only the on-stage pins.

        """
        pass

    def on_card_cleanup(self, node_id: str, callback: Callable[[], None]) -> None:
        """Run *callback* when the card being drawn for *node_id* is cleaned up.

        Call it from :meth:`render` for anything the skin builds that outlives the
        draw call and must be released when the card is redrawn or torn down, as
        widgets are. Each callback runs once, after the card's widgets. If the
        render fails, the callback runs at once.

        Example::

            def render(self, main_card, wrapper, *, on_stage):
                view = build_view(...)
                self.on_card_cleanup(wrapper.node_id, view.cleanup)
        """
        self._nodeids_cleanups.setdefault(node_id, []).append(callback)

    def honours_detail(self, *, on_stage: bool) -> bool:
        """Return whether the node's Detail setting thins this skin's cards in this view.

        ``False`` draws the card at full detail whatever the setting. Override to opt out
        in a view; the default honours it in both.
        """
        return True

    def render_widget(self, port: DataPort, node_id: str, classes: str = "") -> ui.element | None:
        """
        Render a widget for the given inlet and node ID.

        Args:
            port: The data port inlet to render the widget for
            node_id: The unique identifier of the node
            classes: Additional CSS classes to apply to the widget ui_element container
        Returns:
            The rendered widget ui_element container, or None if no widget was rendered.
        """
        if port.widget_key is None:
            return None  # Port has no widget configured

        widget_instance, ui_element = self._widget_factory.render_widget(
            registry_key=port.widget_key,
            port=port,
            node_id=node_id,
            route=self._nodeids_routes.get(node_id),
            minimum=LevelMode.OPERATE,
        )

        # Apply styling to the UI element if possible
        if ui_element and hasattr(ui_element, "classes") and callable(ui_element.classes):
            ui_element.classes(classes)

        # Carry the widget's declared size box (@widget(min_width=, min_height=))
        # onto the same element. Every skin funnels through here, so a custom
        # skin gets the behaviour without cooperating.
        if widget_instance is not None:
            stamp_size_declaration(ui_element, widget_instance)

        if widget_instance:
            self._nodeids_widget_instances.setdefault(node_id, {})[port.id] = widget_instance

        return ui_element

    def render_setting_widget(
        self,
        bag: Settings,
        name: str,
        node_id: str,
        *,
        widget_key: str | None = None,
        classes: str = "",
    ) -> ui.element | None:
        """Render the widget of settings field *name* of *bag* on the card of node *node_id*.

        The widget writes through the card's route at level mode ``OPERATE``, or ``EDIT``
        for a field that is not operable; with no route it is read-only.

        Args:
            widget_key: The registry key of the widget to draw; ``None`` draws the field's own.
            classes: Additional CSS classes for the widget's container.

        Returns:
            The rendered widget container, or ``None`` if the field has no widget.

        Raises:
            KeyError: If *bag* has no field *name*.

        Example::

            # The note's text, drawn by a widget of the skin's choosing.
            self.render_setting_widget(node.annotation, "text", wrapper.node_id, widget_key=NOTE_TEXT_WIDGET)
        """
        from haywire.ui.widget.factory import setting_widget_model

        descriptor = type(bag)._settings_descriptors()[name]
        key = widget_key or descriptor.widget_key
        if not key:
            return None
        model = setting_widget_model(bag, name, self._nodeids_routes.get(node_id), LevelMode.OPERATE)
        widget_instance, ui_element = self._widget_factory.render_widget(key, model, node_id)

        if ui_element is not None and hasattr(ui_element, "classes") and callable(ui_element.classes):
            ui_element.classes(classes)
        if widget_instance is not None:
            stamp_size_declaration(ui_element, widget_instance)
            self._nodeids_widget_instances.setdefault(node_id, {})[descriptor.storage_key] = widget_instance

        return ui_element

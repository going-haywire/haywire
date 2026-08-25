from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar
import logging

import nicegui.ui as ui

from haywire.core.library.identity import LibraryIdentity
from haywire.core.types import DataPort
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.registry.identity import BaseIdentity

from ..widget.interface import IWidget
from ..widget.factory_interface import IWidgetFactory
from ..widget.sizing import stamp_size_declaration
from .nodecard import UINodeCard

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
    """

    class_identity: ClassVar[SkinIdentity]
    class_library: ClassVar[LibraryIdentity]

    def __init__(self, widget_factory: IWidgetFactory):
        """
        Initialize the skin with a widget factory.

        Args:
            widget_factory: Factory for creating widget instances
        """
        self._widget_factory: IWidgetFactory = widget_factory
        self._nodeids_widget_instances: dict[str, dict[str, IWidget]] = {}

    def _render(self, wrapper: NodeWrapper) -> UINodeCard:
        ui_nodeCard: UINodeCard = UINodeCard()
        try:
            # Initialize node_id storage for widget instances
            self._nodeids_widget_instances[wrapper.node_id] = {}

            self.render(ui_nodeCard.get_card(), wrapper)

            ui_nodeCard.set_widget_instances(self._nodeids_widget_instances[wrapper.node_id])

            # Clear widget instances for next render
            self._nodeids_widget_instances[wrapper.node_id] = {}

            return ui_nodeCard

        except Exception:
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

    @abstractmethod
    def render(self, main_card: ui.card, wrapper: NodeWrapper) -> UINodeCard:
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

        """
        pass

    def card_style(
        self,
        wrapper: NodeWrapper,
        *,
        background: str,
        border_color: str,
        border_thickness: int,
        border_roundness: int,
    ) -> str:
        """The card's colour/border CSS, with the node's own props layered on top.

        A skin passes its *own* look as the keyword defaults and gets back a
        style string in which any per-node override from the ``appearance``
        props (``body_color``, ``border_color``, ``border_thickness``,
        ``border_roundness``) has replaced the corresponding default. A node
        that overrides nothing renders exactly as the skin declared, so calling
        this is behaviour-preserving.

        ``background`` is the only default passed through untouched when unset,
        which is what lets a skin hand in a gradient (``linear-gradient(...)``)
        rather than a flat colour — an override replaces it wholesale.

        "Overridden" means *locally set*, not "differs from the default". The
        props carry concrete defaults (they have to survive the widget layer —
        see NodeProperties), so their value alone cannot distinguish a node that
        was styled from one that never was. ``is_locally_set`` is the framework's
        own set-or-unset opinion and the same one ``to_dict`` serializes on, so
        resetting a field in the panel returns the card to the skin's look.

        Thickness and roundness are clamped here because ``min``/``max`` in a
        widget_config are UI-only and unenforced on write: a hand-edited graph
        JSON can carry any int, and a negative border silently breaks the pin
        geometry that positions against the card edge.
        """
        props = getattr(wrapper.node, "props", None)
        is_set = getattr(props, "is_locally_set", None)

        def _override(name: str):
            if props is None:
                return None
            # A bag without the set-or-unset API (a stub, a custom props object)
            # falls back to reading the value directly.
            if callable(is_set) and not is_set(name):
                return None
            value = getattr(props, name, None)
            # An empty colour field is not an override either.
            return None if value is None or value == "" else value

        body = _override("body_color") or background
        color = _override("border_color") or border_color

        def _px(name: str, default: int, ceiling: int) -> int:
            raw = _override(name)
            if raw is None:
                return default
            try:
                return max(0, min(int(raw), ceiling))
            except (TypeError, ValueError):
                # Garbage in a hand-edited graph must not take the card's whole
                # render down — fall back to the skin's own value.
                logger.warning("Ignoring non-numeric props.%s: %r", name, raw)
                return default

        thickness = _px("border_thickness", border_thickness, 32)
        roundness = _px("border_roundness", border_roundness, 64)

        return f"background: {body}; border: {thickness}px solid {color}; border-radius: {roundness}px; "

    def render_widget(self, port: DataPort, node_id: str, classes: str = "") -> ui.element | None:
        """
        Render a widget for the given inlet and node ID.

        Args:
            port: The data port inlet to render the widget for
            node_id: The unique identifier of the node
            classes: Additional CSS classes to apply to the widget ui_element container
        Returns:
            The rendered widget ui_element container, or None if no widget was rendered
        """
        if port.widget_key is None:
            return None  # Port has no widget configured

        widget_instance, ui_element = self._widget_factory.render_widget(
            registry_key=port.widget_key, port=port, node_id=node_id
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

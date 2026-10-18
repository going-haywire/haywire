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

from ..widget.interface import IWidget
from ..widget.factory_interface import IWidgetFactory
from ..widget.sizing import stamp_size_declaration
from .nodecard import UINodeCard
from .pin_icons import DEFAULT_PIN_ICONS, PinIconResolver

if TYPE_CHECKING:
    from haywire.core.graph.edit_route import EditRoute
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

    def _render(
        self, wrapper: NodeWrapper, *, on_stage: bool = False, route: EditRoute | None = None
    ) -> UINodeCard:
        """Draw *wrapper*'s card: :meth:`render` into a fresh card.

        ``on_stage`` is forwarded to :meth:`render`. Every widget :meth:`render_widget`
        draws for this card writes through *route*, at level mode ``OPERATE``;
        ``None`` refuses every write.
        """
        self._nodeids_routes[wrapper.node_id] = route
        try:
            return self._render_into_card(
                wrapper, lambda card: self.render(card, wrapper, on_stage=on_stage)
            )
        finally:
            self._nodeids_routes.pop(wrapper.node_id, None)

    def _render_into_card(self, wrapper: NodeWrapper, draw: Callable[[ui.card], object]) -> UINodeCard:
        ui_nodeCard: UINodeCard = UINodeCard()
        try:
            # Initialize node_id storage for widget instances
            self._nodeids_widget_instances[wrapper.node_id] = {}

            draw(ui_nodeCard.get_card())

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
            The rendered widget ui_element container, or None if no widget was rendered. An
            operable port's container is marked ``data-hw-operable``, so it takes pointer input
            on a canvas in level mode ``OPERATE``.
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
        if ui_element is not None and getattr(port, "operable", True):
            ui_element.props("data-hw-operable")

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
            The rendered widget container, or ``None`` if the field has no widget. An
            operable field's container is marked ``data-hw-operable``.

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
        if ui_element is not None and descriptor.operable:
            ui_element.props("data-hw-operable")
        if widget_instance is not None:
            stamp_size_declaration(ui_element, widget_instance)
            self._nodeids_widget_instances.setdefault(node_id, {})[descriptor.storage_key] = widget_instance

        return ui_element

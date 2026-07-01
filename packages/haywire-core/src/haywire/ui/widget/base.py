from abc import ABC, abstractmethod
import logging
from typing import Any, Optional

from haywire.core.types import WidgetModel
from haywire.ui.widget.binding import PropertyBinding
from haywire.ui.widget.converters import BindingConverter, BindingMode, PrimitiveUnwrappingConverter
from haywire.ui.widget.interface import IWidget


class BaseWidget(IWidget, ABC):
    """The single canonical widget base.

    Floor (always available, serves any BaseType):
      - ``build()``            : construct & return the NiceGUI root element.
      - ``on_model_changed(v)``: override for arbitrary model→view sync. Fires on
                                 every port change and once at render. Default
                                 refreshes any ``bind()``-registered bindings.

    Sugar (flat-scalar convenience):
      - ``bind(element, to=...)``: register a two-way (or one-way) binding from a
                                   model field to a NiceGUI element property.
    """

    def __init__(self, port: WidgetModel):
        self.port = port
        self.port_id: str = port.id
        widget_config = port.widget_config if hasattr(port, "widget_config") and port.widget_config else {}
        self._config: dict[str, Any] = widget_config

        self.ui_element: Optional[Any] = None
        self._bindings: list[PropertyBinding] = []
        self._model_dispatch_cb: Optional[Any] = None
        self._cleaned_up: bool = False
        self.logger = logging.getLogger(__name__)

    # ---- FLOOR ----------------------------------------------------------
    @abstractmethod
    def build(self) -> Any:
        """Construct and return the NiceGUI root element for this widget."""
        ...

    def get_value(self) -> Any:
        return self.port.get_value()

    def set_value(self, value: Any) -> None:
        self.port.set_value(value)

    def on_model_changed(self, value: Any) -> None:
        """Override for custom model→view sync. Default drives bind()-ings.

        Subclasses that override should call ``super().on_model_changed(value)``
        to keep their bind()-registered elements live, or omit the super() call
        to take full ownership of sync.
        """
        for binding in self._bindings:
            binding.sync_to_view()

    # ---- SUGAR ----------------------------------------------------------
    def bind(
        self,
        element: Any,
        *,
        to: str = "value",
        prop: str = "value",
        event: str = "update:modelValue",
        converter: Optional[BindingConverter] = None,
        one_way: bool = False,
    ) -> Any:
        """Register a binding from model field ``to`` to ``element.prop``.

        ``to="value"`` (default) binds the whole port value (primitive case).
        ``to="x"`` / ``to="position.x"`` navigates a BaseType field path.
        Returns ``element`` so it composes inside ``with ui.row():`` blocks.
        """
        binding = PropertyBinding(
            source_property=to,
            target_property=prop,
            target_event=event,
            converter=converter or PrimitiveUnwrappingConverter(),
            mode=BindingMode.ONE_WAY if one_way else BindingMode.TWO_WAY,
        )
        binding._pending_element = element  # activated once, in render()
        self._bindings.append(binding)
        return element

    # ---- RENDER + LIFECYCLE (final) -------------------------------------
    def render(self) -> Any:
        """Build the element, activate bindings exactly once, wire dispatch."""
        if self._cleaned_up:
            raise RuntimeError("Cannot render a widget after cleanup()")
        if self.ui_element is None:
            self.ui_element = self.build()

            # Activate each bind()-ed binding once, against its pending element.
            # The widget owns model→view (via _model_dispatch_cb below); each
            # binding owns only view→model, so suppress its self-subscription.
            for binding in self._bindings:
                binding.activate(self.port, binding._pending_element, subscribe_model_to_view=False)
                binding._pending_element = None  # drop the round-trip element reference

            # Single model→view dispatch channel → on_model_changed.
            self._model_dispatch_cb = lambda _: self.on_model_changed(self.port.get_value())
            self.port.data.on_changed += self._model_dispatch_cb

            # Initial sync.
            self.on_model_changed(self.port.get_value())

            if hasattr(self.ui_element, "client"):
                self.ui_element.client.on_disconnect(self.cleanup)

        return self.ui_element

    def cleanup(self) -> None:
        """Final teardown. Drops the dispatch subscription, deactivates bindings,
        then calls the subclass hook ``_on_cleanup()``. Idempotent."""
        if self._cleaned_up:
            return
        if self._model_dispatch_cb is not None and self.port is not None:
            try:
                self.port.data.on_changed -= self._model_dispatch_cb
            except Exception as e:
                self.logger.warning(f"Failed to drop model dispatch: {e}", exc_info=True)
        self._model_dispatch_cb = None

        for binding in self._bindings:
            binding.deactivate()
        self._bindings.clear()

        self._on_cleanup()

        self.ui_element = None
        self._cleaned_up = True

    def _on_cleanup(self) -> None:
        """Override to release subclass-owned resources (e.g. a backend).
        Called by the final ``cleanup()``; do NOT override ``cleanup()`` itself."""
        ...

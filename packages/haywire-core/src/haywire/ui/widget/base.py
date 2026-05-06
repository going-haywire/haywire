from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from haywire.core.types import DataPort
from haywire.ui.widget.binding import PropertyBinding
from haywire.ui.widget.converters import BindingConverter, BindingMode, PrimitiveUnwrappingConverter
from haywire.ui.widget.interface import IWidget

# ============================================================================
#    BASE WIDGET CLASS
# ============================================================================


class BaseWidget(IWidget, ABC):
    """
    Base class for sophisticated widgets with declarative binding support.

    Features:
    - Multiple bindings per widget
    - Custom converters and validators
    - Multiple UI elements with targeted bindings
    - Debouncing, validation, error handling

    Widgets override configure_bindings() to setup data flow declaratively,
    eliminating boilerplate for common patterns.
    """

    def __init__(self, port: DataPort):
        """
        Initialize widget.

        Args:
            port: DataPort containing the data to bind to
        """
        self.port = port
        self.port_id: str = port.id
        widget_config = port.widget_config if hasattr(port, "widget_config") and port.widget_config else {}
        self._config: Dict[str, Any] = widget_config

        # UI element (created during render)
        self.ui_element: Optional[Any] = None

        # Binding management
        self._bindings: Dict[str, List[PropertyBinding]] = {}

        # Sub-element references (for complex widgets)
        self._ui_element_refs: Dict[str, Any] = {}

        # Cleanup flag — signals cleanup() has run; callers must not access
        # the widget's fields after that. Mirrors Settings._cleaned_up.
        self._cleaned_up: bool = False

    @abstractmethod
    def configure_bindings(self) -> None:
        """
        Configure bindings for this widget.

        Override this method to setup declarative bindings.
        Called after create_element(), before render completes.

        Example:
            def configure_bindings(self):
                # Simple binding with default converter
                self.add_binding(self.create_default_binding())

                # Custom binding with formatting
                self.add_binding(PropertyBinding(
                    source_property="value",
                    converter=FormattingConverter("{:.2f}"),
                    mode=BindingMode.ONE_WAY
                ))
        """
        pass

    @abstractmethod
    def create_element(self) -> Any:
        """
        Create and return the NiceGUI element for this widget.

        For complex widgets with multiple sub-elements, store references:

        Example:
            def create_element(self):
                with ui.card() as card:
                    self.label = ui.label()
                    self.button = ui.button()

                # Store refs for targeted bindings
                self._ui_element_refs['label'] = self.label
                self._ui_element_refs['button'] = self.button

                return card
        """
        pass

    def add_binding(self, binding: PropertyBinding, target_element: Optional[str] = None) -> None:
        """
        Add a binding to this widget.

        Args:
            binding: Binding configuration
            target_element: Optional name of sub-element (for complex widgets)
                          If None, binds to the main ui_element
        """
        target_key = target_element or "__main__"

        if target_key not in self._bindings:
            self._bindings[target_key] = []

        self._bindings[target_key].append(binding)

        # Activate immediately if target element exists
        if target_element and target_element in self._ui_element_refs:
            binding.activate(self.port, self._ui_element_refs[target_element])
        elif not target_element and self.ui_element is not None:
            binding.activate(self.port, self.ui_element)

    def create_default_binding(
        self,
        source_property: str = "value",
        target_property: str = "value",
        target_event: str = "update:modelValue",
        converter: Optional[BindingConverter] = None,
        mode: BindingMode = BindingMode.TWO_WAY,
        **kwargs,
    ) -> PropertyBinding:
        """
        Create standard binding for this widget's data port.

        This is a convenience method that most simple widgets can use.

        Args:
            source_property: Property path in container (default: "value")
            target_property: Property name to bind (default: "value")
            target_event: Event name to listen for (default: "update:modelValue")
            converter: Optional custom converter (default: PrimitiveUnwrappingConverter)
            mode: Binding mode (default: TWO_WAY)
            **kwargs: Additional PropertyBinding arguments

        Returns:
            Configured PropertyBinding
        """
        return PropertyBinding(
            source_property=source_property,
            target_property=target_property,
            target_event=target_event,
            converter=converter or PrimitiveUnwrappingConverter(),
            mode=mode,
            **kwargs,
        )

    def render(self) -> Any:
        """
        Render widget with automatic binding setup.

        Returns:
            The rendered UI element
        """
        if self.ui_element is None:
            # Create UI element
            self.ui_element = self.create_element()

            # Let subclass configure bindings
            self.configure_bindings()

            # Activate all bindings
            self._activate_all_bindings()

            # Cleanup on disconnect
            if hasattr(self.ui_element, "client"):
                self.ui_element.client.on_disconnect(lambda: self.cleanup())

        return self.ui_element

    def _activate_all_bindings(self) -> None:
        """Activate all configured bindings"""
        # Activate main bindings
        if "__main__" in self._bindings:
            for binding in self._bindings["__main__"]:
                binding.activate(self.port, self.ui_element)

        # Activate sub-element bindings
        for element_name, bindings in self._bindings.items():
            if element_name != "__main__" and element_name in self._ui_element_refs:
                target_element = self._ui_element_refs[element_name]
                for binding in bindings:
                    binding.activate(self.port, target_element)

    def cleanup(self) -> None:
        """Clean up bindings and resources.

        Callers must not access the widget's fields after cleanup() returns —
        the contract is signalled by ``self._cleaned_up = True``.
        """
        if self._cleaned_up:
            return
        print(f"Cleaning up widget: {self.class_identity.registry_key} for element ID: {self.port_id}")

        # Deactivate all bindings
        for bindings_list in self._bindings.values():
            for binding in bindings_list:
                binding.deactivate()

        self._bindings.clear()
        self._ui_element_refs.clear()

        self.ui_element = None
        self._cleaned_up = True

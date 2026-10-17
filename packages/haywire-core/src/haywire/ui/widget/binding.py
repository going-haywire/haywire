"""
PropertyBinding - Updated with property update logic

This module provides the PropertyBinding class that handles declarative
bindings between DataPort properties and UI element properties.

With the new DataField system, property-level updates are handled by
PropertyBinding rather than DataField, creating a cleaner separation
between data storage and binding logic.
"""

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, List, Optional

from haywire.core.types import PrimitiveField, BaseField, WidgetModel
from haywire.ui.widget.converters import (
    BindingConverter,
    BindingMode,
    PrimitiveUnwrappingConverter,
)

if TYPE_CHECKING:
    from haywire.ui.widget.base import BaseWidget


@dataclass
class PropertyBinding:
    """
    Declarative binding between DataPort property and UI element property.

    With the new architecture:
    - DataField handles data storage (primitives, instances, containers)
    - PropertyBinding handles widget updates (property navigation, updates)

    This creates clean separation between data and UI concerns.
    """

    # Source (path within data)
    source_property: str = "value"

    # Target (UI element)
    target_property: str = "value"
    target_event: str = "update:modelValue"

    # Transformation
    converter: Optional[BindingConverter] = None

    # Behavior
    mode: BindingMode = BindingMode.TWO_WAY

    # The widget whose ``accepts_write()`` decides a view edit; None decides by the field alone.
    owner: Optional["BaseWidget"] = field(default=None, repr=False, compare=False)

    # Internal state
    _element: Optional[WidgetModel] = field(default=None, init=False, repr=False)
    _ui_element: Optional[Any] = field(default=None, init=False, repr=False)
    _is_active: bool = field(default=False, init=False, repr=False)
    _cleanup_callbacks: List[Callable] = field(default_factory=list, init=False, repr=False)
    _pending_element: Optional[Any] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize with default converter if none provided"""
        if self.converter is None:
            self.converter = PrimitiveUnwrappingConverter()

    def activate(self, element: WidgetModel, ui_element: Any, subscribe_model_to_view: bool = True) -> None:
        """
        Activate binding between DataPort and UI element.

        Args:
            element: DataPort to bind
            ui_element: NiceGUI element to bind
            subscribe_model_to_view: when ``False``, skip the binding's own
                model→view subscription + initial sync. The owning widget then
                drives model→view through its single dispatch channel and this
                binding owns only view→model.
        """
        if self._is_active:
            return

        self._element = element
        self._ui_element = ui_element

        # Setup Model → View binding
        if subscribe_model_to_view:
            self._setup_model_to_view()

        # Setup View → Model binding (if two-way)
        if self.mode == BindingMode.TWO_WAY:
            self._setup_view_to_model()

        self._is_active = True

    # ========================================================================
    # MODEL → VIEW (Reading from DataField)
    # ========================================================================

    def _setup_model_to_view(self) -> None:
        """Setup Model → View data flow"""
        if self.mode == BindingMode.ONE_TIME:
            self.sync_to_view()
            return

        def on_model_changed(_):
            self.sync_to_view()

        assert self._element is not None and self._element.data is not None
        element_data = self._element.data
        element_data.on_changed += on_model_changed
        self._cleanup_callbacks.append(lambda: element_data.on_changed.remove(on_model_changed))

        # Initial sync
        on_model_changed(None)

    def sync_to_view(self) -> None:
        """Synchronize model value to view."""
        assert self._element is not None and self.converter is not None
        if self.source_property == "value":
            model_value = self._element.get_value()
        else:
            field = self._element.data
            if isinstance(field, BaseField):
                container = field.get_value()
                model_value = self._navigate_path(container, self.source_property)
            elif isinstance(field, PrimitiveField):
                raise ValueError(
                    f"PrimitiveField only supports source_property='value', got '{self.source_property}'"
                )
            else:
                raise ValueError(f"Property navigation not supported for {type(field).__name__}")

        view_value = self.converter.to_view(model_value)
        setattr(self._ui_element, self.target_property, view_value)

    # ========================================================================
    # VIEW → MODEL (Writing to DataField)
    # ========================================================================

    def _setup_view_to_model(self) -> None:
        """Setup View → Model data flow (immediate update on the target event)."""
        handler = self._create_immediate_handler()
        assert self._ui_element is not None
        ui_element = self._ui_element
        ui_element.on(self.target_event, handler)
        self._cleanup_callbacks.append(
            lambda: self._safe_remove_handler(ui_element, self.target_event, handler)
        )

    def _create_immediate_handler(self) -> Callable:
        """Create immediate update handler"""

        def handler(e):
            view_value = getattr(e.sender, self.target_property)
            self._sync_to_model(view_value)

        return handler

    def _sync_to_model(self, view_value: Any) -> None:
        """Write a view edit to the model, or show the model again when the write is refused.

        With an ``owner``, its ``accepts_write()`` decides. Without one, the write
        is refused while an edge's value stands in front of the own value or the
        field holds no own value. A model whose ``set_value`` returns ``False``
        (a routed model whose edit route refused) refuses the write too.

        A nested ``source_property`` (``"x"``, ``"transform.scale"``) writes a
        copy of the model's value with that path changed; the value the model
        holds is never changed in place.
        """
        assert self._element is not None and self.converter is not None
        if not self._accepts_write():
            self.sync_to_view()
            return
        is_valid, _error_msg = self.converter.validate(view_value)
        if not is_valid:
            return

        model_value = self.converter.to_model(view_value)

        before = self._element.get_value()
        if self.source_property == "value":
            new_value = model_value
        elif self._navigate_path(before, self.source_property) == model_value:
            return
        else:
            new_value = self._with_nested_property(before, self.source_property, model_value)
        if self._element.set_value(new_value) is False:
            self.sync_to_view()

    def _accepts_write(self) -> bool:
        if self.owner is not None:
            return self.owner.accepts_write()
        assert self._element is not None
        data = self._element.data
        return not data.has_linked_value() and data.accepts_own_value()

    # ========================================================================
    # PROPERTY UPDATE LOGIC (Moved from DataField)
    # ========================================================================

    def _navigate_path(self, obj: Any, path: str) -> Any:
        """
        Navigate property path and return value.

        Args:
            obj: Object to navigate (BaseType instance)
            path: Property path (e.g., 'transform.scale.x')

        Returns:
            Value at the end of the path
        """
        parts = path.split(".")
        current = obj
        for part in parts:
            current = getattr(current, part)
        return current

    def _with_nested_property(self, container: Any, path: str, value: Any) -> Any:
        """Return a deep copy of *container* with the property at *path* set to *value*.

        Raises:
            ValueError: If the model's field is not a ``BaseField``.
        """
        assert self._element is not None
        field = self._element.data
        if not isinstance(field, BaseField):
            raise ValueError(
                f"Property updates only supported for BaseField, got {type(field).__name__}. "
                f"Use source_property='value' for other field types."
            )

        *parents, final_property = path.split(".")
        updated = copy.deepcopy(container)
        current = updated
        for part in parents:
            current = getattr(current, part)
        setattr(current, final_property, value)
        return updated

    # ========================================================================
    # CLEANUP
    # ========================================================================

    def _safe_remove_handler(self, ui_element: Any, event: str, handler: Callable) -> None:
        """Safely remove event handler"""
        try:
            if hasattr(ui_element, "off"):
                ui_element.off(event, handler)
        except Exception:
            pass

    def deactivate(self) -> None:
        """Deactivate binding and cleanup resources"""
        if not self._is_active:
            return

        for cleanup in self._cleanup_callbacks:
            try:
                cleanup()
            except Exception:
                pass

        self._cleanup_callbacks.clear()
        self._is_active = False

"""
PropertyBinding - Updated with property update logic

This module provides the PropertyBinding class that handles declarative
bindings between DataPort properties and UI element properties.

With the new DataField system, property-level updates are handled by
PropertyBinding rather than DataField, creating a cleaner separation
between data storage and binding logic.
"""

from dataclasses import dataclass, field
import threading
from typing import Any, Callable, List, Optional

from haywire.core.types.ports import DataPort
from haywire.core.data.fields import PrimitiveField, BaseField
from haywire.ui.widget.converters import (
    BindingConverter,
    BindingMode,
    PrimitiveUnwrappingConverter,
    UpdateTrigger
)

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
    update_trigger: UpdateTrigger = UpdateTrigger.IMMEDIATE
    
    # Advanced options
    update_delay: float = 0.0
    validation: Optional[Callable[[Any], tuple[bool, Optional[str]]]] = None
    on_error: Optional[Callable[[str], None]] = None
    
    # Internal state
    _element: Optional[DataPort] = field(default=None, init=False, repr=False)
    _ui_element: Optional[Any] = field(default=None, init=False, repr=False)
    _is_active: bool = field(default=False, init=False, repr=False)
    _cleanup_callbacks: List[Callable] = field(default_factory=list, init=False, repr=False)
    _debounce_timer: Optional[threading.Timer] = field(default=None, init=False, repr=False)
    
    def __post_init__(self):
        """Initialize with default converter if none provided"""
        if self.converter is None:
            self.converter = PrimitiveUnwrappingConverter()
    
    def activate(self, element: DataPort, ui_element: Any) -> None:
        """
        Activate binding between DataPort and UI element.
        
        Args:
            element: DataPort to bind
            ui_element: NiceGUI element to bind
        """
        if self._is_active:
            return
        
        self._element = element
        self._ui_element = ui_element
        
        # Setup Model → View binding
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
            self._sync_to_view()
            return
        
        def on_model_changed(_):
            self._sync_to_view()
        
        self._element.data.on_changed += on_model_changed
        self._cleanup_callbacks.append(
            lambda: self._element.data.on_changed.remove(on_model_changed)
        )
        
        # Initial sync
        on_model_changed(None)
    
    def _sync_to_view(self) -> None:
        """Synchronize model value to view"""
        try:
            # For primitives and simple cases, use get_value()
            if self.source_property == "value":
                model_value = self._element.get_value()
            else:
                # For complex properties, navigate the path
                # This only works for BaseField (not Primitive/Pooled/Array)
                field = self._element.data
                if isinstance(field, BaseField):
                    container = field._container
                    model_value = self._navigate_path(container, self.source_property)
                elif isinstance(field, PrimitiveField):
                    # PrimitiveField only supports 'value' property
                    raise ValueError(
                        f"PrimitiveField only supports source_property='value', got '{self.source_property}'"
                    )
                else:
                    raise ValueError(
                        f"Property navigation not supported for {type(field).__name__}"
                    )
            
            # Convert and update UI
            view_value = self.converter.to_view(model_value)
            setattr(self._ui_element, self.target_property, view_value)
            
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
    
    # ========================================================================
    # VIEW → MODEL (Writing to DataField)
    # ========================================================================
    
    def _setup_view_to_model(self) -> None:
        """Setup View → Model data flow"""
        if self.update_trigger == UpdateTrigger.IMMEDIATE:
            handler = self._create_immediate_handler()
        elif self.update_trigger == UpdateTrigger.DEBOUNCED:
            handler = self._create_debounced_handler()
        elif self.update_trigger == UpdateTrigger.ON_BLUR:
            handler = self._create_immediate_handler()
            self.target_event = "blur"
        elif self.update_trigger == UpdateTrigger.ON_ENTER:
            handler = self._create_immediate_handler()
            self.target_event = "keydown.enter"
        else:
            handler = self._create_immediate_handler()
        
        self._ui_element.on(self.target_event, handler)
        self._cleanup_callbacks.append(
            lambda: self._safe_remove_handler(self._ui_element, self.target_event, handler)
        )
    
    def _create_immediate_handler(self) -> Callable:
        """Create immediate update handler"""
        def handler(e):
            view_value = getattr(e.sender, self.target_property)
            self._sync_to_model(view_value)
        return handler
    
    def _create_debounced_handler(self) -> Callable:
        """Create debounced update handler"""
        def handler(e):
            view_value = getattr(e.sender, self.target_property)
            
            if self._debounce_timer:
                self._debounce_timer.cancel()
            
            self._debounce_timer = threading.Timer(
                self.update_delay,
                lambda: self._sync_to_model(view_value)
            )
            self._debounce_timer.start()
        
        return handler
    
    def _sync_to_model(self, view_value: Any) -> None:
        """Synchronize view value to model"""
        try:
            # Validate
            if self.validation:
                is_valid, error_msg = self.validation(view_value)
                if not is_valid:
                    if self.on_error:
                        self.on_error(error_msg)
                    return
            
            is_valid, error_msg = self.converter.validate(view_value)
            if not is_valid:
                if self.on_error:
                    self.on_error(error_msg)
                return
            
            # Convert
            model_value = self.converter.to_model(view_value)
            
            # Update model
            if self.source_property == "value":
                # Simple case - replace entire value
                self._element.set_value(model_value)
            else:
                # Complex case - update nested property
                self._update_nested_property(self.source_property, model_value)
            
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
    
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
        parts = path.split('.')
        current = obj
        for part in parts:
            current = getattr(current, part)
        return current
    
    def _update_nested_property(self, path: str, value: Any) -> None:
        """
        Update nested property and notify observers.
        
        This is the property update logic that was previously in DataField.
        Now it lives in PropertyBinding for better separation of concerns.
        
        Args:
            path: Property path (e.g., 'radius', 'transform.scale')
            value: New value for the property
        
        Raises:
            ValueError: If field type doesn't support property updates
        """
        field = self._element.data
        
        # Only works for BaseField
        if not isinstance(field, BaseField):
            raise ValueError(
                f"Property updates only supported for BaseField, got {type(field).__name__}. "
                f"Use source_property='value' for other field types."
            )
        
        # Get container (the BaseType instance)
        container = field._container
        
        # Navigate to parent of final property
        parts = path.split('.')
        current = container
        for part in parts[:-1]:
            current = getattr(current, part)
        
        # Update final property
        final_property = parts[-1]
        old_value = getattr(current, final_property, None)
        
        if old_value == value:
            return  # No change
        
        setattr(current, final_property, value)
        
        # Mark dirty and fire observers
        field.is_dirty = True
        field.fire(container)
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    def _safe_remove_handler(self, ui_element: Any, event: str, handler: Callable) -> None:
        """Safely remove event handler"""
        try:
            if hasattr(ui_element, 'off'):
                ui_element.off(event, handler)
        except Exception:
            pass
    
    def deactivate(self) -> None:
        """Deactivate binding and cleanup resources"""
        if not self._is_active:
            return
        
        if self._debounce_timer:
            self._debounce_timer.cancel()
            self._debounce_timer = None
        
        for cleanup in self._cleanup_callbacks:
            try:
                cleanup()
            except Exception:
                pass
        
        self._cleanup_callbacks.clear()
        self._is_active = False
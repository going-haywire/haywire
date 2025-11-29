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
from haywire.core.data.fields import PrimitiveField, ComplexField, PooledField, ArrayField
from haywire.ui.widget.converters import BindingConverter, BindingMode, PrimitiveUnwrappingConverter, UpdateTrigger


@dataclass
class PropertyBinding:
    """
    Declarative binding configuration between DataPort property and UI element property.
    
    Now handles property-level updates internally rather than delegating to DataField,
    creating better separation between data storage and binding logic.
    """
    # Source (path within container, default for primitives)
    source_property: str = "value"
    
    # Target (View side)
    target_property: str = "value"
    target_event: str = "update:modelValue"
    
    # Transformation
    converter: Optional[BindingConverter] = None
    
    # Behavior
    mode: BindingMode = BindingMode.TWO_WAY
    update_trigger: UpdateTrigger = UpdateTrigger.IMMEDIATE
    
    # Advanced options
    update_delay: float = 0.0           # Debounce delay in seconds
    validation: Optional[Callable[[Any], tuple[bool, Optional[str]]]] = None
    on_error: Optional[Callable[[str], None]] = None  # Error handler
    
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
            # One-time initialization only
            self._sync_to_view()
            return
        
        # Create update handler
        def on_model_changed(_):
            self._sync_to_view()
        
        # Subscribe to model changes
        self._element.data.on_changed += on_model_changed
        self._cleanup_callbacks.append(
            lambda: self._element.data.on_changed.remove(on_model_changed)
        )
        
        # Initial sync
        on_model_changed(None)
    
    def _sync_to_view(self) -> None:
        """Synchronize model value to view"""
        try:
            # Extract value using DataPort or property path
            if self.source_property == "value":
                # Fast path - use DataPort.get_value()
                model_value = self._element.get_value()
            else:
                # Navigate property path for complex types
                container = self._get_container()
                model_value = self._navigate_path(container, self.source_property)
            
            # Convert model → view
            view_value = self.converter.to_view(model_value)
            
            # Update UI element
            setattr(self._ui_element, self.target_property, view_value)
            
        except Exception as e:
            print(f"Error syncing to view: {e}")
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
        
        # Register event handler
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
            
            # Cancel existing timer
            if self._debounce_timer:
                self._debounce_timer.cancel()
            
            # Schedule update
            self._debounce_timer = threading.Timer(
                self.update_delay,
                lambda: self._sync_to_model(view_value)
            )
            self._debounce_timer.start()
        
        return handler
    
    def _sync_to_model(self, view_value: Any) -> None:
        """Synchronize view value to model"""
        try:
            # Validate if validator provided
            if self.validation:
                is_valid, error_msg = self.validation(view_value)
                if not is_valid:
                    if self.on_error:
                        self.on_error(error_msg)
                    return
            
            # Validate using converter
            is_valid, error_msg = self.converter.validate(view_value)
            if not is_valid:
                if self.on_error:
                    self.on_error(error_msg)
                return
            
            # Convert view → model
            model_value = self.converter.to_model(view_value)
            
            # Update model based on property path
            if self.source_property == "value":
                # Simple case - replace entire value
                self._element.set_value(model_value)
            else:
                # Complex case - update nested property
                self._update_nested_property(self.source_property, model_value)
            
        except Exception as e:
            print(f"Error syncing to model: {e}")
            if self.on_error:
                self.on_error(str(e))
    
    # ========================================================================
    # PROPERTY UPDATE LOGIC (Moved from DataField)
    # ========================================================================
    
    def _get_container(self) -> Any:
        """
        Get the container for property navigation.
        
        Returns:
            For PrimitiveField: The PrimitiveType wrapper instance
            For ComplexField: The BaseType instance
        
        Raises:
            ValueError: If field type doesn't support property binding
        """
        field = self._element.data
        
        if isinstance(field, PrimitiveField):
            return field._container  # The PrimitiveType wrapper
        elif isinstance(field, ComplexField):
            return field._container  # The BaseType instance
        elif isinstance(field, PooledField):
            raise ValueError(
                "Cannot bind to properties of PooledField. "
                "Pooled fields are read-only collections. "
                "Use mode=BindingMode.ONE_WAY for display only."
            )
        elif isinstance(field, ArrayField):
            raise ValueError(
                "Cannot bind to properties of ArrayField. "
                "Arrays must be replaced wholesale via set_value(). "
                "Consider using a custom widget for array editing."
            )
        else:
            raise TypeError(f"Unknown field type: {type(field).__name__}")
    
    def _navigate_path(self, obj: Any, path: str) -> Any:
        """
        Navigate property path and return value.
        
        Supports dot notation for nested properties.
        
        Args:
            obj: Object to navigate
            path: Property path (e.g., 'transform.scale.x')
        
        Returns:
            Value at the end of the path
        
        Examples:
            _navigate_path(mesh, 'vertices')  # mesh.vertices
            _navigate_path(mesh, 'transform.scale.x')  # mesh.transform.scale.x
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
        By moving it here, we keep DataField focused on data storage
        and PropertyBinding focused on binding logic.
        
        Args:
            path: Property path (e.g., 'value', 'radius', 'transform.scale')
            value: New value for the property
        
        Raises:
            ValueError: If field type doesn't support property updates
        
        Examples:
            # Update primitive value
            _update_nested_property('value', 42.0)
            # container.value = 42.0
            
            # Update simple property
            _update_nested_property('radius', 5.0)
            # container.radius = 5.0
            
            # Update nested property
            _update_nested_property('transform.scale.x', 2.0)
            # container.transform.scale.x = 2.0
        """
        field = self._element.data
        
        # Only works for Primitive and Complex fields
        if isinstance(field, (PooledField, ArrayField)):
            raise ValueError(
                f"Cannot update properties of {type(field).__name__}. "
                f"Pooled and Array fields do not support property-level updates. "
                f"Use set_value() to replace the entire value instead."
            )
        
        # Get container
        container = self._get_container()
        
        # Navigate to parent of final property
        parts = path.split('.')
        current = container
        
        # Navigate through nested objects
        for part in parts[:-1]:
            current = getattr(current, part)
        
        # Get final property name
        final_property = parts[-1]
        
        # Check if value actually changed
        old_value = getattr(current, final_property, None)
        if old_value == value:
            return  # No change, skip update
        
        # Update the property
        setattr(current, final_property, value)
        
        # Mark dirty and fire observers
        # Note: We fire with the top-level container, not the nested object
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
            pass  # Element might be deleted
    
    def deactivate(self) -> None:
        """
        Deactivate binding and cleanup resources.
        """
        if not self._is_active:
            return
        
        # Cancel debounce timer if exists
        if self._debounce_timer:
            self._debounce_timer.cancel()
            self._debounce_timer = None
        
        # Run all cleanup callbacks
        for cleanup in self._cleanup_callbacks:
            try:
                cleanup()
            except Exception as e:
                print(f"Error during binding cleanup: {e}")
        
        self._cleanup_callbacks.clear()
        self._is_active = False
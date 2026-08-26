from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Generic, List, Optional, TypeVar

T = TypeVar("T")


class BindingMode(Enum):
    """Direction of data flow in a binding"""

    ONE_WAY = "one_way"  # Model → View only
    TWO_WAY = "two_way"  # Model ↔ View (default)
    ONE_TIME = "one_time"  # Initialize once, no updates


# ============================================================================
# Binding Converters
# ============================================================================


class BindingConverter(ABC, Generic[T]):
    """
    Base class for converting between model and view representations.
    Converters can be stateful and specific to a binding instance.
    """

    @abstractmethod
    def to_view(self, model_value: Any) -> Any:
        """
        Convert model value to view representation.

        Args:
            model_value: Value from DataField

        Returns:
            Value suitable for UI element property
        """
        pass

    def to_model(self, view_value: Any) -> Any:
        """
        Convert view value back to model representation.

        Args:
            view_value: Value from UI element

        Returns:
            Value suitable for DataField

        Raises:
            NotImplementedError: If converter is read-only
        """
        raise NotImplementedError(f"{self.__class__.__name__} is read-only")

    def validate(self, view_value: Any) -> tuple[bool, Optional[str]]:
        """
        Validate view value before converting to model.

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None


class PrimitiveUnwrappingConverter(BindingConverter):
    """
    Unwraps PrimitiveType instances to their underlying value.
    Handles both single values and pooled fields.
    """

    def __init__(self, default_value: Any = None):
        self.default_value = default_value

    def to_view(self, model_value: Any) -> Any:
        """Extract .value from PrimitiveType if present"""
        # Handle pooled fields (returns dict)
        if isinstance(model_value, dict):
            if not model_value:
                return self.default_value
            first_value = next(iter(model_value.values()))
            return self._unwrap(first_value)

        return self._unwrap(model_value)

    def _unwrap(self, value: Any) -> Any:
        """Unwrap primitive if it has .value attribute"""
        if value is None:
            return self.default_value
        return value.value if hasattr(value, "value") else value

    def to_model(self, view_value: Any) -> Any:
        """
        For primitive updates, we use DataPort.set_value() which handles
        the .value attribute update, so no wrapping needed here.
        """
        return view_value


class CompositeConverter(BindingConverter):
    """
    Chains multiple converters in sequence.
    Useful for complex transformations: unwrap → convert → format
    """

    def __init__(self, converters: List[BindingConverter]):
        if not converters:
            raise ValueError("CompositeConverter requires at least one converter")
        self.converters = converters

    def to_view(self, model_value: Any) -> Any:
        """Apply converters in sequence"""
        value = model_value
        for converter in self.converters:
            value = converter.to_view(value)
        return value

    def to_model(self, view_value: Any) -> Any:
        """Apply converters in reverse sequence"""
        value = view_value
        for converter in reversed(self.converters):
            value = converter.to_model(value)
        return value

    def validate(self, view_value: Any) -> tuple[bool, Optional[str]]:
        """Validate using all converters"""
        for converter in self.converters:
            is_valid, error_msg = converter.validate(view_value)
            if not is_valid:
                return False, error_msg
        return True, None


class RangeValidatingConverter(BindingConverter):
    """
    Validates and clamps numeric values to a range.
    """

    def __init__(
        self, min_value: Optional[float] = None, max_value: Optional[float] = None, clamp: bool = True
    ):
        """
        Args:
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            clamp: If True, clamp to range; if False, reject out-of-range values
        """
        self.min_value = min_value
        self.max_value = max_value
        self.clamp = clamp

    def to_view(self, model_value: Any) -> Any:
        """Pass through - validation happens on model update"""
        return model_value

    def to_model(self, view_value: Any) -> Any:
        """Validate and optionally clamp value"""
        if self.clamp:
            if self.min_value is not None:
                view_value = max(self.min_value, view_value)
            if self.max_value is not None:
                view_value = min(self.max_value, view_value)
        return view_value

    def validate(self, view_value: Any) -> tuple[bool, Optional[str]]:
        """Validate value is in range"""
        if not self.clamp:
            if self.min_value is not None and view_value < self.min_value:
                return False, f"Value must be at least {self.min_value}"
            if self.max_value is not None and view_value > self.max_value:
                return False, f"Value must be at most {self.max_value}"
        return True, None


# ============================================================================
# Converter Factory (Convenience)
# ============================================================================


class Converters:
    """Factory class for creating common converters"""

    @staticmethod
    def primitive(default_value: Any = None) -> PrimitiveUnwrappingConverter:
        """Create primitive unwrapping converter"""
        return PrimitiveUnwrappingConverter(default_value)

    @staticmethod
    def range(
        min_value: Optional[float] = None, max_value: Optional[float] = None, clamp: bool = True
    ) -> RangeValidatingConverter:
        """Create range validating converter"""
        return RangeValidatingConverter(min_value, max_value, clamp)

    @staticmethod
    def chain(*converters: BindingConverter) -> CompositeConverter:
        """Chain multiple converters"""
        return CompositeConverter(list(converters))

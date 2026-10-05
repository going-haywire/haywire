"""
DataField Classes - Storage and management for node port data

This module provides the complete DataField hierarchy for storing and managing
data in node ports. Each field type handles a specific storage pattern with
uniform API for different access scenarios.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, TypeVar, cast

from haywire.core.types import IType, BaseType, PrimitiveType, Event


T = TypeVar("T")


@dataclass(frozen=True)
class FieldChange:
    """Payload delivered by ``DataField.on_changed``.

    Carries the new value, the value it replaced (``None`` when unknowable,
    e.g. a manual re-fire after in-place container mutation), and the field's
    identity — for a settings cell that is the descriptor's ``storage_key``
    (== the promoted port id); ``""`` when never stamped.
    """

    value: Any
    old: Any = None
    field_id: str = ""


# ============================================================================
# BASE DATAFIELD
# ============================================================================


@dataclass
class DataField(ABC, Generic[T]):
    """
    Abstract base class for all data field types.

    DataFields store data in their natural form and provide uniform
    access patterns for different use cases:
    - Node-to-node data transfer
    - Worker method access
    - Edge validation

    Each IType declares which DataField class handles its storage.

    A field holds its **own value** — written by a widget, the node or a
    setting, and the value that is saved — and, while an edge feeds it, the
    **linked value** that edge delivered. ``get_value()`` returns the linked
    value while there is one, else the own value. A subclass stores the own
    value only, through ``_get_own``/``_set_own``; the linked value lives in a
    second instance of the same class, so it gets the same checks and
    coercion.

    Type tracking via element_type_cls:
    - PrimitiveField: element_type_cls = Python type (float, str, etc.)
    - BaseField: element_type_cls = BaseType class (MeshData, etc.)
    - CompoundField: element_type_cls = IType of elements (FLOAT, MeshData)
    """

    type_cls: type[IType]  # Type class (FLOAT, MeshData, ArrayType, etc.)
    default_kwargs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize event system"""
        self.on_changed: Event[FieldChange] = Event[FieldChange]()
        self.is_dirty: bool = True
        # Identity stamped by the cell's owner at creation (settings bag:
        # storage_key; registry: setting key). Purely descriptive — the field
        # itself never reads it.
        self.field_id: str = ""
        # The value an edge delivered, in a field of this class; None while nothing feeds it.
        self._linked_slot: DataField[T] | None = None

    # ========================================================================
    # CORE API - Implemented by each subclass
    # ========================================================================

    def get_value(self) -> T | None:
        """Return the linked value while an edge feeds this field, else the own value.

        Returns data in its most convenient form:
        - PrimitiveField: unwrapped primitive (42.0), or None if no default was
          registered and no value has been set yet.
        - BaseField: BaseType instance (MeshData(...))
        - CompoundField: container (dict, list, etc.)
        """
        slot = self._linked_slot
        if slot is not None:
            return slot._get_own()
        return self._get_own()

    def get_own_value(self) -> T | None:
        """Return the own value, whether or not an edge's value stands in front of it."""
        return self._get_own()

    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """Store *value* and fire ``on_changed`` with what ``get_value()`` returns before and after.

        Args:
            value: IType instance or raw value, checked and coerced by the field.
            source_id: The id of the edge delivering *value*, which stores it as
                the linked value; ``None`` stores the own value.

        Raises:
            TypeError: If the field rejects *value*.
        """
        observed = self.on_changed.has_observers()
        old = self.get_value() if observed else None
        if source_id is None:
            self._set_own(value)
        else:
            # `is None`, not `or`: an empty ArrayField is falsy.
            slot = self._linked_slot
            if slot is None:
                slot = self._new_linked_slot()
            slot._set_own(value)
            self._linked_slot = slot
        self.is_dirty = True
        if observed:
            self.fire(self.get_value(), old)

    def has_linked_value(self) -> bool:
        """True while an edge's value stands in front of the own value."""
        return self._linked_slot is not None

    def clear_linked(self) -> None:
        """Drop the linked value so ``get_value()`` returns the own value again; no-op without one.

        Fires ``on_changed`` with the own value.
        """
        slot = self._linked_slot
        if slot is None:
            return
        self._linked_slot = None
        self.is_dirty = True
        if self.on_changed.has_observers():
            self.fire(self._get_own(), slot._get_own())

    def _new_linked_slot(self) -> "DataField[T]":
        """Return an empty field of this class to hold a linked value."""
        return type(self)(type_cls=self.type_cls, default_kwargs=self.default_kwargs)

    @abstractmethod
    def _get_own(self) -> T | None:
        """Return the own value in its access form (see ``get_value``)."""

    @abstractmethod
    def _set_own(self, value: Any) -> None:
        """Check, coerce and store *value* as the own value, firing nothing.

        Raises:
            TypeError: If *value* cannot be stored in this field.
        """

    def get_stored_type(self) -> type[IType]:
        """
        Return the type stored in this field — the WIRE type.

        This method allows fields to declare what type they store
        because in some cases this differs from the type the field is
        created from.
        EdgeWrapper uses this to evaluate compatibility and
        which types to pass to AdapterFactory for chain creation.

        The split matters for a ``WrapperType`` field: ``type_cls`` stays
        ``OPTIONAL[INT]`` — what the field IS, which is what the widget and
        the identity read — while this returns ``INT``, what actually flows
        along an edge. That is why a promoted optional setting connects to
        ordinary INT ports with no ``OPTIONAL[T] -> T`` adapter, and why
        ``pin_render`` draws it with the element's own icon and colour.

        Returns:
            type[IType]: The IType class of the instance(s) that is(are) actually stored.
        """
        return self.type_cls

    def accepts_absence(self) -> bool:
        """Whether this field can hold "no value" as a deliberate state.

        Storage capability, NOT type compatibility — the two were only ever
        the same question by accident. ``get_stored_type()`` answers "what
        values flow here" (and so decides whether an edge can exist at all);
        this answers "can this slot be empty", which is what ``Pipe.pull()``
        needs before forwarding absence into a sink.

        Keeping them separate is what lets a promoted ``OPTIONAL[INT]`` port
        be honestly an ``INT`` pin whose sink happens to have somewhere to put
        nothing: OPTIONAL -> OPTIONAL passes absence, OPTIONAL -> INT connects
        natively and skips it.

        Read ONCE per edge, when the pipe is built — never per frame.
        """
        return False

    def keeps_value_per_source(self) -> bool:
        """Whether this field keeps one value per feeding edge rather than one value in total.

        True for a pooled field, whose value is a mapping from feeding edge id to
        that edge's value. False for a field holding a single value. See
        ``DataPort.takes_many_links``.
        """
        return False

    def accepts_own_value(self) -> bool:
        """Whether a write without a source can store an own value in this field.

        False for a field whose value comes only from its edges (a pooled field)
        and for one that holds nothing (an ``ADD`` slot).
        """
        return True

    @abstractmethod
    def reset(self) -> None:
        """Reset field to default value"""
        pass

    @abstractmethod
    def has_data(self) -> bool:
        """Check if field has any data"""
        pass

    def remove_source(self, source_id: str) -> None:
        """Remove a disconnected source."""
        pass

    # ========================================================================
    # EVENT SYSTEM
    # ========================================================================

    def add_observer(self, callback: Callable) -> None:
        """Add observer for value changes"""
        self.on_changed.append(callback)

    def remove_observer(self, callback: Callable) -> None:
        """Remove observer"""
        self.on_changed.remove(callback)

    def fire(self, value: Any, old: Any = None) -> None:
        """Notify observers of change. ``old`` is the replaced value — pass it
        wherever it is knowable; ``None`` marks an in-place/unknowable change."""
        self.on_changed(FieldChange(value, old, self.field_id))

    def mark_clean(self) -> None:
        """Mark field as clean (up-to-date)"""
        self.is_dirty = False

    # ========================================================================
    # SERIALIZATION - absence in the base, a present value in the hooks
    # ========================================================================

    def to_dict(self) -> dict | None:
        """Return the own value as JSON-ready data, or ``None`` (JSON null) for absence.

        A field that ``accepts_absence()`` and holds no own value saves ``None``;
        any other value goes through ``_own_to_dict``.

        Raises:
            TypeError, ValueError: The own value is not a valid value of the field's type.
        """
        if self.accepts_absence() and self._get_own() is None:
            return None
        return self._own_to_dict()

    def from_dict(self, data: dict | None) -> None:
        """Restore the own value from what ``to_dict`` returned.

        Raises:
            TypeError: *data* is ``None`` and this field cannot hold absence.
        """
        if data is None:
            if not self.accepts_absence():
                raise TypeError(
                    f"{type(self).__name__} of {self.type_cls.__name__} cannot hold absence, got null"
                )
            self._set_own(None)
        else:
            self._own_from_dict(data)
        self.is_dirty = True

    def _own_to_dict(self) -> dict:
        """Serialize a present own value. The default returns the type's declared default."""
        if hasattr(self.type_cls, "class_identity"):
            default_dict = getattr(self.type_cls.class_identity, "default", None)
            if isinstance(default_dict, dict):
                return default_dict
        return {}

    def _own_from_dict(self, data: dict) -> None:
        """Restore a present own value from ``_own_to_dict`` output. The default resets the field."""
        self.reset()


def element_to_dict(element_type: "type[IType]", value: Any) -> dict | None:
    """Return *value* serialized the way a field of *element_type* serializes its own value.

    For a container field saving its items one by one.
    """
    cell = element_type.create_field()
    cell.set_value(value)
    return cell.to_dict()


def element_from_dict(element_type: "type[IType]", data: dict | None) -> Any:
    """Return the value a field of *element_type* holds after loading *data*; see ``element_to_dict``."""
    cell = element_type.create_field()
    cell.from_dict(data)
    return cell.get_value()


# ============================================================================
# PRIMITIVEFIELD - Stores unwrapped primitives
# ============================================================================


@dataclass
class PrimitiveField(DataField[T]):
    """
    Stores unwrapped primitive value for maximum performance.

    Storage: T (unwrapped primitive - 42.0 not FLOAT(42.0))
    Worker Access: T (unwrapped primitive)
    Transfer: T (unwrapped primitive)

    Key insight: We store the primitive directly, not wrapped in PrimitiveType.
    Type information comes from type_cls, not from wrapping every value.

    """

    _value: T | None = field(init=False, repr=False)
    _default: T | None = field(init=False, repr=False)

    def __post_init__(self):
        """Initialize primitive field with default value"""
        super().__post_init__()

        # Extract and store unwrapped primitive. ``default_kwargs`` may not
        # carry a "value" key — primitive types are allowed to be created
        # without an explicit default; ``has_data()`` returns False until a
        # set_value() call lands.
        self._default = self.default_kwargs.get("value")
        self._value = self._default

    def get_value(self) -> T | None:
        """Return the linked value while an edge feeds this field, else the own value."""
        # The base's logic without the _get_own call: this read is on the node-execution hot path.
        slot = self._linked_slot
        if slot is not None:
            return slot._value  # type: ignore[attr-defined]
        return self._value

    def _get_own(self) -> T | None:
        """Return the unwrapped primitive — O(1) direct access. None when unset."""
        return self._value

    def _set_own(self, value: Any) -> None:
        """Store the primitive as given; a subclass coerces first (see ``INTField``)."""
        self._value = value

    def reset(self) -> None:
        """Reset to default value"""
        self._value = self._default
        self.is_dirty = True

    def has_data(self) -> bool:
        """Check if has data"""
        return self._value is not None

    # ========================================================================
    # SERIALIZATION - Delegate to PrimitiveType classmethods
    # ========================================================================

    def _own_to_dict(self) -> dict:
        """Serialize the present value through the type's ``to_dict``."""
        # PrimitiveField stores PrimitiveType[T] subclasses; cast to access
        # PrimitiveType's value= constructor.
        primitive_cls = cast("type[PrimitiveType[T]]", self.type_cls)
        return primitive_cls(value=self._value).to_dict()

    def _own_from_dict(self, data: dict) -> None:
        """Restore a present value through the type's ``from_dict``."""
        self._value = self.type_cls.from_dict(data)


# ============================================================================
# BASEFIELD - Stores BaseType instances
# ============================================================================


@dataclass
class BaseField(DataField[BaseType]):
    """
    Stores BaseType instance.

    Storage: BaseType instance (MeshData(...))
    Worker Access: BaseType instance
    Transfer: BaseType instance

    Complex types are already "unwrapped" - the instance IS the value.
    """

    _container: BaseType | None = field(init=False, repr=False)

    def __post_init__(self):
        """Initialize complex field with default instance"""
        super().__post_init__()
        self._container = self._default_instance()

    def _default_instance(self) -> BaseType | None:
        """Return the own value this field starts and resets to: the type built from the default kwargs."""
        # type_cls is type[IType] at the base; for BaseField it's always type[BaseType].
        return cast(BaseType, self.type_cls(**self.default_kwargs))

    def _get_own(self) -> BaseType | None:
        """Return the instance, or ``None`` for an absent value."""
        return self._container

    def _set_own(self, value: Any) -> None:
        """Store a BaseType instance.

        Raises:
            TypeError: If *value* is not an instance of the field's type.
        """
        if not isinstance(value, self.type_cls):
            raise TypeError(f"Expected {self.type_cls.__name__}, got {type(value).__name__}")
        # type_cls is type[IType] at the base; for BaseField it's always type[BaseType].
        self._container = cast(BaseType, value)

    def reset(self) -> None:
        """Reset to default value"""
        self._container = self._default_instance()
        self.is_dirty = True

    def has_data(self) -> bool:
        """Check if has data"""
        return self._container is not None

    # ========================================================================
    # SERIALIZATION - Delegate to BaseType methods
    # ========================================================================

    def _own_to_dict(self) -> dict:
        """Serialize the present instance through its ``to_dict``."""
        # Only a field that holds absence holds None, and the base saves that as null.
        assert self._container is not None
        return self._container.to_dict()

    def _own_from_dict(self, data: dict) -> None:
        """Restore a present instance through the type's ``from_dict``."""
        self._container = self.type_cls.from_dict(data)


# Set field_class attributes after classes are defined
PrimitiveType.field_class = PrimitiveField
BaseType.field_class = BaseField

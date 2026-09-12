"""ADD — a pin that grows a new port from whatever connects to it."""

import builtins
from dataclasses import dataclass
from typing import Any as AnyValue
from typing import Generic, TypeVar

from haywire.core.types import BaseType, FlowType, IType, PortType, StoreStrategy, type
from haywire.core.types.base import _wrapped_identity
from haywire.core.types.fields import DataField

T = TypeVar("T")


@dataclass
class ADDField(DataField):
    """Storage for an ``ADD`` port, which holds no value of its own.

    ``get_stored_type`` reports the element for a parameterization, so an
    ``ADD[STRING]`` pin resolves adapter chains as an ordinary ``STRING`` pin
    while ``type_cls`` stays ``ADD[STRING]`` for the identity and the glyph.
    """

    def get_stored_type(self) -> "builtins.type[IType]":
        element = getattr(self.type_cls, "element_type_cls", None)
        if element is not None and element is not self.type_cls:
            return element  # type: ignore[no-any-return]
        return self.type_cls

    def get_value(self) -> AnyValue:
        return None

    def set_value(self, value: AnyValue, source_id: "str | None" = None) -> None:
        """Ignore the write; an ``ADD`` pin is replaced before values flow."""
        return None

    def reset(self) -> None:
        return None

    def has_data(self) -> bool:
        """Always False: the pin holds nothing to read."""
        return False

    def to_dict(self) -> dict:
        return {"value": None}

    def from_dict(self, data: dict) -> None:
        return None


@type(
    flow_type=FlowType.DATA,
    label="Add",
    description="Grows a new port from whatever connects to it",
    color="#666666",
    icon_in="add_circle_outline",
    icon_in_multi="add_circle_outline",
    icon_out="add_circle",
    icon_out_multi="add_circle",
    default={"value": None},
    # A placeholder holds nothing worth saving.
    store_strategy=StoreStrategy.NEVER,
)
class ADD(BaseType, Generic[T]):
    """A pin that grows a new port when something connects to it.

    Connecting is the point: the node reads the connection and replaces the pin
    with a real one, so `ADD` is a slot that has not been filled yet. It comes
    in two forms, and the difference is what the new port's type will be.

    Bare `ADD` is **undecided** — it takes the type from the other end:

    ```python
    def init(self):
        self.add(ADD.as_inlet("in_0", on_connect="_resolve"))
    ```

    An `INT` outlet connected to a bare `ADD` inlet gives an `INT` pin. Any
    type connects, because there is nothing to convert to yet.

    `ADD[T]` is **decided** — it stays `T` and lets the adapters convert:

    ```python
    self.add(ADD[STRING].as_inlet("in_0", on_connect="_resolve"))
    ```

    An `INT` outlet connected to an `ADD[STRING]` inlet gives a `STRING` pin
    with a conversion on the edge. Only types that convert to `T` connect at
    all: the edge fails to build, so the pin is never grown and nothing is
    silently mistyped. The pin carries `T`'s colour with the `ADD` glyph, so it
    shows what it accepts before the user drags.

    Give the port an `on_connect` handler and rebuild it inside `rejig`:

    ```python
    def _resolve(self, port, edge_wrapper):
        incoming = edge_wrapper._outlet_port.stored_type
        if incoming._is_any:
            return  # the other end is undecided too — nothing to adopt
        with self.rejig(include=[port.id]):
            self.add(incoming.as_inlet(port.id, on_connect="_resolve"))
    ```

    The edge survives the swap and rebuilds against the new type on the next
    validation pass. A handler that declines to retype leaves the pin as it is
    and the edge passing values through untouched.

    An edge between two bare `ADD` pins is valid and does nothing: neither end
    has a type to give. Both resolve once either connects to something concrete.

    Holds no value and renders no widget. Cannot be a config port — a config
    never connects, so it could never resolve.
    """

    field_class = ADDField

    #: True on bare ADD, which connects to anything; False on every ADD[T],
    #: which resolves a real adapter chain instead.
    _is_any = True

    #: Cache of parameterized classes; cleared by the @type decorator on reload.
    _parameterized_cache: "dict[AnyValue, builtins.type]" = {}

    def __init__(self, value: AnyValue = None, **kwargs: AnyValue) -> None:
        """Wrap *value*, where ``None`` means "not filled yet"."""
        self._value = value if value is not None else kwargs.get("value")

    @property
    def value(self) -> AnyValue:
        """The held value, always ``None`` — an ``ADD`` pin stores nothing."""
        return None

    def to_dict(self) -> dict:
        return {"value": None}

    @classmethod
    def from_dict(cls, data: dict) -> AnyValue:
        return None

    @classmethod
    def __class_getitem__(cls, element_type_cls: "builtins.type[IType]"):
        """Return the parameterized ``ADD`` for *element_type_cls*, cached.

        The parameterization takes the element's colour while keeping ``ADD``'s
        own ``registry_key``, ``widget_key`` and glyphs, and clears ``_is_any``
        so its edges resolve adapter chains.

        Raises:
            TypeError: If *element_type_cls* is not an IType class, or is
                itself an ``ADD``.
        """
        if not isinstance(element_type_cls, builtins.type):
            raise TypeError(
                f"ADD[{element_type_cls!r}] is not a valid type — parameterize ADD with "
                f"the IType the new port should carry, e.g. ADD[STRING]."
            )

        if not hasattr(cls, "_parameterized_cache"):
            cls._parameterized_cache = {}

        cache_key = (cls, element_type_cls)
        if cache_key in cls._parameterized_cache:
            return cls._parameterized_cache[cache_key]

        if issubclass(element_type_cls, ADD):
            raise TypeError(
                f"{cls.__name__}[{element_type_cls.__name__}] is not a valid type — "
                f"an ADD pin cannot grow another ADD pin. Parameterize with the "
                f"type the new port should carry."
            )

        class_name = f"{cls.__name__}[{element_type_cls.__name__}]"
        attrs: dict[str, AnyValue] = {
            "element_type_cls": element_type_cls,
            "field_class": cls.field_class,
            # A decided slot converts into its element, so its edges must
            # resolve a real chain instead of passing through untyped.
            "_is_any": False,
            # Share the cache
            "_parameterized_cache": cls._parameterized_cache,
        }
        if hasattr(cls, "class_identity"):
            attrs["class_identity"] = _wrapped_identity(cls.class_identity, element_type_cls)
        if hasattr(cls, "class_library"):
            attrs["class_library"] = cls.class_library

        metaclass = builtins.type(cls)
        parameterized_cls = metaclass(class_name, (cls,), attrs)  # type: ignore[misc]

        cls._parameterized_cache[cache_key] = parameterized_cls
        return parameterized_cls

    @classmethod
    def _validate_port_type(cls, port_type: PortType) -> None:
        """Reject CONFIG.

        Raises:
            ValueError: If *port_type* is ``PortType.CONFIG``.
        """
        if port_type == PortType.CONFIG:
            raise ValueError(
                "ADD cannot be a config port: a config port has no pin, so it "
                "never connects and could never resolve to a real type."
            )

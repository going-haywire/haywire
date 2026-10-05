"""Wire types: how a value travels between ports, and what the framework does with the edge.

Every port has a data type, and the data type declares its wire type. The data
type says what the value is; the wire type says how it travels. A wire type is
a class that is never instantiated. Its metadata is class attributes, and
``__init_subclass__`` gives it an id and records it in an id map. Framework
code branches on a wire type's ``role``, never on which wire type it is.

Two pins connect when their wire keys match (``wires_match``): equal wire type
ids, or a bare ``ADD`` slot, whose key is ``WILDCARD``.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from haywire.core.library.utils import WIRE, derive_library_identity, reg_key
from haywire.core.types.enums import Propagation

if TYPE_CHECKING:
    from haywire.core.settings.settings_edge import EdgeSettings

#: The wire key of a bare ``ADD`` slot, which any wire type connects to.
WILDCARD = "*"

# id -> WireType subclass, filled by WireType.__init_subclass__.
_WIRE_BY_ID: dict[str, type["WireType"]] = {}


class WireRole(Enum):
    """What the framework does with an edge, decided by the edge's wire type.

    The set is closed: framework code branches on the role, so a new role is a
    framework change.

    - ``DEPENDENT``: assembly walks it backward from the node that needs the value.
    - ``SEQUENCE``: the VM walks it forward, in execution order.
    - ``IMMEDIATE``: takes effect on write, with no engine involved.
    - ``VISUAL``: drawn and saved, never executed.
    """

    DEPENDENT = "dependent"
    SEQUENCE = "sequence"
    IMMEDIATE = "immediate"
    VISUAL = "visual"


class ArrowAt(Enum):
    """The end of a computed edge its arrow head is drawn at.

    A computed edge's wire type declares no style bag; its head comes from the
    graph's edge defaults and sits where the wire type's ``arrow_at`` says.

    - ``INLET``: at the inlet end, pointing into the inlet's pin.
    - ``OUTLET``: at the outlet end, pointing back into the outlet's pin.
    - ``NONE``: no head, whatever the graph sets.
    """

    INLET = "inlet"
    OUTLET = "outlet"
    NONE = "none"


class WireType:
    """How a value travels between two ports, and how its pins look.

    Subclass it and name the subclass in ``@type(wire_type=...)``. It is never
    instantiated. A subclass that sets ``role`` is registered under the id
    ``"<library>:wire:<ClassName>"``; setting ``id`` replaces the last segment.
    Compare wire types by ``id``: a hot reload makes a new class object under
    the same id.

    Attributes:
        role: What the framework does with an edge of this wire type.
        propagation: The modes an edge may take. The first is the default, a
            single entry locks it, and an empty tuple means the edge has none.
        pin_kind: The key the skin's ``PinIconResolver`` looks up in its icon
            map, such as ``"control"``. It is not an icon; a type names its own.
        arrow_at: The end a computed edge of this wire type draws its arrow head at;
            see ``ArrowAt``.
        holds_absence: Fields of types declared on this wire type can hold ``None``,
            meaning "no value", and pools of them drop an absent entry.
        style: The ``EdgeSettings`` subclass each edge of this wire type carries,
            holding what the user may set per edge, or ``None`` for a computed
            edge whose look comes from its pins and the graph's edge defaults.
        id: The registry id, set when the class is defined.

    Raises:
        ValueError: When a class from another module already holds the derived id.
        TypeError: When ``style`` is neither ``None`` nor an ``EdgeSettings`` subclass.

    Example::

        class ControlWire(WireType):
            role = WireRole.SEQUENCE
            propagation = (Propagation.EAGER, Propagation.LAZY)
            pin_kind = "control"

        @type(wire_type=ControlWire, default={"value": {}})
        class EXEC(PrimitiveType[dict]): ...

        ControlWire.id  # "haywire-core:wire:ControlWire"
    """

    role: ClassVar[WireRole]
    propagation: ClassVar[tuple[Propagation, ...]] = ()
    pin_kind: ClassVar[str] = ""
    arrow_at: ClassVar[ArrowAt] = ArrowAt.INLET
    holds_absence: ClassVar[bool] = False
    style: ClassVar[type[EdgeSettings] | None] = None
    id: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "role", None) is None:
            return
        style = cls.__dict__.get("style")
        if style is not None:
            # Imported here: settings import the builtin types, which import wire types.
            from haywire.core.settings.settings_edge import EdgeSettings

            if not (isinstance(style, type) and issubclass(style, EdgeSettings)):
                raise TypeError(
                    f"{cls.__qualname__}.style must be an EdgeSettings subclass or None, got {style!r}"
                )
        segment = cls.__dict__.get("id", cls.__name__)
        wire_id = reg_key(derive_library_identity(cls).name, WIRE, segment)
        existing = _WIRE_BY_ID.get(wire_id)
        if existing is not None and (existing.__module__, existing.__qualname__) != (
            cls.__module__,
            cls.__qualname__,
        ):
            raise ValueError(
                f"Wire type id collision: {cls.__module__}.{cls.__qualname__} and "
                f"{existing.__module__}.{existing.__qualname__} both derive id={wire_id!r}"
            )
        # The same module and qualname is a hot reload: the new class replaces the old.
        cls.id = wire_id
        _WIRE_BY_ID[wire_id] = cls

    @classmethod
    def clamp(cls, mode: Propagation | None) -> Propagation | None:
        """Return *mode* when this wire type allows it, else its default; ``None`` when it allows none."""
        if not cls.propagation:
            return None
        return mode if mode in cls.propagation else cls.propagation[0]


def get_wire_type(wire_id: str) -> type[WireType] | None:
    """Return the wire type registered under *wire_id*, or ``None``."""
    return _WIRE_BY_ID.get(wire_id)


def declaring_type_of(type_cls: Any) -> tuple[Any, type[WireType]] | None:
    """Return the type that declares the wire type of *type_cls*, with that wire type, or ``None``.

    A type that declares a wire type in its identity is its own declarer. A
    container or wrapper that declares none (``ArrayType[T]``, ``PooledType[T]``,
    ``ADD[T]``) yields its element's declarer, through any nesting. A bare
    ``ADD``, a type without an identity and ``None`` yield ``None``.
    """
    current = type_cls
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        identity = getattr(current, "class_identity", None)
        wire = getattr(identity, "wire_type", None)
        if wire is not None:
            return current, wire
        current = getattr(current, "element_type_cls", None)
    return None


def wire_type_of(type_cls: Any) -> type[WireType] | None:
    """Return the wire type values of *type_cls* travel on, or ``None``.

    A type answers with the wire type its identity declares. A container or
    wrapper that declares none (``ArrayType[T]``, ``PooledType[T]``, ``ADD[T]``)
    answers with its element's, through any nesting. A bare ``ADD``, a type
    without an identity and ``None`` answer ``None``. See ``declaring_type_of``.
    """
    declared = declaring_type_of(type_cls)
    return declared[1] if declared is not None else None


def wires_match(a: str | None, b: str | None) -> bool:
    """Return whether two pins with wire keys *a* and *b* may be linked.

    True for equal wire type ids, and when exactly one key is ``WILDCARD`` (a bare
    ``ADD`` slot). Two wildcards do not match: the edge would have no wire type
    to take. A key of ``None`` (a port without a wire type) matches nothing.
    """
    if a is None or b is None:
        return False
    if a == WILDCARD and b == WILDCARD:
        return False
    return a == b or a == WILDCARD or b == WILDCARD

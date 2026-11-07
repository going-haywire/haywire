"""Nodes that stamp, read and list the fields on a carrier."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from haywire.barn.builtin.carrier import BundleValue, CarrierValue
from haywire.barn.builtin.types import BUNDLE, CARRIER, FIELD_LIST, INT, STRING, FieldEntry
from haywire.core.di.context import get_type_registry
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node
from haywire.core.settings import NodeSettings, Promotable, bag, setting
from haywire.core.types import IType

logger = logging.getLogger(__name__)

_CARRIER_IN = "carrier_inlet"
_CARRIER_OUT = "carrier_outlet"
_FIELD_PINS = r"_(in|out)$"
_SUMMARY_LENGTH = 60


class MetadataNodeBase(BaseNode):
    """Base of the nodes that stamp and read fields on a carrier.

    Every pin whose id ends in `_in` or `_out` belongs to the field lists and is
    rebuilt from them. A library declares its fields as class attributes:

    ```python
    @node(label="Camera Info", menu="camera", node_type=NodeType.DATA)
    class CameraInfoNode(MetadataNodeBase):
        READ_FIELDS = FIELD_LIST().with_added("camera_timestamp", FLOAT)
    ```
    """

    STAMP_FIELDS: ClassVar[FIELD_LIST] = FIELD_LIST()
    READ_FIELDS: ClassVar[FIELD_LIST] = FIELD_LIST()

    def stamp_fields(self) -> FIELD_LIST:
        """Return the fields this node stamps; each has a pin `<key>_in`."""
        return self.STAMP_FIELDS

    def read_fields(self) -> FIELD_LIST:
        """Return the fields this node reads; each has a pin `<key>_out`."""
        return self.READ_FIELDS

    def init(self) -> None:
        self.add(
            CARRIER.as_inlet(
                _CARRIER_IN,
                label="Carrier",
                description="The value to stamp and read",
                on_connect="hb_carrier_connected",
            )
        )
        self.add(CARRIER.as_outlet(_CARRIER_OUT, label="Carrier", description="The value with its stamps"))
        self._add_field_pins()

    def post_init(self) -> None:
        self.hb_rebuild_field_pins()

    def hb_rebuild_field_pins(self, *_: Any) -> None:
        """Make the field pins match the field lists; a pin that stays keeps its wires and value."""
        with self.rejig(include=_FIELD_PINS):
            self._add_field_pins()

    def _add_field_pins(self) -> None:
        for entry in self.stamp_fields().entries:
            type_cls = _resolve(entry)
            if type_cls is not None:
                self.add(type_cls.as_inlet(f"{entry.key}_in", label=entry.key))
        for entry in self.read_fields().entries:
            type_cls = _resolve(entry)
            if type_cls is not None:
                self.add(type_cls.as_outlet(f"{entry.key}_out", label=entry.key))

    def hb_carrier_connected(self, port: Any, edge_wrapper: Any) -> None:
        """Make the carrier outlet the type of what just connected to the carrier inlet."""
        incoming = edge_wrapper._outlet_port.stored_type
        # Fires again on every relink, so an outlet already of this type stays untouched.
        if self.ports[_CARRIER_OUT].type_cls is incoming or not issubclass(incoming, CARRIER):
            return
        with self.rejig(include=[_CARRIER_OUT]):
            self.add(
                incoming.as_outlet(_CARRIER_OUT, label="Carrier", description="The value with its stamps")
            )
        # A Metadata node downstream follows, so a chain has one type from end to end.
        for edge in self.ports[_CARRIER_OUT].outgoing.valid_edges():
            inlet = edge._inlet_port
            if inlet is not None and inlet.on_connect == "hb_carrier_connected":
                inlet._trigger_callback(inlet.on_connect, edge)

    def worker(self, context: ExecutionContext) -> None:
        """Stamp, pass the carrier on, then write every read pin.

        Raises:
            ValueError: A read field holds a type its pin cannot read, or is absent on a
                type with no default. Every pin is written first.
        """
        carrier = self.value(_CARRIER_IN)
        outlet_type: Any = self.ports[_CARRIER_OUT].stored_type
        # With its wire gone the inlet holds a bare carrier, which the typed outlet cannot pass on.
        if not isinstance(carrier, outlet_type.element_type_cls):
            carrier = outlet_type.empty_value()
        for entry in self.stamp_fields().entries:
            port = self.ports.get(f"{entry.key}_in")
            if port is not None:
                carrier = carrier.stamped(entry.key, self.value(port.id), port.stored_type)
        self.out(_CARRIER_OUT, carrier)

        problem: str | None = None
        for entry in self.read_fields().entries:
            port = self.ports.get(f"{entry.key}_out")
            if port is None:
                continue
            stamp = carrier.fields.get(entry.key)
            if stamp is not None and _reads_as(stamp.type_key, port.stored_type):
                self.out(port.id, stamp.value)
                continue
            # A default rather than None: None leaves a plain inlet on its last value.
            default = _default_of(port)
            self.out(port.id, default)
            if problem is not None:
                continue
            if stamp is not None:
                problem = (
                    f"Field {entry.key!r} holds {_type_name(stamp.type_key)}, "
                    f"this pin reads {port.stored_type.__name__}"
                )
            elif default is None:
                problem = (
                    f"Field {entry.key!r} is absent and {port.stored_type.__name__} has no default, "
                    f"so what this pin feeds keeps its last value"
                )
        if problem is not None:
            raise ValueError(problem)


def _default_of(port: Any) -> Any:
    """Return the value a new pin of ``port``'s type holds; ``None`` for a type with no default."""
    return port.stored_type.create_field().get_value()


def _resolve(entry: FieldEntry) -> type[IType] | None:
    """Return the type ``entry`` declares, or ``None`` with a warning if it is not installed."""
    try:
        return get_type_registry().resolve_type_from_spec(entry.recipe)
    except (ValueError, TypeError, AttributeError) as exc:  # a hand-edited recipe can be any shape
        logger.warning("Field %r has no pin: %s", entry.key, exc)
        return None


def _reads_as(type_key: str, pin_type: type[IType]) -> bool:
    """Return whether a value stamped as ``type_key`` can be read by a pin of ``pin_type``."""
    stamped = get_type_registry().get_type_class(type_key)
    return stamped is not None and issubclass(stamped, pin_type)


def _type_name(type_key: str) -> str:
    """Return the class name of a registered type, or ``type_key`` for one not installed."""
    stamped = get_type_registry().get_type_class(type_key)
    return stamped.__name__ if stamped is not None else type_key


class MetadataFieldSettings(NodeSettings):
    """The fields a Metadata node stamps and reads."""

    stamp = setting[FIELD_LIST](
        FIELD_LIST,
        label="Stamp",
        description="Fields to set, each with an inlet",
        promotable=Promotable.NONE,
    )
    read = setting[FIELD_LIST](
        FIELD_LIST,
        label="Read",
        description="Fields to get, each with an outlet",
        promotable=Promotable.NONE,
    )


@node(
    label="Metadata",
    description="Stamps fields on an image or bundle, and reads them back",
    menu="core/metadata",
    search_tags=["metadata", "field", "stamp", "read", "carrier", "bundle"],
    node_type=NodeType.DATA,
)
class MetadataNode(MetadataNodeBase):
    """Stamps named fields on an image, depth map or bundle, and reads them back.

    List fields under **Stamp** and **Read** in the Properties panel, each with a key
    and a type. A field does nothing until it is listed.

    - **Stamp** adds an inlet `<key>`. Wired, it stamps the incoming value; unwired, it
      stamps the value typed into it.
    - **Read** adds an outlet `<key>`. A field that is not there gives the type's default,
      such as 0 or an empty text.
    - **Carrier** passes the value on with its stamps. The input itself is not changed.

    Stamps apply before reads. Reading a field stamped as another type gives the default
    and reports an error on the node. So does a missing field on a type with no default,
    such as a model, since what the pin feeds would keep its last value. Renaming a field
    means removing and adding it, which drops its wires.

    A node that makes new pixels drops the fields unless its help says it keeps them; to
    keep one anyway, read it before that node and stamp it after. Changing an image's
    channels keeps them. Fields are not saved, either with the graph or in image files.
    """

    metadata_fields = bag(MetadataFieldSettings)

    def stamp_fields(self) -> FIELD_LIST:
        return self.metadata_fields.stamp

    def read_fields(self) -> FIELD_LIST:
        return self.metadata_fields.read

    def post_init(self) -> None:
        super().post_init()
        self.metadata_fields._subscribe_field("stamp", self.hb_rebuild_field_pins)
        self.metadata_fields._subscribe_field("read", self.hb_rebuild_field_pins)


@node(
    label="New Bundle",
    description="Starts an empty bundle, for Metadata nodes to stamp values on",
    menu="core/metadata",
    search_tags=["bundle", "metadata", "new", "carrier"],
    node_type=NodeType.DATA,
)
class NewBundleNode(BaseNode):
    """Starts an empty bundle.

    Wire it into a **Metadata** node and stamp values on it, to make several values
    travel together on one wire.
    """

    def init(self) -> None:
        self.add(BUNDLE.as_outlet("bundle", label="Bundle", description="A bundle with no fields"))

    def worker(self, context: ExecutionContext) -> None:
        self.out("bundle", BundleValue())


@node(
    label="Metadata Info",
    description="Lists the fields an image or bundle carries",
    menu="core/metadata",
    search_tags=["metadata", "info", "field", "carrier", "icc", "exif"],
    node_type=NodeType.DATA,
)
class MetadataInfoNode(BaseNode):
    """Lists what an image, depth map or bundle carries.

    - `Text`: one line per field with its key, type and value, followed by what the
      value holds besides fields, such as the size of an image's ICC profile.
    - `Count`: how many fields it carries.
    """

    def init(self) -> None:
        self.add(CARRIER.as_inlet("carrier", label="Carrier", description="The value to list"))
        self.add(STRING.as_outlet("text", label="Text", description="What the value carries, one line each"))
        self.add(INT.as_outlet("count", label="Count", description="How many fields the value carries"))

    def worker(self, context: ExecutionContext, carrier: CarrierValue) -> None:
        lines = [
            f"{key} ({_type_name(stamp.type_key)}) = {_summary(stamp.value)}"
            for key, stamp in carrier.fields.items()
        ]
        lines += [f"{name}: {fact}" for name, fact in carrier.describe().items()]
        self.out("text", "\n".join(lines) or "No fields")
        self.out("count", len(carrier.fields))


def _summary(value: object) -> str:
    """Return ``value`` as text, short enough that a stamped image cannot flood the list."""
    text = repr(value)
    return text if len(text) <= _SUMMARY_LENGTH else f"{text[:_SUMMARY_LENGTH]}..."

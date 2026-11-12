"""DRAIN — an inlet that queues every value its edge delivers until the node takes them.

Use it where one flow collects values written by another flow at its own pace, so
none is lost or read twice. The node takes the queue with ``NodeData.drain``.
"""

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, List, Optional, Type, TypeVar, cast

from haywire.core.types import type, CompoundType, DataField, Drained, IType
from haywire.core.types.enums import PortType, StoreStrategy
from haywire.core.types.wire import WireRole, declaring_type_of

T = TypeVar("T")

#: Values a drain inlet holds when its port declares no ``max_len``.
DEFAULT_MAX_LEN = 64


@type(
    label="Drain",
    description="Every value its edge delivers, queued until the node takes them",
    default={"max_len": DEFAULT_MAX_LEN},
    store_strategy=StoreStrategy.NEVER,
)
class DRAIN(CompoundType[T]):
    """An inlet that keeps every value its edge delivers, in order, until the node takes them.

    Use it when the values come from another flow that runs at its own pace: an
    ordinary inlet holds only the latest value, so values written between two runs
    of the node are lost, and a value nobody replaced is read again. A drain inlet
    loses none and repeats none.

    The pin is the element's pin, so `DRAIN[AUDIO]` connects to any `AUDIO`
    outlet. It takes one edge. The edge is always eager, and a promoted outlet
    cannot feed it.

    The node takes everything queued since its last take with `self.drain(id)`,
    oldest first. The queue holds `max_len` values (64 unless the port sets it);
    when it is full the oldest value is dropped, and the next take reports how many
    were. The queue is not saved with the graph, and it empties when its edge is
    removed.

    ```python
    def init(self):
        self.add(DRAIN[AUDIO].as_inlet("in_0", label="In 0"))
        self.add(DRAIN[AUDIO].as_inlet("in_1", label="In 1", default={"max_len": 128}))

    def worker(self, context):
        batch = self.drain("in_0")
        for block in batch:
            ...
        if batch.dropped:
            logger.warning("lost %d blocks", batch.dropped)
    ```

    `self.value(id)` shows the queued values without taking them.
    """

    field_class: "Optional[Type[DataField]]" = None  # set to DrainField once it is defined

    @classmethod
    def _validate_port_type(cls, port_type: PortType) -> None:
        """Refuse anything but an inlet.

        Raises:
            ValueError: If *port_type* is not ``INLET``.
        """
        if port_type != PortType.INLET:
            raise ValueError("DRAIN supports inlets only: it queues what an edge delivers.")

    @classmethod
    def _configure_port(cls, port, **context) -> None:
        """Take the colour of the element that declares the wire type.

        Raises:
            ValueError: If the element travels on a control or callback wire.
        """
        declared = declaring_type_of(port.type_cls.element_type_cls)
        if declared is None:
            return
        element, wire = declared
        port.color = element.class_identity.color
        if wire.role is not WireRole.DEPENDENT:
            raise ValueError(
                f"DRAIN needs an element that carries values; {element.__name__} travels on a "
                f"{wire.role.name.lower()} wire"
            )


@dataclass
class DrainField(DataField):
    """Field of a ``DRAIN`` inlet: a bounded, thread-safe queue of the values its edge delivered.

    ``set_value`` with a ``source_id`` appends; when the queue is full the oldest
    value is dropped and counted. ``take()`` returns the queue as ``Drained`` and
    empties it. ``get_value()`` returns a copy. A write without a source raises.
    ``on_changed`` carries the value that joined the queue, not the whole queue.

    The default dict may set ``max_len``, the queue's capacity (at least 1).
    """

    _queue: deque = field(init=False, repr=False)
    _dropped: int = field(default=0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self):
        """Create the queue at the declared ``max_len``.

        Raises:
            ValueError: If ``max_len`` is below 1.
        """
        super().__post_init__()
        max_len = int(self.default_kwargs.get("max_len", DEFAULT_MAX_LEN))
        if max_len < 1:
            raise ValueError(f"DRAIN max_len must be at least 1, got {max_len}")
        self._queue = deque(maxlen=max_len)

    @property
    def max_len(self) -> int:
        """How many values the queue holds before it drops the oldest."""
        return cast(int, self._queue.maxlen)

    def queues_values(self) -> bool:
        """True: every value the edge delivers joins the queue."""
        return True

    def accepts_own_value(self) -> bool:
        """A drain field holds only what its edge delivered."""
        return False

    def get_stored_type(self) -> Type[IType]:
        """Return the element type, which is what travels along the edge."""
        element_type = self.type_cls.element_type_cls
        assert element_type is not None
        return cast(Type[IType], element_type)

    def get_value(self) -> List[Any]:
        """Return a copy of the queued values, oldest first, leaving them queued."""
        with self._lock:
            return list(self._queue)

    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """Append *value* to the queue, dropping the oldest value when it is full.

        ``None`` is ignored. Equal values are each queued.

        Raises:
            ValueError: If *source_id* is ``None``; only an edge writes a drain field.
        """
        if source_id is None:
            raise ValueError("DrainField takes values only from its edge")
        if value is None:
            return
        with self._lock:
            if len(self._queue) == self._queue.maxlen:
                self._dropped += 1
            self._queue.append(value)
        self.is_dirty = True
        if self.on_changed.has_observers():
            self.fire(value)

    def take(self) -> Drained:
        """Return the queued values, oldest first, and empty the queue.

        ``dropped`` on the result counts the values lost to the limit since the last take.
        """
        with self._lock:
            batch = Drained(self._queue, dropped=self._dropped)
            self._queue.clear()
            self._dropped = 0
        return batch

    def remove_source(self, source_id: str) -> None:
        """Empty the queue: its edge is gone."""
        self.reset()

    def reset(self) -> None:
        """Empty the queue and the dropped count."""
        with self._lock:
            self._queue.clear()
            self._dropped = 0
        self.is_dirty = True

    def has_data(self) -> bool:
        """True while a value is queued."""
        return len(self._queue) > 0

    def _get_own(self) -> List[Any]:
        """Return a copy of the queued values; a drain field has no value besides them."""
        return self.get_value()

    def _set_own(self, value: Any) -> None:
        """Refuse a write without a source.

        Raises:
            ValueError: Always; only an edge writes a drain field.
        """
        raise ValueError("DrainField takes values only from its edge")


DRAIN.field_class = DrainField

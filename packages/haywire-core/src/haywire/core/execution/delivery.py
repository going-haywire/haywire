"""How a callback reaches its listeners, and what a pool's backlog does when full (ADR 0097)."""

from __future__ import annotations

from enum import Enum


class Delivery(Enum):
    """How an event node takes the callbacks it listens to.

    ``EVERY`` (the default) runs the node's flow for every callback. ``POOLED``
    shares the callbacks of one emit with the other pooled listeners of that
    emit: the next free one runs it, and while none is free it waits in the
    emitter's backlog.
    """

    EVERY = "every"
    POOLED = "pooled"


class BacklogFull(Enum):
    """What a pool's backlog does with a new callback when it is full."""

    DROP_OLDEST = "drop_oldest"  # The oldest waiting callback makes room.
    WAIT = "wait"  # The emitter waits for room (never a runner thread), then drops the new one.

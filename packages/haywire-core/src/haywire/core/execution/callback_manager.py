"""
Callback Manager - Manages inter-flow communication via callbacks.

The CallbackManager enables control nodes to emit callbacks that
trigger event nodes in other flows within the same graph. Each listener
takes its callbacks by its ``Delivery``: ``EVERY`` gets every callback,
``POOLED`` listeners of one emit share them (ADR 0097).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from haywire.barn.builtin.delivery import BacklogSettings
    from haywire.core.execution.flow import Flow

from haywire.core.execution.delivery import BacklogFull, Delivery
from haywire.core.execution.event_source import CallbackEvent, Trigger

logger = logging.getLogger(__name__)

#: Backlog size of a pool whose emitter passes no ``BacklogSettings``.
DEFAULT_BACKLOG_SIZE = 16


@dataclass(slots=True)
class _Waiting:
    """A callback waiting in a pool's backlog; ``seq`` orders waiting callbacks across pools."""

    seq: int
    payload: dict[str, Any] | None
    timestamp: float


@dataclass(slots=True)
class _Pool:
    """The pooled listeners of one emitter's emit, and the callbacks waiting for one of them."""

    key: tuple[str | None, frozenset[str]]
    members: list[Flow]
    size: int = DEFAULT_BACKLOG_SIZE
    rule: BacklogFull = BacklogFull.DROP_OLDEST
    waiting: deque[_Waiting] = field(default_factory=deque)
    turn: int = 0
    dropped: int = 0
    emitters_waiting: int = 0

    def take_free(self, busy: set[Flow]) -> Flow | None:
        """Return the next free member after the last one taken, or ``None`` when all are busy."""
        count = len(self.members)
        for step in range(count):
            index = (self.turn + step) % count
            flow = self.members[index]
            if flow not in busy:
                self.turn = (index + 1) % count
                return flow
        return None


class CallbackManager:
    """
    Manages callback-based inter-flow communication.

    Responsibilities:
    - Register flows that listen for callbacks
    - Dispatch callbacks to listening flows, each by its ``Delivery``
    - Keep the pools of pooled listeners: busy flows and backlogs
    - Track callback statistics

    One lock guards pools, busy flows, backlogs and the registrations
    ``clear_callbacks`` removes; no ``FlowQueue`` is called while it is held.
    """

    def __init__(self, wait_timeout_s: float = 5.0) -> None:
        """Initialize callback manager.

        Args:
            wait_timeout_s: How long an emit into a full backlog under
                ``BacklogFull.WAIT`` waits for room before the callback is dropped.
        """
        self.callbacks: dict[str, list[Flow]] = {}
        """Maps callback event names to listening flows"""

        self.callback_stats: dict[str, int] = {}
        """Tracks number of times each callback was emitted"""

        self._wait_timeout_s = wait_timeout_s
        self._cond = threading.Condition()
        self._pools: dict[tuple[str | None, frozenset[str]], _Pool] = {}
        self._pools_of: dict[Flow, list[_Pool]] = {}
        self._busy: set[Flow] = set()
        self._seq = 0
        # Bumped by clear_callbacks, so an emit waiting for room gives up.
        self._generation = 0

        logger.debug("CallbackManager initialized")

    def register_callback_listener(self, event_name: str, flow: Flow) -> None:
        """
        Register a flow as listener for a callback event.

        Args:
            event_name: Name of callback event to listen for
            flow: Flow that should be triggered
        """
        if event_name not in self.callbacks:
            self.callbacks[event_name] = []

        if flow not in self.callbacks[event_name]:
            self.callbacks[event_name].append(flow)
            logger.debug(f"Flow {flow.flow_id} registered for callback '{event_name}'")

    def unregister_callback_listener(self, event_name: str, flow: Flow) -> None:
        """
        Unregister a flow from callback event.

        Args:
            event_name: Callback event name
            flow: Flow to unregister
        """
        if event_name in self.callbacks:
            if flow in self.callbacks[event_name]:
                self.callbacks[event_name].remove(flow)
                logger.debug(f"Flow {flow.flow_id} unregistered from callback '{event_name}'")

    def emit_callback(
        self,
        event_name: str | Sequence[str],
        payload: dict[str, Any] | None = None,
        backlog: BacklogSettings | None = None,
    ) -> None:
        """
        Emit a callback event to trigger listening flows.

        Every ``EVERY`` listener of each name gets the callback in its own flow
        queue, in name order. The ``POOLED`` listeners of all the names form one
        pool: the next free one gets the callback, and while none is free it
        waits in the pool's backlog. Under ``BacklogFull.WAIT`` a full backlog
        holds the calling thread, except the runner thread of a member's group,
        which drops the callback instead. A dropped callback counts on the
        queue of the member whose turn it was.

        Args:
            event_name: Name of the callback event, or the names of every
                subscriber of one emitter, so its pooled listeners share the callback.
            payload: Optional data to pass to triggered flows
            backlog: The emitter's backlog settings; ``None`` uses a backlog of
                ``DEFAULT_BACKLOG_SIZE`` that drops the oldest.

        Example::

            # One name: every listener of it runs.
            manager.emit_callback("tick_event_1", {"delta_time": 0.016})
            # All subscribers in one emit: pooled ones share it, by the emitter's backlog.
            manager.emit_callback(["event_a", "event_b"], payload, backlog=node.backlog)
        """
        names = [event_name] if isinstance(event_name, str) else list(event_name)
        pooled: list[Flow] = []
        for name in names:
            self.callback_stats[name] = self.callback_stats.get(name, 0) + 1

            flows = self.callbacks.get(name, [])
            if not flows:
                logger.debug("Callback '%s' emitted but no flows listening", name)
                continue

            logger.debug("Emitting callback '%s' to %d flows", name, len(flows))
            trigger = Trigger(source_key=f"callback:{name}", payload=payload, timestamp=time.time())
            for flow in flows:
                if _is_pooled(flow):
                    if flow not in pooled:
                        pooled.append(flow)
                elif flow.queue:
                    flow.queue.enqueue_trigger(trigger)
                else:
                    logger.warning(f"Flow {flow.flow_id} has no queue, cannot trigger callback")

        if pooled:
            self._emit_pooled(pooled, payload, backlog)

    def _emit_pooled(
        self, members: list[Flow], payload: dict[str, Any] | None, backlog: BacklogSettings | None
    ) -> None:
        """Hand the callback to the pool's next free member, or put it in the pool's backlog."""
        owner = backlog.owner_id if backlog is not None else None
        size = max(1, int(backlog.size)) if backlog is not None else DEFAULT_BACKLOG_SIZE
        rule = backlog.rule if backlog is not None else BacklogFull.DROP_OLDEST
        timestamp = time.time()
        deadline: float | None = None
        picked: Flow | None = None
        dropped: tuple[_Pool, str] | None = None
        dropped_on: Flow | None = None
        with self._cond:
            generation = self._generation
            pool = self._pool_for(owner, members)
            pool.size, pool.rule = size, rule
            while generation == self._generation:
                picked = pool.take_free(self._busy)
                if picked is not None:
                    self._busy.add(picked)
                    break
                if len(pool.waiting) < pool.size:
                    self._seq += 1
                    pool.waiting.append(_Waiting(self._seq, payload, timestamp))
                    break
                if rule is BacklogFull.DROP_OLDEST:
                    pool.waiting.popleft()
                    dropped = (pool, "the backlog is full, its oldest callback makes room")
                    continue
                if self._is_member_runner(pool):
                    # A member's own runner would wait for itself (ADR 0064 D6).
                    dropped = (pool, "the backlog is full and the emit runs in a member's group")
                    break
                if deadline is None:
                    deadline = time.monotonic() + self._wait_timeout_s
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    dropped = (pool, f"the backlog stayed full for {self._wait_timeout_s} s")
                    break
                pool.emitters_waiting += 1
                try:
                    self._cond.wait(remaining)
                finally:
                    pool.emitters_waiting -= 1
            if dropped is not None:
                dropped_on = self._count_drop(dropped[0])
        if dropped is not None and dropped_on is not None:
            self._report_drop(dropped_on, dropped[1], rule)
        if picked is not None:
            self._enqueue_pooled(picked, payload, timestamp)

    def _count_drop(self, pool: _Pool) -> Flow:
        """Count a drop on ``pool`` and return the member whose turn it was; call under the lock."""
        pool.dropped += 1
        return pool.members[pool.turn]

    def _report_drop(self, member: Flow, reason: str, rule: BacklogFull) -> None:
        """Count a drop on the queue of the member whose turn it was, for the Flow meter, and log it."""
        if member.queue is not None:
            member.queue.count_dropped()
        # Drop oldest loses callbacks by design, as QueueMode.DROP does; Wait losing one is a warning.
        level = logging.DEBUG if rule is BacklogFull.DROP_OLDEST else logging.WARNING
        logger.log(level, "Dropping a pooled callback for %s: %s", member.flow_id, reason)

    def _pool_for(self, owner: str | None, members: list[Flow]) -> _Pool:
        """Return the pool of ``owner`` and ``members``, creating it on first use; call under the lock."""
        key = (owner, frozenset(flow.flow_id for flow in members))
        pool = self._pools.get(key)
        if pool is None:
            pool = _Pool(key=key, members=list(members))
            self._pools[key] = pool
            for flow in members:
                self._pools_of.setdefault(flow, []).append(pool)
        return pool

    def _enqueue_pooled(self, flow: Flow, payload: dict[str, Any] | None, timestamp: float) -> None:
        """Put one callback into a busy member's queue; a refused one frees the member."""
        event_name = (
            flow.event_subscription.event_name if isinstance(flow.event_subscription, CallbackEvent) else ""
        )
        trigger = Trigger(source_key=f"callback:{event_name}", payload=payload, timestamp=timestamp)
        if flow.queue is None:
            logger.warning("Dropping a pooled callback: flow %s has no queue", flow.flow_id)
        elif flow.queue.enqueue_trigger(trigger):
            return
        else:
            logger.debug("Dropping a pooled callback: flow %s refused it (stopping)", flow.flow_id)
        with self._cond:
            self._busy.discard(flow)
            self._cond.notify_all()

    def trigger_done(self, flow: Flow) -> None:
        """Hand a pooled flow whose callback is done the oldest callback waiting in its pools, or free it.

        Called by the flow's ``FlowQueue`` for every callback it takes out of its
        queue: after the frame, also one that raised, and for each one discarded
        at a stop.
        """
        with self._cond:
            if flow not in self._busy:
                return
            source: _Pool | None = None
            for pool in self._pools_of.get(flow, []):
                if pool.waiting and (source is None or pool.waiting[0].seq < source.waiting[0].seq):
                    source = pool
            self._cond.notify_all()
            if source is None:
                self._busy.discard(flow)
                return
            item = source.waiting.popleft()
        self._enqueue_pooled(flow, item.payload, item.timestamp)

    @staticmethod
    def _is_member_runner(pool: _Pool) -> bool:
        """Return ``True`` when called on the runner thread of a pool member's group."""
        for flow in pool.members:
            group = flow.queue.group if flow.queue is not None else None
            if group is not None and group.is_runner_thread():
                return True
        return False

    def get_listeners(self, event_name: str) -> list[Flow]:
        """
        Get all flows listening for a callback event.

        Args:
            event_name: Callback event name

        Returns:
            List of flows listening for this callback
        """
        return self.callbacks.get(event_name, []).copy()

    def clear_callbacks(self) -> None:
        """Clear all callback registrations, pools and backlogs; an emit waiting for room gives up."""
        with self._cond:
            self.callbacks.clear()
            self._generation += 1
            self._pools.clear()
            self._pools_of.clear()
            self._busy.clear()
            self._cond.notify_all()
        logger.debug("All callback registrations cleared")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get callback statistics.

        Returns:
            Dictionary with callback stats; ``pools`` lists each pool's members
            (flow ids), how many are busy, how many callbacks wait, how many
            were dropped and how many emitting threads wait for room.
        """
        with self._cond:
            pools = [
                {
                    "members": [flow.flow_id for flow in pool.members],
                    "busy": sum(1 for flow in pool.members if flow in self._busy),
                    "waiting": len(pool.waiting),
                    "dropped": pool.dropped,
                    "emitters_waiting": pool.emitters_waiting,
                }
                for pool in self._pools.values()
            ]
        return {
            "total_callbacks": len(self.callbacks),
            "callbacks": [
                {
                    "event_name": event_name,
                    "listener_count": len(flows),
                    "emit_count": self.callback_stats.get(event_name, 0),
                }
                for event_name, flows in self.callbacks.items()
            ],
            "pools": pools,
        }


def _is_pooled(flow: Flow) -> bool:
    """Return ``True`` when the flow's event node chose ``Delivery.POOLED``."""
    subscription = flow.event_subscription
    return isinstance(subscription, CallbackEvent) and subscription.delivery is Delivery.POOLED

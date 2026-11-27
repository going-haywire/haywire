"""Settings for pooled callback delivery: an event node's Delivery, an emitter's Backlog (ADR 0097).

An event node includes ``DeliverySettings`` and passes ``delivery`` into the
``CallbackEvent`` it listens with. An emitter includes ``BacklogSettings`` and
passes the bag with each emit, so the pool its pooled listeners form knows its
size, its full rule and which emitter owns it.
"""

from __future__ import annotations

from haywire.barn.builtin.types import CHOICES, INT
from haywire.core.execution.callback_manager import DEFAULT_BACKLOG_SIZE
from haywire.core.execution.delivery import BacklogFull, Delivery
from haywire.core.settings import NodeSettings, Promotable, setting

_DELIVERY_CHOICES = {"Every": Delivery.EVERY, "Pooled": Delivery.POOLED}
_FULL_CHOICES = {"Drop oldest": BacklogFull.DROP_OLDEST, "Wait": BacklogFull.WAIT}


class DeliverySettings(NodeSettings):
    """How an event node takes the callbacks it listens to. Applies on the next start.

    Example::

        from haywire.api import CallbackEvent, DeliverySettings, bag

        class TickEventNode(BaseNode):
            delivery = bag(DeliverySettings)

            def post_init(self):
                self.event_subscription = CallbackEvent(
                    event_name=self.node_id, delivery=self.delivery.delivery
                )
    """

    mode = setting[CHOICES](
        "Every",
        label="Delivery",
        category="Delivery",
        description=(
            "Every runs this flow for every event. Pooled shares the events with the other "
            "pooled listeners of the same emitter: the next free one runs each event."
        ),
        widget_config={"options": list(_DELIVERY_CHOICES)},
        promotable=Promotable.CONFIG,
    )

    @property
    def delivery(self) -> Delivery:
        """Return the chosen ``Delivery``; an unknown choice reads as ``Delivery.EVERY``."""
        return _DELIVERY_CHOICES.get(str(self.mode), Delivery.EVERY)


class BacklogSettings(NodeSettings):
    """Where an emitter's events wait while every pooled listener is busy.

    Pass the bag with each emit. An emitter whose listeners all use Every
    ignores it.

    Example::

        from haywire.api import BacklogSettings, bag

        class TickEmitNode(BaseNode):
            backlog = bag(BacklogSettings)

            def _tick(self, context, names):
                context.emit_callback(names, {"delta_time": 0.016}, backlog=self.backlog)
    """

    size = setting[INT](
        DEFAULT_BACKLOG_SIZE,
        min=1,
        max=1024,
        label="Backlog Size",
        category="Backlog",
        description="How many events wait while every pooled listener is busy.",
        promotable=Promotable.CONFIG,
    )
    full = setting[CHOICES](
        "Drop oldest",
        label="When Full",
        category="Backlog",
        description=(
            "Drop oldest makes room by losing the oldest waiting event. Wait holds the emitter "
            "up to 5 s for room, then loses the new event."
        ),
        widget_config={"options": list(_FULL_CHOICES)},
        promotable=Promotable.CONFIG,
    )

    @property
    def rule(self) -> BacklogFull:
        """Return the chosen full rule; an unknown choice reads as ``BacklogFull.DROP_OLDEST``."""
        return _FULL_CHOICES.get(str(self.full), BacklogFull.DROP_OLDEST)

    @property
    def owner_id(self) -> str | None:
        """Return the id of the emitter node this bag belongs to, or ``None`` for an unbound bag."""
        node = self._node
        return node.node_id if node is not None else None

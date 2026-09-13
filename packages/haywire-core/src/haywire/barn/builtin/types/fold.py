from haywire.core.types import FlowType, StoreStrategy, type

from .specs import BOOL


@type(
    flow_type=FlowType.DATA,
    label="Fold",
    description="Hides or shows the ports inside it",
    color="#90a4ae",
    default={"value": True},
    # The disclosure triangle on the node card is the whole control, so a fold
    # renders no widget of its own.
    widget_key=None,
    # A widget-less port would not otherwise be stored, and a fold that is not
    # stored forgets whether the user left it open.
    store_strategy=StoreStrategy.ALWAYS,
)
class FOLD(BOOL):
    """Fold data type.

    Minted by `NodeData.fold()`; never declared directly. Its value is the
    fold's open state — `True` while open — which a node may read like any
    port, or hook with `on_change=` to reconfigure itself when the user folds.

    Pass `description=` to `fold()` to replace the default shown in the fold
    header's hover tooltip.
    """

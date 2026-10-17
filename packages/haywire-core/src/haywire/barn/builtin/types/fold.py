from typing import TYPE_CHECKING, Any

from haywire.barn.builtin import widget_keys
from haywire.core.types import StoreStrategy, type

from .specs import BOOL
from ..wires import DataWire

if TYPE_CHECKING:
    from haywire.core.types.port import DataPort


@type(
    wire_type=DataWire,
    label="Fold",
    description="Hides or shows the ports inside it",
    color="#90a4ae",
    default={"value": True},
    # The fold's header on the node card is its widget.
    widget_key=widget_keys.FOLD_WIDGET,
    # A fold that is not stored forgets whether the user left it open.
    store_strategy=StoreStrategy.ALWAYS,
)
class FOLD(BOOL):
    """Fold data type.

    Minted by `NodeData.fold()`; never declared directly. Its value is the
    fold's open state — `True` while open — which a node may read like any
    port, or hook with `on_change=` to reconfigure itself when the user folds.
    Click the fold's header on the node card to open or close it.

    Pass `description=` to `fold()` to replace the default shown in the fold
    header's hover tooltip.
    """

    @classmethod
    def _configure_port(cls, port: "DataPort", **context: Any) -> None:
        """Give the port the fold header widget, labelled and described like the port, and
        redraw its node card whenever the fold opens or closes.

        Applies to a port loaded from a saved graph too, whatever widget it was saved with.
        """
        port.widget_key = widget_keys.FOLD_WIDGET
        # The header widget sees only its model, so the label and description travel in its config.
        properties = dict(port.widget_config.get("properties", {}))
        properties.setdefault("text", port.label)
        properties.setdefault("description", port.description)
        port.widget_config = {**port.widget_config, "properties": properties}

        def _redraw(_event: Any) -> None:
            wrapper = port._wrapper
            if wrapper is not None and wrapper.state.is_registered:
                wrapper.redraw()

        port.data.on_changed += _redraw

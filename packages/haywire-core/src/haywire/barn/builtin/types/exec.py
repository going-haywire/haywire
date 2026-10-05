"""EXEC — the execution signal that sequences one node after another."""

from haywire.core.types import PrimitiveType, StoreStrategy, type
from ..wires import ControlWire


@type(
    wire_type=ControlWire,
    label="Execution Signal",
    description="Signal for controlling execution flow between nodes",
    color="#004cff",
    default={"value": {}},
    store_strategy=StoreStrategy.NEVER,
)
class EXEC(PrimitiveType[dict]):
    """Execution signal carrying an optional `dict` payload."""

    @classmethod
    def create_default(cls) -> "EXEC":
        return cls({})

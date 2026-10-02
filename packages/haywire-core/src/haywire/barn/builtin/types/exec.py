"""EXEC — the execution signal that sequences one node after another."""

from haywire.core.types import FlowType, PrimitiveType, StoreStrategy, type


@type(
    flow_type=FlowType.CONTROL,
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

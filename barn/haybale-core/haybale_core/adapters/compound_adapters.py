from typing import Any, List, override

from haywire.core.adapter.base import adapter, BaseAdapter

from ..types.array_type import ArrayType


@adapter(
    label="Array to Array",
    description="Transform array elements (ArrayType[X] → ArrayType[Y])",
    converts_from=ArrayType,
    converts_to=ArrayType,
    priority=0,
)
class ArrayArrayAdapter(BaseAdapter):
    """
    Transforms ArrayType[X] → ArrayType[Y].

    Uses internal adapter chain for element transformation.
    Always skips None values to prevent chain failures.

    Examples:
        # ArrayType[FLOAT] → ArrayType[FLOAT] (no element transformation)
        adapter = ArrayArrayAdapter()
        result = adapter.convert([1.0, 2.0, 3.0])
        # → [1.0, 2.0, 3.0]

        # ArrayType[FLOAT] → ArrayType[STRING] (with element transformation)
        float_to_str = FloatToStringAdapter()
        adapter = ArrayArrayAdapter(element_adapter=float_to_str)
        result = adapter.convert([1.5, None, 2.7])
        # → ["1.50", "2.70"]  (None skipped)
    """

    @override
    def convert(self, values: List[Any]) -> List[Any]:
        """
        Transform each element or pass through.

        Args:
            values: List of source elements

        Returns:
            List of transformed elements (None values skipped)
        """
        return [
            self._chain.execute(v)
            for v in values
            if v is not None  # Always skip None
        ]

    # Override to execute conversion since we treat the inner chain as element adapter
    @override
    def execute(self, value):
        return self.convert(value)

    @override
    def get_test_value(self) -> Any:
        # Generate list of random values from the element adapter chain
        return [self._chain.get_test_value() for _ in range(5)]

from typing import Any, List
from typing_extensions import override

from haywire.api import BaseAdapter, adapter

from haybale_core.types.array_type import ARRAY


@adapter(
    label="Array to Array",
    description="Transform array elements (ARRAY[X] → ARRAY[Y])",
    converts_from=ARRAY,
    converts_to=ARRAY,
    priority=0,
)
class ArrayArrayAdapter(BaseAdapter):
    """
    Transforms ARRAY[X] → ARRAY[Y].

    Uses internal adapter chain for element transformation.
    Always skips None values to prevent chain failures.

    Examples:
        # ARRAY[FLOAT] → ARRAY[FLOAT] (no element transformation)
        adapter = ArrayArrayAdapter()
        result = adapter.convert([1.0, 2.0, 3.0])
        # → [1.0, 2.0, 3.0]

        # ARRAY[FLOAT] → ARRAY[STRING] (with element transformation)
        float_to_str = FloatToStringAdapter()
        adapter = ArrayArrayAdapter(element_adapter=float_to_str)
        result = adapter.convert([1.5, None, 2.7])
        # → ["1.50", "2.70"]  (None skipped)
    """

    @override
    def convert(self, value: List[Any]) -> List[Any]:
        """
        Transform each element or pass through.

        Args:
            value: List of source elements

        Returns:
            List of transformed elements (None values skipped)
        """
        return [
            self._chain.execute(v)
            for v in value
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

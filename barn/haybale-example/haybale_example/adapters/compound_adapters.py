from typing import Any, Dict, List
from typing_extensions import override

from haywire.api import BaseAdapter, adapter

from haybale_core.types import ARRAY
from haybale_example.types.maps_string_type import MapsStringType


@adapter(
    label="MapsString to Array",
    description="Transform MapsString elements (MapsStringType[str, X] → ARRAY[Y])",
    converts_from=MapsStringType,
    converts_to=ARRAY,
    priority=0,
)
class MapsStringArrayAdapter(BaseAdapter):
    """
    Transforms MapsStringType[str, X] → ARRAY[Y].

    Uses internal adapter chain for element transformation.
    Always skips None values to prevent chain failures.

    Examples:
        # MapsStringType[FLOAT] → ARRAY[FLOAT] (no element transformation)
        adapter = MapsStringArrayAdapter()
        result = adapter.convert({"a": 1.0, "b": 2.0, "c": 3.0})
        # → [1.0, 2.0, 3.0]

        # MapsStringType[FLOAT] → ARRAY[STRING] (with element transformation)
        float_to_str = FloatToStringAdapter()
        adapter = MapsStringArrayAdapter(_chain=float_to_str)
        result = adapter.convert({"a": 1.5, "b": None, "c": 2.7})
        # → ["1.50", "2.70"]  (None skipped)
    """

    @override
    def convert(self, value: Dict[str, Any]) -> List[Any]:
        return list(value.values())

    @override
    def get_test_value(self):
        array_values = self._chain.get_test_value()
        return {f"key_{i}": value for i, value in enumerate(array_values)}

    @override
    def get_test_repetitions(self):
        return 2

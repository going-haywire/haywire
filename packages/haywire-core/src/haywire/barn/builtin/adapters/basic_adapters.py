"""
Basic type conversion adapters
"""

import random

from typing_extensions import override

from haywire.barn.builtin.types import BOOL, CHOICES, FLOAT, INT, STRING
from haywire.core.adapter.base import BaseAdapter, adapter


@adapter(description="Convert integer to float", converts_from=INT, converts_to=FLOAT)
class IntToFloatAdapter(BaseAdapter):
    @override
    def convert(self, value: int) -> float:
        return float(value)

    def get_test_value(self) -> int:
        return int(random.randrange(0, 100))


@adapter(description="Convert float to integer", converts_from=FLOAT, converts_to=INT)
class FloatToIntAdapter(BaseAdapter):
    @override
    def convert(self, value: float) -> int:
        return int(value)

    def get_test_value(self) -> float:
        return float(random.randrange(0, 100) * 1.0)


@adapter(description="Convert float to integer", converts_from=FLOAT, converts_to=STRING)
class FloatToStringAdapter(BaseAdapter):
    """Convert integer to float"""

    @override
    def convert(self, value: float) -> str:
        return str(value)

    def get_test_value(self) -> float:
        return float(random.randrange(0, 100))


@adapter(description="Convert bool to integer", converts_from=BOOL, converts_to=INT)
class BoolToIntAdapter(BaseAdapter):
    """Convert bool to integer"""

    @override
    def convert(self, value: bool) -> int:
        return int(value)

    def get_test_value(self) -> bool:
        return random.choice([True, False])


@adapter(description="String into a choices slot", converts_from=STRING, converts_to=CHOICES)
class StringToChoicesAdapter(BaseAdapter):
    """STRING -> CHOICES needs an explicit adapter: CHOICES is the descendant,
    so (per adapter-canon.md) an ancestor-to-descendant conversion is never a
    free passthrough — not every string is a valid choice. The reverse
    direction (CHOICES -> STRING) needs no adapter at all: CHOICES(STRING)
    already gets a free passthrough via AdapterFactory's
    issubclass(source_type, sink_type) check."""

    @override
    def convert(self, value: str) -> str:
        return value

    def get_test_value(self) -> str:
        return "fast"

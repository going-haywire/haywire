# tests/core/types/test_primitive_port_default.py
"""
A primitive port's default must be a value its type accepts:

- ``INT.as_outlet("n", default="abc")`` raises TypeError naming the port when
  the spec is built (i.e. inside the node's ``init()``), not at copy/save time
- a valid or coercible default builds fine
- a value that still reaches the field unconverted makes ``to_dict()`` raise a
  HaywireException naming the port, not a bare ValueError from ``int()``
"""

from typing import Any, cast

import pytest

from haywire.barn.builtin.types import FLOAT, INT, STRING
from haywire.core.errors.haywire_exception import HaywireException

pytestmark = pytest.mark.integration


class TestDefaultRejectedAtDeclaration:
    def test_int_outlet_with_text_default_raises_naming_the_port(self):
        with pytest.raises(TypeError, match="toppings"):
            INT.as_outlet("toppings", default="default value")

    def test_float_inlet_with_text_default_raises(self):
        with pytest.raises(TypeError, match="not a valid FLOAT"):
            FLOAT.as_inlet("ratio", default="half")

    @pytest.mark.parametrize(
        ("itype", "default"),
        [(INT, 3), (INT, 3.7), (INT, "4"), (FLOAT, 1), (STRING, "text")],
    )
    def test_accepted_defaults_build(self, itype, default):
        spec = itype.as_inlet("value", default=default)
        assert spec["kwargs"]["default"] == {"value": default}


class TestUnconvertedValueAtSerialization:
    def test_to_dict_raises_haywire_exception_naming_the_port(self, library_system):
        from haywire.core.types.port import DataPort

        spec = INT.as_outlet("toppings", default=1)
        port = DataPort.from_spec(
            cast(Any, spec), library_system.get_type_registry(), cast(Any, None), cast(Any, None)
        )
        cast(Any, port._data)._value = "abc"  # bypasses INTField's coercion
        with pytest.raises(HaywireException, match="toppings"):
            port.to_dict(include_data=True)

"""An array port holding [] is a port with a value, not a port without data."""

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, PortType

pytestmark = pytest.mark.unit


def _array_port(port_type: PortType) -> DataPort:
    from haybale_core.types import ArrayType

    array = ArrayType[FLOAT]
    return DataPort(
        registry_id="a",
        registry_key=array.class_identity.registry_key,
        label="A",
        id="a",
        type_cls=array,
        port_type=port_type,
    )


def test_an_empty_array_reads_as_an_empty_list():
    assert _array_port(PortType.INLET).get_value() == []


def test_the_first_write_to_an_empty_array_is_kept():
    port = _array_port(PortType.OUTLET)

    port.set_value([1.0, 2.0])

    assert port.get_value() == [1.0, 2.0]


def test_an_array_cleared_to_empty_is_saved_and_reloads_empty():
    from haywire.core.types.enums import StoreStrategy

    port = _array_port(PortType.OUTLET)
    port.store_strategy = StoreStrategy.ALWAYS
    port.set_value([1.0, 2.0])
    port.set_value([])

    spec = port.to_dict(include_data=True)

    assert "field_data" in spec
    port._data.from_dict(spec["field_data"])
    assert port.get_value() == []

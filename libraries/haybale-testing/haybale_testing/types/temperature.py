"""
Temperature type - derived from FLOAT for testing type hierarchy support.
"""

from haybale_core.types.specs import FLOAT, FLOATField
from haywire.core.types.decorator import type
from haywire.core.data.enums import FlowType


@type(
    registry_id='temperature',
    label='Temperature',
    description='Temperature in Celsius',
    color='#ff5722',
    flow_type=FlowType.DATA,
    default={'value': 20.0},
)
class Temperature(FLOAT):
    """Temperature in Celsius — derived from FLOAT."""
    pass


# Reuse FLOATField to guarantee float storage
Temperature.field_class = FLOATField

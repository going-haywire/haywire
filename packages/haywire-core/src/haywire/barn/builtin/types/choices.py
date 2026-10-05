from haywire.core.types import type
from haywire.barn.builtin import widget_keys

from .specs import STRING
from ..wires import DataWire


@type(
    wire_type=DataWire,
    label="Choices",
    description="A string constrained to a set of options (options live per-use in widget_config)",
    color="#ffd54f",
    default={"value": ""},
    widget_key=widget_keys.SELECT_WIDGET,
)
class CHOICES(STRING):
    """String selected from a per-setting/per-port option list.

    The TYPE carries only 'renders as a select'; the options are supplied by
    each setting/port via widget_config={"options": [...] | {value: label} |
    callable}.
    """

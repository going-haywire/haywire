"""ANNOTATION — the drawn-only wire of annotation nodes, its look and its type.

The wire and its style bag live here, beside the type, and not in ``wires.py``:
the bag's fields need builtin types, and every builtin type imports ``wires.py``.
"""

from haywire.barn.builtin import widget_keys
from haywire.core.edge.arrow_heads import NO_HEAD
from haywire.core.edge.style import dash_choices
from haywire.core.settings import EdgeSettings, setting
from haywire.core.types import StoreStrategy, WireRole, WireType, type

from .choices import CHOICES
from .color import COLOR
from .specs import FLOAT, STRING


class AnnotationStyle(EdgeSettings):
    """The look of an annotation edge, set per edge in the edge menu and the Edge inspector."""

    color = setting[COLOR]("#8e8e8e", label="Colour")
    width = setting[FLOAT](2.0, label="Width", min=0.5, max=12.0)
    dash = setting[CHOICES]("solid", label="Dash", widget_config={"options": dash_choices})
    arrow_start = setting[STRING](NO_HEAD, label="Start Head", widget={"key": widget_keys.ARROW_HEAD_WIDGET})
    arrow_end = setting[STRING]("arrow", label="End Head", widget={"key": widget_keys.ARROW_HEAD_WIDGET})


class AnnotationWire(WireType):
    """Links between annotation nodes: drawn and saved, never executed."""

    role = WireRole.VISUAL
    propagation = ()
    pin_kind = "annotation"
    style = AnnotationStyle


@type(
    wire_type=AnnotationWire,
    label="Annotation",
    description="A link between annotation nodes; carries no value",
    color="#8e8e8e",
    widget_key=None,
    store_strategy=StoreStrategy.NEVER,
)
class ANNOTATION(STRING):
    """A link between two annotation nodes.

    It is drawn and saved with the graph but never run, so it carries no value.
    Its colour, dash, width and arrow heads are set per link.
    """

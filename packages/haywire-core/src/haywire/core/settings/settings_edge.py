# haywire/core/settings/settings_edge.py
"""
EdgeSettings — base class for an edge's style bag.

The Settings flavour parallel to GraphSettings and NodeSettings:

- Per-instance DataField cells; never registered with SettingsRegistry.
- Named by a wire type's ``style``; each edge on that wire type holds one while
  it validates (see ``EdgeWrapper.style``), saved under the edge's ``"style"`` key.
- Carries an ``_edge`` backref; ``_node`` stays None, so promotion is
  unavailable.
"""

from typing import TYPE_CHECKING

from typing_extensions import dataclass_transform

from .descriptor import setting
from .settings import Settings

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.settings.registry import SettingsRegistry


@dataclass_transform(field_specifiers=(setting,))
class EdgeSettings(Settings):
    """Base class for the look a wire type lets the user set per edge.

    Subclass it, declare the fields the user may edit, and name the subclass in
    a wire type's ``style``. A field's default is that wire type's look. The
    canvas draws the fields named in ``haywire.core.edge.style.STYLE_FIELDS``:
    ``color`` (a colour string), ``width`` (px), ``dash`` (a key of
    ``DASH_PATTERNS``), ``arrow_start`` and ``arrow_end`` (a head name, or
    ``"none"``). A field the bag does not declare falls back to the graph's edge
    defaults. Other fields are saved but not drawn.

    Example::

        class NoteStyle(EdgeSettings):
            color = setting[COLOR]("#8e8e8e", label="Colour")
            dash = setting[CHOICES]("solid", label="Dash", widget_config={"options": dash_choices})
            arrow_end = setting[STRING]("arrow", label="End Head", widget={"key": ARROW_HEAD_WIDGET})

        class NoteWire(WireType):
            role = WireRole.VISUAL
            style = NoteStyle
    """

    def __init__(
        self,
        registry: "SettingsRegistry | None" = None,
        edge: "EdgeWrapper | None" = None,
    ) -> None:
        super().__init__(registry=registry, node=None)
        # Back-reference to the owning edge (None for standalone/test bags).
        self._edge: "EdgeWrapper | None" = edge

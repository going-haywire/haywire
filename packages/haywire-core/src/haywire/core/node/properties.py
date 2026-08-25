# haywire/core/settings/builtins/node_instance.py
"""
NodeInstanceSettings — per-node-instance observable props.

Migrated from NodeSettings + setting() to Settings + setting().
No longer part of the Settings resolution chain.

Access via:  node.props.muted,  node.props.collapsed, ...
Serialized under the 'props' key in graph JSON.
"""

from typing import Any

from haywire.core.settings import NodeSettings, setting
from haywire.core.settings.descriptor import graph
from haywire.core.graph.properties import GraphProperties
from haywire.core.skin.settings import _layout_direction_choices, _node_skin_choices
from haywire.barn.builtin.types import BOOL, CHOICES, COLOR, FILL, INT, FLOAT, STRING


class NodeProperties(NodeSettings):
    """
    Framework-provided props available on every node instance.

    Accessed as ``node.props`` (e.g. ``self.props.muted``).
    Serialized under ``'props'`` key in the graph JSON.
    """

    REDRAW_FIELDS: tuple[str, ...] = (
        "muted",
        "collapsed",
        "condensed",
        "pinned",
        "skin",
        "layout_direction",
        "body_fill",
        "border_color",
        "border_thickness",
        "border_roundness",
        "comment",
        "show_comment",
    )
    """Fields whose change triggers a full node-card redraw.

    NodeWrapper subscribes to these after each build; layout fields
    (posX/posY/width/height/…) are deliberately absent — position changes
    ride the cheaper NODE_MOVED path and fire on every drag tick.
    """

    # -----------------------------------------------------------------
    # Visual state
    # -----------------------------------------------------------------

    muted = setting[BOOL](
        False,
        label="Muted",
        order=10,
        category="state",
        description="Mark this node as muted (execution skipping not yet implemented)",
    )
    collapsed = setting[BOOL](
        False,
        label="Collapsed",
        order=20,
        category="state",
        description="Collapse node to show only header",
    )
    condensed = setting[BOOL](
        False,
        label="Condensed",
        order=30,
        category="state",
        description="Show node in condensed view",
    )
    pinned = setting[BOOL](
        False,
        label="Pinned",
        order=40,
        category="state",
        description="Prevent auto-layout from moving this node",
    )

    # -----------------------------------------------------------------
    # Appearance
    # -----------------------------------------------------------------

    skin = graph(
        src=GraphProperties.default_skin,
        label="Skin",
        category="appearance",
        order=10,
        # Mirrors inherit IType (-> CHOICES/SELECT_WIDGET) from src, but NOT its
        # per-setting widget_config — options must be re-supplied here.
        widget_config={"options": _node_skin_choices},
    )

    layout_direction = graph(
        src=GraphProperties.layout_direction,
        label="Layout Direction",
        description="Direction flow reads across THIS node's card",
        category="appearance",
        order=15,
        widget_config={"options": _layout_direction_choices},
    )

    # These four defaults are never rendered: a field that is not *locally set*
    # means "inherit from the skin", and BaseSkin.card_style decides that on
    # `is_locally_set`, not on the value. They exist because the value still has
    # to survive the widget layer — PrimitiveUnwrappingConverter maps a None
    # model value onto the widget's own default and the browser echoes that
    # back as a genuine edit, so a None here silently writes #ffffffff into the
    # graph on the first render. The values below mirror DefaultNodeSkin so an
    # inherited field and a just-touched one look the same.
    #
    # The body is a FILL, not a colour: a solid fill is the one-stop case of the
    # same type that expresses the gradients skins already use in code. CSS is
    # generated from its fields (FILL.to_css), never assembled from user text.
    # A callable default, not a shared FILL instance: every node must get its
    # own, or resetting one node's fill would hand it an object another node
    # can mutate. `reset()` writes this default back into the cell, and
    # BaseField only accepts a real FILL — a bare None fails there.
    body_fill = setting[FILL](
        lambda: FILL(),
        label="Body Fill",
        order=20,
        category="appearance",
        description="Background fill for this node (reset to inherit the skin's)",
    )

    # Border stays a flat COLOR — a gradient border means border-image, which is
    # a different mechanism with its own rules, and the card does not need it.
    # Alpha rides inside the value as #rrggbbaa; COLOR is a string type whose
    # contract has always been "hex or rgba" (see ColorStr).
    border_color = setting[COLOR](
        "#333333ff",
        label="Border Color",
        order=30,
        category="appearance",
        description="Border color for this node (reset to inherit the skin's)",
        widget_config={"alpha": True},
    )

    # min/max are UI-only and NOT enforced on write — a hand-edited graph JSON
    # can carry any int, so the skin clamps at render (BaseSkin.card_style).
    border_thickness = setting[INT](
        3,
        label="Border Thickness",
        order=40,
        category="appearance",
        description="Border width in px (reset to inherit the skin's)",
        widget_config={"min": 0, "max": 32},
    )

    border_roundness = setting[INT](
        16,
        label="Border Roundness",
        order=50,
        category="appearance",
        description="Corner radius in px (reset to inherit the skin's)",
        widget_config={"min": 0, "max": 64},
    )

    # -----------------------------------------------------------------
    # Annotation
    # -----------------------------------------------------------------

    comment = setting[STRING](
        "",
        label="Comment",
        order=10,
        category="annotation",
        description="Comment displayed above the node",
    )
    show_comment = setting[BOOL](
        False,
        label="Show Comment",
        order=20,
        category="annotation",
        description="Display the comment bubble",
    )

    # -----------------------------------------------------------------
    # Layout (position & dimensions) — not shown in settings panels
    # -----------------------------------------------------------------

    posX = setting[FLOAT](0.0, order=10, category="layout")
    posY = setting[FLOAT](0.0, order=20, category="layout")
    # Size — a valid pair from birth (200/200 bootstrap for headless nodes).
    # size_adapt discriminates per axis: an "auto" axis is measured from render
    # (written back by the ResizeObserver in ui_node.py); a "manual" axis is
    # fixed by the user's resize gadget. Applied to the host slot as a
    # style-write — see UINode._apply_size (no card redraw). width/height stay
    # OUT of REDRAW_FIELDS.
    width = setting[INT](200, order=30, category="layout")
    height = setting[INT](200, order=40, category="layout")
    size_adapt = setting[CHOICES](
        "auto",
        widget_config={
            "options": {
                "auto": "Auto",
                "manual_width": "Manual width · auto height",
                "manual_height": "Manual height · auto width",
                "manual": "Manual (both)",
            }
        },
        label="Size Adapt",
        description="Per-axis manual control of node card size",
        order=50,
        category="layout",
    )

    # -----------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize props, flattening ``body_fill`` to a JSON-safe dict.

        ``Settings.to_dict`` stores each locally-set value as-is, which is
        right for the primitives every other setting holds. A FILL is an
        object, so it would reach ``json.dumps`` intact and raise — the graph
        would simply fail to save. Its ``to_dict`` is the JSON form, and
        ``from_dict`` below rebuilds it.
        """
        data = super().to_dict()
        fill = data.get("values", {}).get("body_fill")
        if isinstance(fill, FILL):
            data["values"] = {**data["values"], "body_fill": fill.to_dict()}
        return data

    # -----------------------------------------------------------------
    # Load migration
    # -----------------------------------------------------------------

    #: Props renamed since a released graph format, ``old name -> new name``.
    #: Applied on load only; nothing ever serializes under an old name again.
    #: Both colour spellings land on ``body_fill``, whose FILL absorbs a plain
    #: colour string as a one-stop solid (see ``FILL.__init__``).
    _RENAMED_FIELDS: dict[str, str] = {
        "color_override": "body_fill",
        "body_color": "body_fill",
    }

    def from_dict(self, data: dict) -> None:
        """Restore props, mapping any renamed field onto its current name.

        ``Settings.from_dict`` skips unknown value keys silently, so without
        this an old graph's colour would vanish rather than fail — the quiet
        kind of data loss. A key already present under its new name wins; the
        old one is dropped rather than overwriting it.

        Ordering matters when two old names map to the same new one
        (``color_override`` and ``body_color`` both became ``body_fill``): the
        later spelling wins, so a graph written between the two renames keeps
        the value the user last saw rather than a resurrected older one.
        """
        values = data.get("values")
        if isinstance(values, dict):
            migrated = dict(values)
            for old_name, new_name in self._RENAMED_FIELDS.items():
                if old_name not in migrated:
                    continue
                old_value = migrated.pop(old_name)
                if new_name not in values:
                    migrated[new_name] = self._migrate_value(new_name, old_value)
            # A FILL round-trips through JSON as a plain dict, and the restore
            # path writes into the cell without consulting the type — so it has
            # to arrive already rebuilt, whether it came from a migration above
            # or straight out of a graph saved in the current format.
            if "body_fill" in migrated:
                migrated["body_fill"] = self._migrate_value("body_fill", migrated["body_fill"])
            data = {**data, "values": migrated}
        super().from_dict(data)

    @staticmethod
    def _migrate_value(new_name: str, old_value: Any) -> Any:
        """Convert a renamed field's stored value to the new field's type.

        A rename that also changes type cannot be a key swap: the restore path
        writes straight into the cell (``_write_local``), and ``BaseField``
        rejects anything that is not already an instance of its type. Both old
        colour spellings held a plain string, so they are rebuilt as one-stop
        solid fills here.
        """
        if new_name == "body_fill" and not isinstance(old_value, FILL):
            if isinstance(old_value, dict):
                return FILL.from_dict(old_value)
            return FILL.from_css_color(str(old_value))
        return old_value

    # -----------------------------------------------------------------
    # Convenience helpers
    # -----------------------------------------------------------------

    def set_position(self, pos: tuple[float, float]) -> None:
        """Set node position as (x, y) tuple."""
        self.posX = pos[0]
        self.posY = pos[1]

    def get_position(self) -> tuple[float, float]:
        """Get node position as (x, y) tuple."""
        return (self.posX, self.posY)

"""Edge style: the fields a style bag can declare for the canvas to draw, and the dash vocabulary.

A wire type's style bag (``EdgeSettings``) may declare any fields; the canvas
draws the ones named here. Heads come from ``haywire.core.edge.arrow_heads``.
"""

#: The style fields the canvas draws, in the order a bag usually declares them.
STYLE_FIELDS: tuple[str, ...] = (
    "color",
    "width",
    "dash",
    "arrow_start",
    "arrow_start_size",
    "arrow_end",
    "arrow_end_size",
)

#: A ``dash`` field's values and the SVG dash pattern each draws, in px.
DASH_PATTERNS: dict[str, str] = {"solid": "", "dashed": "8,4", "dotted": "2,4"}


def dash_choices() -> dict[str, str]:
    """Return the ``dash`` options for a choices widget, value to label."""
    return {"solid": "Solid", "dashed": "Dashed", "dotted": "Dotted"}

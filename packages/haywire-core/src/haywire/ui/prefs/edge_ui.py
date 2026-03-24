# haywire/ui/prefs/edge_ui.py
"""Edge routing, width, and animation preference singleton."""

from haywire.core.property import Bag, prop


class EdgeUISettings(Bag):
    """Global preferences controlling edge routing, width, and animation behaviour."""

    # Width
    width: int = prop(
        2,
        label="Edge Width",
        description="Default edge width in pixels",
        category="ui.edge",
        order=10,
        min=1,
        max=8,
    )
    width_selected: int = prop(
        3,
        label="Selected Edge Width",
        description="Edge width when selected",
        category="ui.edge",
        order=11,
        min=1,
        max=10,
    )

    # Port-color tinting
    use_port_colors: bool = prop(
        True,
        label="Use Port Colors",
        description="Tint edges with the connected port type colour",
        category="ui.edge",
        order=12,
    )

    # Curve
    curve_style: str = prop(
        "bezier",
        label="Curve Style",
        description="How edges are drawn between nodes",
        category="ui.edge",
        order=20,
        choices=["bezier", "straight", "step", "smoothstep"],
    )
    curve_tension: float = prop(
        0.5,
        label="Curve Tension",
        description="Tension for bezier curves (0–1)",
        category="ui.edge",
        order=21,
        min=0.0,
        max=1.0,
    )
    curve_offset: int = prop(
        50,
        label="Curve Offset",
        description="Control point offset for curves",
        category="ui.edge",
        order=22,
        min=10,
        max=200,
    )

    # Animation
    animate_flow: bool = prop(
        False,
        label="Animate Flow",
        description="Show animated flow direction on edges",
        category="ui.edge",
        order=30,
    )
    animation_speed: float = prop(
        1.0,
        label="Animation Speed",
        description="Speed of flow animation",
        category="ui.edge",
        order=31,
        min=0.1,
        max=5.0,
    )
    animate_on_execute: bool = prop(
        True,
        label="Animate on Execute",
        description="Animate edges during execution",
        category="ui.edge",
        order=32,
    )

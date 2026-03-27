# haybale_studio/settings/ui_edge.py
"""Edge routing, width, and animation settings (colors are owned by the theme system)."""

from haywire.core.settings.schema import LibrarySettings
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings


@settings(namespace="ui.edge", label="Edge UI")
class EdgeUISettings(LibrarySettings):
    """Global settings controlling edge routing, width, and animation behaviour."""

    # Width
    width: int = setting(
        2,
        label="Edge Width",
        description="Default edge width in pixels",
        category="ui.edge",
        order=10,
        min=1,
        max=8,
    )
    width_selected: int = setting(
        3,
        label="Selected Edge Width",
        description="Edge width when selected",
        category="ui.edge",
        order=11,
        min=1,
        max=10,
    )

    # Port-color tinting
    use_port_colors: bool = setting(
        True,
        label="Use Port Colors",
        description="Tint edges with the connected port type colour",
        category="ui.edge",
        order=12,
    )

    # Curve
    curve_style: str = setting(
        "bezier",
        label="Curve Style",
        description="How edges are drawn between nodes",
        category="ui.edge",
        order=20,
        choices=["bezier", "straight", "step", "smoothstep"],
    )
    curve_tension: float = setting(
        0.5,
        label="Curve Tension",
        description="Tension for bezier curves (0–1)",
        category="ui.edge",
        order=21,
        min=0.0,
        max=1.0,
    )
    curve_offset: int = setting(
        50,
        label="Curve Offset",
        description="Control point offset for curves",
        category="ui.edge",
        order=22,
        min=10,
        max=200,
    )

    # Animation
    animate_flow: bool = setting(
        False,
        label="Animate Flow",
        description="Show animated flow direction on edges",
        category="ui.edge",
        order=30,
    )
    animation_speed: float = setting(
        1.0,
        label="Animation Speed",
        description="Speed of flow animation",
        category="ui.edge",
        order=31,
        min=0.1,
        max=5.0,
    )
    animate_on_execute: bool = setting(
        True,
        label="Animate on Execute",
        description="Animate edges during execution",
        category="ui.edge",
        order=32,
    )

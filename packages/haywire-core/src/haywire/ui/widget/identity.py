from haywire.core.registry.identity import BaseIdentity


from dataclasses import dataclass


@dataclass
class WidgetIdentity(BaseIdentity):
    """Core identifying attributes of a widget

    ``min_width``/``min_height`` declare the widget's **intrinsic box**: the size
    it claims when nothing constrains it. Declaring both opts the widget out of
    content-driven intrinsic sizing entirely (CSS size containment) — its
    contents stop voting on the node's size floor, so the node can be resized
    down to the declared box while the widget still grows to fill a larger card.
    Without them a widget sizes from its content, as every stock widget does.

    ``max_height`` overrides the framework's default expanded ceiling for the
    widget container (a definite px value; content beyond it is clipped by the
    container's ``overflow: hidden``). Independent of the intrinsic box — it
    bounds *unbounded content*, it does not declare a claimed size.
    """

    min_width: int | None = None  # Declared intrinsic width (px); pairs with min_height
    min_height: int | None = None  # Declared intrinsic height (px); pairs with min_width
    max_height: int | None = None  # Expanded-container ceiling (px); overrides the 200px default

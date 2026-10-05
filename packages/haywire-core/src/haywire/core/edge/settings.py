"""Edge defaults: the arrow head and width computed edges draw with, before a graph overrides them.

A pure ``FrameworkSettings`` schema in core, because ``GraphProperties`` (core)
shadows it and core never imports ui. The canvas reads the effective values
from ``GraphProperties``.
"""

from haywire.barn.builtin.types import FLOAT, STRING
from haywire.barn.builtin.widget_keys import ARROW_HEAD_WIDGET
from haywire.core.namespaces import CATEGORY_EDGES, NAMESPACE_UI_EDGE_DEFAULT
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


class EdgeDefaultSettings(FrameworkSettings, namespace=NAMESPACE_UI_EDGE_DEFAULT):
    """How computed edges look in the studio, before a graph overrides it.

    A computed edge is a data, control or callback edge: its colour comes from
    its pins and its dash from its adapter chain. Its arrow head and width come
    from here, and each graph may override both.
    """

    arrow = setting[STRING](
        "none",
        label="Edge Arrow",
        description="Arrow head computed edges draw, at the end their wire type names",
        category=CATEGORY_EDGES,
        widget={"key": ARROW_HEAD_WIDGET},
    )
    width = setting[FLOAT](
        2.0,
        label="Edge Width",
        description="Line width of computed edges, in pixels",
        category=CATEGORY_EDGES,
        min=0.5,
        max=12.0,
    )

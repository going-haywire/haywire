"""User-facing spacing of node arrange (see ``haywire.core.graph.arrange``)."""

from haywire.barn.builtin.types import INT
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings

from .arrange import ArrangeGaps


class ArrangeSettings(FrameworkSettings, namespace="arrange"):
    """The space Arrange leaves between node cards, for every graph.

    Read each time an arrange runs, so a change applies to the next arrange.
    """

    rank_gap = setting[INT](
        int(ArrangeGaps.rank),
        label="Node Gap",
        description="Space Arrange leaves between two connected nodes",
        min=0,
        max=1000,
    )
    cross_gap = setting[INT](
        int(ArrangeGaps.cross),
        label="Flow Gap",
        description="Space Arrange leaves between nodes in separate flows.",
        min=0,
        max=1000,
    )
    band_gap = setting[INT](
        int(ArrangeGaps.band),
        label="Band Gap",
        description="Space Arrange All leaves between two unconnected flows.",
        min=0,
        max=1000,
    )

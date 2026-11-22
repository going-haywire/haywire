"""FlowMeterSettings — whether the haystack rows of running graphs show flow meters."""

from __future__ import annotations

from haywire.api import BOOL, LibrarySettings, setting, settings


@settings(namespace="flow_meters", label="Flow meters", description="Meters on the rows of running graphs")
class FlowMeterSettings(LibrarySettings):
    """Whether a running graph's row shows how well its flows keep up."""

    show = setting[BOOL](
        True,
        label="Show flow meters",
        description=(
            "Show how well each running graph's flows keep up, as bars on its row. "
            "Applies the next time a graph is started or stopped."
        ),
        category="Flow meters",
    )

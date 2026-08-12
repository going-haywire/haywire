# haywire/core/settings/settings_graph.py
"""
GraphSettings — base class for graph-owned settings bags.

The fourth Settings flavour, parallel to NodeSettings:

- Per-instance DataField cells; never registered with SettingsRegistry.
- Owned by a BaseGraph (``graph.props``), serialized into the graph JSON
  (restored BEFORE nodes on load, so node-bag graph mirrors seed correctly).
- Carries a ``_graph`` backref instead of a node backref. ``_node`` stays
  None, which keeps every node-only surface — promotion, the setting-row
  menu's promote entries — structurally disabled.
- Fields may ``shadow()`` framework/library settings exactly like node
  bags; node-bag fields may in turn declare ``graph(src=<field here>)``
  (a graph mirror), giving the framework < graph < node resolution chain.
"""

from typing import TYPE_CHECKING

from typing_extensions import dataclass_transform

from .descriptor import setting, shadow
from .settings import Settings

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.settings.registry import SettingsRegistry


@dataclass_transform(field_specifiers=(setting, shadow))
class GraphSettings(Settings):
    """Base class for graph-local settings bags.

    Instantiated by ``BaseGraph`` with the DI registry; never registered
    with SettingsRegistry as a class. A graph has no ports, so promotion
    is structurally unavailable (``_node`` is always None).
    """

    def __init__(
        self,
        registry: "SettingsRegistry | None" = None,
        graph: "BaseGraph | None" = None,
    ) -> None:
        super().__init__(registry=registry, node=None)
        # Back-reference to the owning graph (None for standalone/test
        # bags). The graph-side analogue of Settings._node.
        self._graph: "BaseGraph | None" = graph

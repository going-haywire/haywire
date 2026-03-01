# packages/haywire-framework/src/haywire/ui/panels/builtins.py
"""
Bootstrap function for registering built-in framework panels.

Called from the DI provider in HaywireModule to register framework-provided
panels into the PanelRegistry.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.ui.panel.registry import PanelRegistry


def register_builtin_panels(registry: 'PanelRegistry') -> None:
    """Register all built-in framework panels into the registry.

    Args:
        registry: The PanelRegistry DI singleton to register into.
    """
    from haywire.ui.panels.node_properties_panel import NodePropertiesPanel
    from haywire.ui.panels.node_ports_panel import NodePortsPanel
    from haywire.ui.panels.node_settings_panel import NodeSettingsPanel
    from haywire.ui.panels.graph_info_panel import GraphInfoPanel
    from haywire.ui.panels.edge_info_panel import EdgeInfoPanel
    for cls in [NodePropertiesPanel, NodePortsPanel, NodeSettingsPanel,
                GraphInfoPanel, EdgeInfoPanel]:
        registry._register_class(cls, library_identity=None)

# barn/haybale-studio/haybale_studio/editors/scopes.py
"""
Built-in scope descriptors for the PropertiesEditor.

These define the left-hand icon tabs in the PropertiesEditor. They are
registered into PanelRegistry from haybale_studio's register_components()
before the panels folder is scanned.

Scope hierarchy (top to bottom in the toolbar):
    app        — application-wide settings (always available)
    execution  — execution behaviour settings (always available)
    canvas     — canvas and node visual settings (always available)
    debug      — debug and development tools (always available)
    graph      — active graph info (requires active_graph)
    node       — selected node properties (requires active_node)
    edge       — selected edge info (requires active_edge)

The app/execution/canvas/debug scopes are registered now so the toolbar
tabs appear; the panels that populate them are added in a later phase once
the settings rendering strategy is decided.
"""

from haywire.ui.panel.scope import ScopeDescriptor

PROPERTIES_SCOPES: list[ScopeDescriptor] = [
    ScopeDescriptor(
        scope_id='app',
        label='Application',
        icon='settings',
        order=10,
        poll=lambda ctx: True,
    ),
    ScopeDescriptor(
        scope_id='execution',
        label='Execution',
        icon='play_circle',
        order=20,
        poll=lambda ctx: True,
    ),
    ScopeDescriptor(
        scope_id='canvas',
        label='Canvas & Nodes',
        icon='grid_on',
        order=30,
        poll=lambda ctx: True,
    ),
    ScopeDescriptor(
        scope_id='debug',
        label='Debug',
        icon='bug_report',
        order=40,
        poll=lambda ctx: True,
    ),
    ScopeDescriptor(
        scope_id='graph',
        label='Graph',
        icon='account_tree',
        order=50,
        poll=lambda ctx: ctx.active_graph is not None,
    ),
    ScopeDescriptor(
        scope_id='node',
        label='Node',
        icon='widgets',
        order=60,
        poll=lambda ctx: ctx.active_node is not None,
    ),
    ScopeDescriptor(
        scope_id='edge',
        label='Edge',
        icon='cable',
        order=70,
        poll=lambda ctx: ctx.active_edge is not None,
    ),
]

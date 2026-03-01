# packages/haywire-framework/src/haywire/ui/editors/properties_editor.py
"""
PropertiesEditor — context-sensitive properties sidebar.

Displays panels registered to the 'properties' editor, filtered by the
current selection context (node / edge / graph). No hardcoded content —
everything comes from the PanelRegistry.
"""

import logging
from typing import TYPE_CHECKING, List

from nicegui import ui

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.context_events import ContextChangeType
from haywire.ui.panel.base import PanelLayout

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent


@editor(
    registry_id='properties',
    label='Properties',
    icon='tune',
    default_area='right',
    description='Context-sensitive property panels for the active selection.',
)
class PropertiesEditor(BaseEditor):
    """
    Displays panels registered to the 'properties' editor.

    This editor has NO hardcoded content. It queries the PanelRegistry
    for all panels with editor_key='properties', filters by the current
    context (based on what's selected), runs poll() on each, and renders
    those that return True.

    Context determination:
        - active_node set  → context = 'node'
        - active_edge set  → context = 'edge'
        - active_graph set but nothing else → context = 'graph'
        Multiple contexts can be active (shows panels from all matching).

    Expects 'panel_registry' in context.metadata (set by app.py startup).
    """

    def __init__(self):
        self._container = None
        self._panel_registry = None

    def render(self, container, context: 'SessionContext') -> None:
        """Build the properties panel UI."""
        self._container = container
        self._panel_registry = context.metadata.get('panel_registry')
        self._rebuild_panels(context)

    def on_context_changed(self, event: 'ContextChangedEvent', context: 'SessionContext') -> None:
        """Rebuild panels on any relevant context change."""
        relevant = {
            ContextChangeType.SELECTION_CHANGED,
            ContextChangeType.ACTIVE_GRAPH_CHANGED,
            ContextChangeType.DATA_MUTATED,
        }
        if event.change_type in relevant and self._container is not None:
            self._container.clear()
            self._rebuild_panels(context)

    def _rebuild_panels(self, context: 'SessionContext') -> None:
        """Query PanelRegistry and render all passing panels."""
        if self._container is None:
            return

        with self._container:
            active_contexts = self._resolve_contexts(context)

            if not active_contexts:
                with ui.column().classes('w-full items-center justify-center p-4'):
                    ui.icon('select_all').classes('text-gray-500 text-3xl')
                    ui.label('Nothing selected').classes('text-gray-500 text-sm')
                return

            has_panels = False
            for ctx_name in active_contexts:
                panel_classes = self._get_panels_for_context(ctx_name)
                for panel_cls in panel_classes:
                    try:
                        if not panel_cls.poll(context):
                            continue
                    except Exception as e:
                        logging.warning(f"PropertiesEditor: poll() error for {panel_cls.__name__}: {e}")
                        continue

                    has_panels = True
                    default_open = getattr(panel_cls.class_identity, 'default_open', True)
                    icon = getattr(panel_cls.class_identity, 'icon', None)

                    with ui.expansion(
                        panel_cls.class_identity.label,
                        icon=icon,
                        value=default_open,
                    ).classes('w-full'):
                        panel_container = ui.column().classes('w-full gap-1 p-1')
                        layout = PanelLayout(panel_container)
                        try:
                            panel_instance = panel_cls()
                            panel_instance.draw(context, layout)
                        except Exception as e:
                            logging.error(
                                f"PropertiesEditor: draw() error for {panel_cls.__name__}: {e}"
                            )
                            ui.label(f"Error: {e}").classes('text-red-400 text-xs')

            if not has_panels:
                with ui.column().classes('w-full items-center justify-center p-4'):
                    ui.icon('info').classes('text-gray-500 text-3xl')
                    ui.label('No properties available').classes('text-gray-500 text-sm')

    def _resolve_contexts(self, context: 'SessionContext') -> List[str]:
        """Determine active context names based on selection state."""
        contexts = []
        if context.active_node is not None:
            contexts.append('node')
        if context.active_edge is not None:
            contexts.append('edge')
        if context.active_graph is not None and not contexts:
            contexts.append('graph')
        return contexts

    def _get_panels_for_context(self, ctx_name: str) -> List[type]:
        """Get panels from registry, falling back to empty list if none."""
        if self._panel_registry is None:
            return []
        try:
            editor_key = self.class_identity.registry_id
            return self._panel_registry.get_panels(editor_key, ctx_name)
        except Exception as e:
            logging.warning(f"PropertiesEditor: registry lookup error: {e}")
            return []

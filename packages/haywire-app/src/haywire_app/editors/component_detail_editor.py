# packages/haywire-app/src/haywire_app/editors/component_detail_editor.py
"""
ComponentDetailEditor — shows detail info for the selected node component.

Renders in the right area and reacts to ACTIVE_COMPONENT_CHANGED events.
"""

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor
from haywire.ui.context_events import ContextChangeType

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent


@editor(
    registry_id='component_detail',
    label='Component Detail',
    icon='description',
    default_area='right',
    description='Detailed documentation for the selected node component.',
)
class ComponentDetailEditor(BaseEditor):
    """
    Displays documentation and port information for the active component.
    Rebuilds on ACTIVE_COMPONENT_CHANGED context events.
    """

    def __init__(self):
        self._container = None

    def render(self, container, context: 'SessionContext') -> None:
        self._container = container
        self._rebuild(context)

    def on_context_changed(self, event: 'ContextChangedEvent', context: 'SessionContext') -> None:
        if event.change_type == ContextChangeType.ACTIVE_COMPONENT_CHANGED and self._container is not None:
            self._container.clear()
            self._rebuild(context)

    _COMP_ICONS = {
        'nodes': 'account_tree',
        'widgets': 'widgets',
        'types': 'category',
        'adapters': 'swap_horiz',
        'renderers': 'brush',
    }

    def _rebuild(self, context: 'SessionContext') -> None:
        if self._container is None:
            return
        component_info = context.active_component
        with self._container:
            if not component_info:
                with ui.column().classes('w-full h-full items-center justify-center gap-2'):
                    ui.icon('widgets').classes('text-gray-400 text-4xl')
                    ui.label('Select a component to see details').classes('text-gray-400 text-sm')
                return

            lib = component_info.get('lib')
            class_name = component_info.get('class_name', '')
            comp_type = component_info.get('comp_type', 'nodes')

            app = context.metadata.get('project_state')
            cls = self._lookup_class(app, lib, class_name, comp_type)
            identity = getattr(cls, 'class_identity', None) if cls else None

            label = getattr(identity, 'label', None) or class_name or '?'
            registry_id = getattr(identity, 'registry_id', None) or ''
            description = getattr(identity, 'description', None) or ''
            tags = getattr(identity, 'tags', []) or []
            icon = self._COMP_ICONS.get(comp_type, 'extension')

            with ui.scroll_area().classes('w-full').style('height: 100%;'):
                with ui.column().classes('w-full gap-3 p-4'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon(icon).classes('text-purple-500 text-2xl')
                        ui.label(label).classes('text-lg font-bold')

                    ui.label(comp_type.removesuffix('s').title()).classes(
                        'text-xs text-gray-400 uppercase tracking-wider'
                    )

                    if registry_id:
                        ui.label(registry_id).classes('text-xs text-gray-300 font-mono')

                    if description:
                        ui.label(description).classes('text-sm text-gray-600')

                    if tags:
                        with ui.row().classes('flex-wrap gap-1'):
                            for tag in tags:
                                ui.badge(tag).props('color=purple outline')

                    if lib:
                        ui.separator()
                        lib_label = getattr(lib, 'label', None) or getattr(lib, 'library_id', '?')
                        ui.label(f'Library: {lib_label}').classes('text-xs text-gray-500')

    @staticmethod
    def _lookup_class(app, lib, class_name: str, comp_type: str):
        """Look up the component class from the appropriate registry."""
        lib_id = getattr(lib, 'library_id', None)
        if not lib_id or not app:
            return None
        comp_singular = comp_type.removesuffix('s')
        key = f'{lib_id}:{comp_singular}:{class_name}'
        try:
            if comp_type == 'nodes':
                reg = getattr(app, 'node_registry', None)
            elif hasattr(app, 'library_service'):
                reg = {
                    'widgets': app.library_service.get_widget_registry,
                    'types': app.library_service.get_type_registry,
                    'adapters': app.library_service.get_adapter_registry,
                    'renderers': app.library_service.get_renderer_registry,
                }.get(comp_type, lambda: None)()
            else:
                return None
            return reg.get(key) if reg else None
        except Exception:
            return None

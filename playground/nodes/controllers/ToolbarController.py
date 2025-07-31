"""
Controller for graph toolbar operations
"""

from typing import TYPE_CHECKING
from nicegui import ui

if TYPE_CHECKING:
    from utils.Graph import GraphManager
    from utils.NodeCanvas import NodeCanvas


class ToolbarController:
    """Handles toolbar UI and operations"""
    
    def __init__(self, graph_manager: 'GraphManager', node_graph: 'NodeCanvas'):
        self.graph_manager = graph_manager
        self.node_graph = node_graph
    
    def render_toolbar(self):
        """Render the toolbar UI"""
        with ui.row().classes('w-full justify-between items-center q-pa-sm'):
            with ui.row():
                ui.button('Fit to Screen', icon='fit_screen', 
                         on_click=self._fit_to_screen).props('outline')
                ui.button('Center Graph', icon='center_focus_strong',
                         on_click=self._center_graph).props('outline')
                ui.button('Execute', icon='play_arrow',
                         on_click=self._execute_graph).props('color=green')
            
            with ui.row():
                ui.label('Zoom: 100%').classes('text-caption')
                ui.button('Reset View', icon='refresh',
                         on_click=self._reset_view).props('flat')
    
    def _fit_to_screen(self):
        """Fit all nodes to the screen"""
        # This would implement actual fit-to-screen logic
        self.graph_manager.notification_service.notify("Fit to screen not implemented yet")
    
    def _center_graph(self):
        """Center the graph view"""
        # This would implement actual centering logic
        self.graph_manager.notification_service.notify("Center graph not implemented yet")
    
    def _execute_graph(self):
        """Execute the graph"""
        self.graph_manager.execute_graph()
    
    def _reset_view(self):
        """Reset the view to default zoom and position"""
        # This would implement actual view reset logic
        self.graph_manager.notification_service.notify("Reset view not implemented yet")

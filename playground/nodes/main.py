#!/usr/bin/env python3
"""
Simple Node Graph Editor built with NiceGUI and Quasar
"""
from nicegui import ui

from utils.NodeCanvas import NodeCanvas
from utils.Graph import GraphManager

try:
    from services.nicegui_notification_service import NiceGUINotificationService
    NICEGUI_AVAILABLE = True
except ImportError:
    from services.nicegui_notification_service import ConsoleNotificationService
    NICEGUI_AVAILABLE = False

def main():
    """Main application entry point"""
    
    # Add custom CSS and JavaScript for enhanced functionality
    ui.add_head_html('''
        <style>
            .draggable-node {
                transition: none !important;
            }
            .draggable-node:active {
                cursor: grabbing !important;
                z-index: 1000 !important;
            }
            .draggable-node.dragging {
                box-shadow: 0 8px 16px rgba(0,0,0,0.3) !important;
                transform: rotate(2deg);
            }
        </style>

    ''')
    
    # Initialize the notification service and graph manager
    if NICEGUI_AVAILABLE:
        notification_service = NiceGUINotificationService()
    else:
        notification_service = ConsoleNotificationService()
    
    graph_manager = GraphManager(notification_service)
    
    # Add API endpoint for position updates
    
     
    # Create the main layout
    with ui.header(elevated=True).style('background-color: #1976d2'):
        ui.label('Node Graph Editor').style('font-size: 1.5rem; font-weight: bold; color: white')
        ui.space()
        with ui.row():
            ui.button('New Graph', icon='add', on_click=lambda: graph_manager.clear_graph()).props('flat color=white')
            ui.button('Save Graph', icon='save', on_click=lambda: graph_manager.save_graph()).props('flat color=white')
            ui.button('Load Graph', icon='folder_open', on_click=lambda: graph_manager.load_graph()).props('flat color=white')
    
    # Create the main container
    with ui.splitter(value=20).classes('w-full h-screen') as splitter:
        # Left panel - Node palette
        with splitter.before:
            with ui.card().tight().classes('h-full'):
                ui.label('Node Palette').classes('text-h6 q-pa-md')
                ui.separator()
                
                # Node categories
                with ui.expansion('Basic Nodes', icon='category').classes('w-full'):
                    create_node_palette_section(graph_manager, 'basic')
                
                with ui.expansion('Math Nodes', icon='calculate').classes('w-full'):
                    create_node_palette_section(graph_manager, 'math')
                
                with ui.expansion('Logic Nodes', icon='psychology').classes('w-full'):
                    create_node_palette_section(graph_manager, 'logic')
                
                with ui.expansion('Output Nodes', icon='output').classes('w-full'):
                    create_node_palette_section(graph_manager, 'output')
        
        # Right panel - Node graph canvas
        with splitter.after:
            node_graph = NodeCanvas(graph_manager)
            node_graph.render()
    
    # Add keyboard controls for selected nodes (simplified)
    def handle_keyboard(e):
        """Handle keyboard events for moving selected nodes"""
        if graph_manager.selected_nodes:
            step = 10  # pixels to move
            for node_id in graph_manager.selected_nodes:
                node = graph_manager.nodes.get(node_id)
                if node:
                    if e.key.name == 'ARROW_UP':
                        graph_manager.move_node(node_id, node.x, max(0, node.y - step))
                    elif e.key.name == 'ARROW_DOWN':
                        graph_manager.move_node(node_id, node.x, node.y + step)
                    elif e.key.name == 'ARROW_LEFT':
                        graph_manager.move_node(node_id, max(0, node.x - step), node.y)
                    elif e.key.name == 'ARROW_RIGHT':
                        graph_manager.move_node(node_id, node.x + step, node.y)
    
    # Try to add global keyboard handler (may not work in all NiceGUI versions)
    try:
        ui.keyboard(handle_keyboard, active=True)
    except Exception as e:
        print(f"Keyboard handler not available: {e}")
    
    # Bottom status bar
    with ui.footer().style('background-color: #f5f5f5; border-top: 1px solid #ddd'):
        with ui.row().classes('w-full justify-between items-center q-pa-sm'):
            ui.label('Ready').bind_text_from(graph_manager, 'status_message')
            ui.label().bind_text_from(graph_manager, 'node_count', 
                                      backward=lambda count: f'Nodes: {count}')

def create_node_palette_section(graph_manager: GraphManager, category: str):
    """Create a section of the node palette for a specific category"""
    
    node_types = {
        'basic': [
            ('Input', 'input', 'keyboard'),
            ('Output', 'output', 'output'),
            ('Comment', 'comment', 'comment'),
        ],
        'math': [
            ('Add', 'add', 'add'),
            ('Subtract', 'subtract', 'remove'),
            ('Multiply', 'multiply', 'close'),
            ('Divide', 'divide', 'horizontal_rule'),
        ],
        'logic': [
            ('AND', 'and', 'logic'),
            ('OR', 'or', 'logic'),
            ('NOT', 'not', 'not_interested'),
            ('Compare', 'compare', 'compare_arrows'),
        ],
        'output': [
            ('Display', 'display', 'monitor'),
            ('Chart', 'chart', 'bar_chart'),
            ('Export', 'export', 'file_download'),
        ]
    }
    
    if category in node_types:
        for name, node_type, icon in node_types[category]:
            ui.button(
                name, 
                icon=icon, 
                on_click=lambda t=node_type, n=name: graph_manager.add_node_from_palette(t, n)
            ).props('flat full-width align=left').classes('q-ma-xs')

if __name__ in {'__main__', '__mp_main__'}:
    main()
    ui.run(
        title='Node Graph Editor',
        favicon='🔗',
        dark=False,
        show=True,
        reload=True,
        port=8080
    )

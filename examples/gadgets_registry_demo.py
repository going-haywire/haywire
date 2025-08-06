"""
Gadgets Registry Demo - Demonstrating the new node rendering architecture

This example shows how to use the new gadgets registry system with:
1. Setting up gadgets registry with default and error renderers
2. Creating NodeRenderFactory with both registries
3. Using UINode for reliable rendering and re-rendering
4. Custom renderer registration and usage
"""

from nicegui import ui
from haywire.core.node.node import NodeData
from haywire.core.data.fields import SingleField
from haywire.core.data.enums import CouplingType, DataType, FlowType
from haywire.core.node.elements import Config, Inlet, Outlet
from haywire.core.registry.registry import WidgetRegistry
from haywire.libraries.core.widgets import register_core_widgets

# Import the new gadgets architecture
from haywire.ui.gadgets_registry import GadgetsRegistry, BaseNodeRenderer, UINodeCard
from haywire.ui.node_render_factory import NodeRenderFactory
from haywire.ui.ui_node import UINode
from haywire.ui.default_node_renderer import DefaultNodeRenderer, ErrorNodeRenderer


class CustomMathNodeRenderer(BaseNodeRenderer):
    """Custom renderer for math nodes with special styling."""
    
    def render(self, node: NodeData) -> UINodeCard:
        """Render a math node with custom styling."""
        ui_elements = {}
        widget_instances = {}
        
        node_id = f"math-node-{id(node)}"
        
        # Custom math-themed CSS
        ui.add_head_html(f'''
        <style>
        .{node_id} {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 16px;
            border: 3px solid #4f46e5;
        }}
        .{node_id} .text-h6 {{
            color: #fbbf24;
            font-weight: bold;
        }}
        .{node_id} .widget-container {{
            opacity: 0;
            transition: all 0.4s ease;
            transform: scale(0.95);
        }}
        .{node_id}:hover .widget-container,
        .{node_id}:focus-within .widget-container {{
            opacity: 1;
            transform: scale(1);
        }}
        </style>
        ''')
        
        with ui.card().classes(f'w-full min-w-64 max-w-sm math-node-card {node_id}') as main_card:
            # Math-themed header
            with ui.row().classes('w-full items-center gap-2'):
                ui.icon('calculate', color='yellow').classes('text-lg')
                ui.label("Math Node").classes('text-h6 flex-1')
            
            # Render configs
            if node.configs:
                ui.label('Configuration').classes('font-bold text-sm mt-2')
                for config in node.configs.values():
                    with ui.column().classes('flex-1 gap-1 w-full'):
                        ui.label(config.label).classes('text-xs')
                        self._render_element(config, ui_elements, widget_instances)
            
            # Render inlets and outlets
            with ui.row().classes('w-full gap-2'):
                # Inlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.inlets:
                        ui.label('Inputs').classes('font-bold text-sm')
                        for inlet in node.inlets.values():
                            with ui.row().classes('w-full items-center gap-1'):
                                ui.label(inlet.label).classes('text-xs')
                                if hasattr(inlet, 'coupling_type') and inlet.coupling_type != 'none':
                                    self._render_element(inlet, ui_elements, widget_instances)
                
                # Outlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.outlets:
                        ui.label('Outputs').classes('font-bold text-sm')
                        for outlet in node.outlets.values():
                            ui.label(outlet.label).classes('text-xs text-right')
        
        return UINodeCard(main_card, ui_elements, widget_instances)
    
    def _render_element(self, element, ui_elements, widget_instances):
        """Render element using widget registry."""
        if not element.data or element.widget == 'None':
            return
        
        try:
            widget_class = self.widget_registry.get_widget_class(element.widget, element.data)
            widget_instance = widget_class(element)
            ui_element = widget_instance.render()
            
            if hasattr(ui_element, 'classes'):
                ui_element.classes('widget-container')
            
            ui_elements[element.id] = ui_element
            widget_instances[element.id] = widget_instance
            
        except Exception as e:
            with ui.column().classes('w-full p-2 border border-red-300 bg-red-100 widget-container') as error_widget:
                ui.label(f"Widget Error: {str(e)}").classes('text-red-700 text-sm')
            ui_elements[element.id] = error_widget
            widget_instances[element.id] = None


def setup_gadgets_system():
    """Set up the complete gadgets registry system."""
    
    # 1. Set up widget registry
    widget_registry = WidgetRegistry()
    register_core_widgets(widget_registry)
    
    # 2. Set up gadgets registry
    gadgets_registry = GadgetsRegistry()
    
    # Register default and error renderers
    gadgets_registry.register_renderer("default", DefaultNodeRenderer)
    gadgets_registry.register_renderer("error", ErrorNodeRenderer)
    gadgets_registry.register_renderer("math", CustomMathNodeRenderer)
    
    # Set fallback renderers
    gadgets_registry.register_default_renderer("default")
    gadgets_registry.register_error_renderer("error")
    
    # 3. Create factory with both registries
    factory = NodeRenderFactory(gadgets_registry, widget_registry)
    
    return factory, gadgets_registry, widget_registry


def create_demo_nodes():
    """Create demo nodes for testing."""
    
    # Standard node
    standard_node = NodeData()
    standard_node.inlets = {
        'input': Inlet(
            'input', 
            'Input Value', 
            CouplingType.ONE, 
            data=SingleField('input', DataType.FLOAT, 'scalar', 5.0, False), 
            widget='slider')
    }
    standard_node.outlets = {
        'output': Outlet(
            'output', 
            FlowType.DATA, 
            label='Output', 
            data=SingleField('output', DataType.FLOAT, 'scalar', None, False))
    }
    standard_node.configs = {
        'multiplier': Config(
            'multiplier', 
            callback=None,
            data=SingleField('multiplier', DataType.FLOAT, 'scalar', 2.0, False), 
            widget='knob')
    }
    
    # Math node
    math_node = NodeData()
    math_node.inlets = {
        'a': Inlet(
            'a', 
            'Value A', 
            CouplingType.ONE, 
            data=SingleField('a', DataType.FLOAT, 'scalar', 10.0, False), 
            widget='number'),
        'b': Inlet(
            'b', 
            'Value B', 
            CouplingType.ONE, 
            data=SingleField('b', DataType.FLOAT, 'scalar', 5.0, False), 
            widget='number')
    }
    math_node.outlets = {
        'result': Outlet(
            'result', 
            FlowType.DATA, 
            label='Result', 
            data=SingleField('result', DataType.FLOAT, 'scalar', None, False))
    }
    math_node.configs = {
        'operation': Config(
            'operation', 
            callback=None,
            data=SingleField('operation', DataType.STRING, 'scalar', 'add', False), 
            widget='select')
    }
    
    return standard_node, math_node


def main():
    """Main demo application."""
    
    # Set up the gadgets system
    factory, gadgets_registry, widget_registry = setup_gadgets_system()
    
    # Create demo nodes
    standard_node, math_node = create_demo_nodes()
    
    # Store UINode instances
    ui_nodes = {}
    
    @ui.page('/')
    def index_page():
        ui.label('Gadgets Registry Demo - New Node Rendering Architecture').classes('text-h4 mb-4')
        
        ui.label('This demo shows the new gadgets registry system:').classes('text-lg mb-2')
        ui.html('''
        <ul class="list-disc ml-6 mb-4">
            <li><strong>Gadgets Registry</strong> - Manages NodeRenderer classes with fallback</li>
            <li><strong>NodeRenderFactory</strong> - Caches stateless renderers and creates UINodeCard</li>
            <li><strong>UINode</strong> - Manages UI lifecycle with reliable cleanup</li>
            <li><strong>Container-Slot Approach</strong> - Reliable re-rendering without memory leaks</li>
        </ul>
        ''')
        
        with ui.row().classes('w-full gap-4'):
            # Column 1: Standard Node (Default Renderer)
            with ui.column().classes('flex-1') as col1:
                ui.label('Standard Node (Default Renderer)').classes('text-h6 mb-2')
                
                # Create UINode with container-slot approach
                ui_nodes['standard'] = UINode(standard_node, factory, col1)
                ui_nodes['standard'].render()  # Uses default renderer
                
                # Controls
                with ui.card().classes('mt-4 p-4'):
                    ui.label('Controls').classes('font-bold mb-2')
                    
                    async def rerender_standard():
                        ui_nodes['standard'].rerender()  # Re-render with default
                        ui.notify('Standard node re-rendered')
                    
                    async def update_standard():
                        success = ui_nodes['standard'].update_element_value('input', 15.0)
                        ui.notify(f'Update: {"Success" if success else "Failed"}')
                    
                    ui.button('Re-render', on_click=rerender_standard)
                    ui.button('Set Input to 15.0', on_click=update_standard)
            
            # Column 2: Math Node (Custom Renderer)
            with ui.column().classes('flex-1') as col2:
                ui.label('Math Node (Custom Renderer)').classes('text-h6 mb-2')
                
                # Create UINode with custom renderer
                ui_nodes['math'] = UINode(math_node, factory, col2)
                ui_nodes['math'].render('math')  # Uses custom math renderer
                
                # Controls
                with ui.card().classes('mt-4 p-4'):
                    ui.label('Controls').classes('font-bold mb-2')
                    
                    async def rerender_math_default():
                        ui_nodes['math'].rerender()  # Re-render with default
                        ui.notify('Math node re-rendered with default renderer')
                    
                    async def rerender_math_custom():
                        ui_nodes['math'].rerender('math')  # Re-render with custom
                        ui.notify('Math node re-rendered with custom renderer')
                    
                    async def test_error_renderer():
                        ui_nodes['math'].rerender('nonexistent')  # Should use error renderer
                        ui.notify('Math node rendered with error renderer (fallback)')
                    
                    ui.button('Render as Default', on_click=rerender_math_default)
                    ui.button('Render as Math', on_click=rerender_math_custom)
                    ui.button('Test Error Fallback', on_click=test_error_renderer)
        
        # System Information
        with ui.expansion('System Information', icon='info').classes('w-full mt-6'):
            ui.html(f'''
            <div class="p-4">
                <h3 class="text-lg font-bold mb-2">Registered Renderers:</h3>
                <ul class="list-disc ml-6 mb-4">
                    <li><strong>default</strong>: {DefaultNodeRenderer.__name__}</li>
                    <li><strong>error</strong>: {ErrorNodeRenderer.__name__}</li>
                    <li><strong>math</strong>: {CustomMathNodeRenderer.__name__}</li>
                </ul>
                
                <h3 class="text-lg font-bold mb-2">Fallback Strategy:</h3>
                <ol class="list-decimal ml-6 mb-4">
                    <li>Use default if no renderer name specified</li>
                    <li>Try exact renderer name lookup</li>
                    <li>Return error renderer if exact renderer doesn't exist</li>
                </ol>
                
                <h3 class="text-lg font-bold mb-2">Architecture Benefits:</h3>
                <ul class="list-disc ml-6">
                    <li>Stateless renderers cached for performance</li>
                    <li>Reliable cleanup via container-slot approach</li>
                    <li>Clean separation: UINode delegates to factory</li>
                    <li>Registry-based extensibility</li>
                </ul>
            </div>
            ''')

    # Run the application
    ui.run(port=8080, show=True, title="Gadgets Registry Demo")


if __name__ in {"__main__", "__mp_main__"}:
    main()

"""
ConnectionInfoPopup - Detailed connection information display component

This component provides a dedicated popup for inspecting edge/connection details including:
- Connection path (nodes and ports)
- Validation status
- Error details with full error rendering
- Warning messages
- Adapter chain visualization and testing
- Execution statistics
"""

from nicegui import ui
from typing import Optional

from haywire.core.graph.edge import Edge
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.graph.edge_wrapper import EdgeWrapperState

from .popup import Popup
from haywire.ui.errors.error_info import error_render_detail


class ConnectionInfoPopup:
    """Dedicated popup for displaying detailed connection/edge information."""
    
    def __init__(self):
        self._info_popup: Optional[Popup] = None
    
    def show(
        self,
        x: float,
        y: float,
        connection_id: str,
        edge: Edge,
        state: EdgeWrapperState
    ):
        """Show detailed connection information in a dedicated popup."""
        # Close any existing popup first
        self.close()
        
        # Create a larger popup for detailed information
        popup = Popup.create_context_menu(
            "Connection Details",
            x + 10,
            y + 10,
            width='400px'
        )
        
        with popup:
            with ui.column().classes('w-full gap-2 p-2'):
                # Header with connection status
                with ui.row().classes('w-full items-center justify-between'):
                    ui.label("Connection Information").classes(
                        'text-lg font-bold text-gray-800'
                    )
                    is_valid = state.is_valid
                    status_icon = '✓' if is_valid else '✗'
                    status_color = 'text-green-600' if is_valid else 'text-red-600'
                    status_text = 'Valid' if is_valid else 'Invalid'
                    ui.label(f"{status_icon} {status_text}").classes(
                        f'text-sm font-bold {status_color}'
                    )
                
                ui.separator().classes('my-2')
                                
                # Error Section (if present, expandable, default open)
                error = state.error_main
                if error and isinstance(error, HaywireException):
                    with ui.expansion('Error Details', value=True).classes('w-full'):
                        with ui.card().classes(
                            'w-full p-3 bg-red-50 border border-red-200'
                        ):
                            ui.label(f"Category: {error.category}").classes(
                                'text-xs text-red-600 ml-2'
                            )
                            # Render the error detail with button to show full details
                            error_render_detail(error)
                
                # Warning Section (if present, expandable, default open)
                warning = state.warning_main
                if warning:
                    with ui.expansion('Warning', value=True).classes('w-full'):
                        with ui.card().classes(
                            'w-full p-3 bg-orange-50 border border-orange-200'
                        ):
                            ui.label(f"⚠ {warning}").classes(
                                'text-xs text-orange-600 ml-2'
                            )
                
                # Adapter Chain Section (if available, expandable, default closed)
                if edge.chain_adapter_keys:
                    with ui.expansion('Adapter Chain', value=False).classes('w-full'):
                        with ui.card().classes(
                            'w-full p-3 bg-blue-50 border border-blue-200'
                        ):
                            # Display each adapter in the chain
                            for i, adapter_key in enumerate(edge.chain_adapter_keys, 1):
                                ui.label(f"{i}. {adapter_key}").classes(
                                    'text-xs text-blue-600 ml-2'
                                )
                            
                            # Test adapter chain button
                            ui.separator().classes('my-2')
                            btn_test = ui.button(
                                '▶️ Test Adapter Chain',
                                on_click=lambda e=edge: self._test_adapter_chain(e)
                            )
                            btn_test.props('flat')
                            btn_test.classes(
                                'w-full bg-blue-100 text-blue-700 '
                                'hover:bg-blue-200 text-sm py-2'
                            )
                
                # Execution Statistics Section (expandable, default closed)
                with ui.expansion('Execution Statistics', value=False).classes('w-full'):
                    with ui.card().classes('w-full p-3 bg-gray-50'):
                        exec_count = state.execution_count
                        ui.label(f"Execution Count: {exec_count}").classes(
                            'text-xs text-gray-700 ml-2'
                        )
                        
                        avg_time = state.average_execution_time_ms
                        if avg_time > 0:
                            ui.label(f"Average Time: {avg_time:.2f} ms").classes(
                                'text-xs text-gray-700 ml-2'
                            )
                        else:
                            ui.label("Average Time: Not measured").classes(
                                'text-xs text-gray-500 ml-2'
                            )

                # Connection Path Section (Expandable, default open)
                with ui.expansion('Connection Path', value=False).classes('w-full'):
                    with ui.card().classes('w-full p-3 bg-gray-50'):
                        ui.label(f"From: {edge.output_node_id}").classes(
                            'text-xs text-gray-700 ml-2'
                        )
                        ui.label(f"Port: {edge.outlet_port_id}").classes(
                            'text-xs text-gray-500 ml-4'
                        )
                        ui.label(f"To: {edge.input_node_id}").classes(
                            'text-xs text-gray-700 ml-2 mt-1'
                        )
                        ui.label(f"Port: {edge.inlet_port_id}").classes(
                            'text-xs text-gray-500 ml-4'
                        )
                        ui.label(f"Type: {edge.edge_type}").classes(
                            'text-xs text-gray-700 ml-2 mt-2'
                        )
                        ui.label(f"ID: {connection_id[:8]}...").classes(
                            'text-xs text-gray-400 ml-2'
                        )
                                        
                # Close button
                ui.separator().classes('my-2')
                btn_close = ui.button(
                    'Close',
                    on_click=lambda: self.close()
                )
                btn_close.props('flat')
                btn_close.classes(
                    'w-full bg-gray-100 text-gray-700 '
                    'hover:bg-gray-200 text-sm py-2'
                )
        
        popup.open()
        self._info_popup = popup
    
    def close(self):
        """Close the connection info popup."""
        if self._info_popup:
            self._info_popup.close()
            self._info_popup.delete()
            self._info_popup = None
    
    def _test_adapter_chain(self, edge: Edge):
        """Handle test execution of adapter chain."""
        print(f"[ConnectionInfoPopup] Testing adapter chain for edge {edge.edge_id}")
        print(f"  Chain: {edge.chain_adapter_keys}")
        # TODO: Implement adapter chain test execution
        ui.notify(
            f"Adapter chain test: {edge.chain_adapter_keys}",
            type='info',
            position='top'
        )

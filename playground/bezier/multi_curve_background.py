# test_new_implementation.py
"""Test the new interactive_image pattern implementation."""
from dataclasses import dataclass
from nicegui import ui
from bezier_canvas import BezierCanvas

import draganddrop as dnd

@dataclass
class ToDo:
    title: str

def handle_drop(todo: ToDo, location: str):
    ui.notify(f'"{todo.title}" is now in {location}')


def main():
    """Test the new interactive canvas implementation."""
    
    def handle_mouse_events(e):
        """Handle all mouse events from the canvas."""
        event_type = e.type
        x, y = e.image_x, e.image_y
    
        print(f"🖱️  Mouse event: {event_type} at ({x:.1f}, {y:.1f})")
        
        if event_type == 'click':
            ui.notify(f"Grid clicked at ({x:.1f}, {y:.1f})", type='info')
        elif event_type == 'curve_click':
            curve_id = getattr(e, 'curveId', 'unknown')
            ui.notify(f"Curve {curve_id} clicked", type='warning')
        elif event_type == 'drag_start':
            curve_id = getattr(e, 'curveId', 'unknown')
            point_type = getattr(e, 'pointType', 'unknown')
            ui.notify(f"Started dragging {point_type} of {curve_id}", type='positive')
        elif event_type == 'drag_end':
            curve_id = getattr(e, 'curveId', 'unknown')
            point_type = getattr(e, 'pointType', 'unknown')
            ui.notify(f"Finished dragging {point_type} of {curve_id}", type='positive')
        elif event_type == 'point_drag':
            # Don't spam notifications for drag events, just print
            curve_id = getattr(e, 'curveId', 'unknown')
            point_type = getattr(e, 'pointType', 'unknown')
            print(f"  Dragging {point_type} of {curve_id} to ({x:.1f}, {y:.1f})")
    
    ui.label(
        'Interactive Bézier Canvas - New Implementation'
    ).style('font-size: 1.5em; font-weight: bold; margin-bottom: 1em;')
    ui.label('• Click on grid background to see grid click events')
    ui.label('• Click on curves to see curve click events')
    ui.label('• Drag curve points (start, end, control) to see drag events')
    ui.label('• Background buttons should always be clickable')
    

    # Create canvas with new implementation
    canvas = BezierCanvas(
        width=1000, 
        height=400, 
        show_labels=True,
        on_mouse=handle_mouse_events
    )

    # Add background elements that should always be interactive
    with canvas.background():
        with ui.row():
            with dnd.column('Next', on_drop=handle_drop):
                dnd.card(ToDo('Simplify Layouting'))
                dnd.card(ToDo('Provide Deployment'))
            with dnd.column('Doing', on_drop=handle_drop):
                dnd.card(ToDo('Improve Documentation'))
            with dnd.column('Done', on_drop=handle_drop):
                dnd.card(ToDo('Invent NiceGUI'))
                dnd.card(ToDo('Test in own Projects'))
                dnd.card(ToDo('Publish as Open Source'))
                dnd.card(ToDo('Release Native-Mode'))


    # Add foreground elements that should be interactive but not block canvas events
    with canvas.foreground():
        ui.button('Foreground Button 1', 
                 on_click=lambda: ui.notify('🟢 Foreground button 1 clicked!', type='info')) \
          .style('position: absolute; top: 60px; left: 60px; '
                'background: rgba(34, 197, 94, 0.9); color: white;')

    # Add test curves
    curve1_id = canvas.add_curve(
        start_point=(100, 200),
        end_point=(400, 200),
        control_point1=(200, 100),
        control_point2=(300, 300),
        stroke_color="#ef4444",
        stroke_width=3,
        show_control_points=True
    )
    
    curve2_id = canvas.add_curve(
        start_point=(150, 300),
        end_point=(450, 150),
        control_point1=(250, 350),
        control_point2=(350, 100),
        stroke_color="#10b981",
        stroke_width=3,
        show_control_points=True
    )
    
    # Controls
    with ui.row().style('margin-top: 1em;'):
        ui.button('Select Curve 1', 
                 on_click=lambda: canvas.select_curve(curve1_id))
        ui.button('Select Curve 2', 
                 on_click=lambda: canvas.select_curve(curve2_id))
        ui.button('Deselect All', 
                 on_click=lambda: canvas.select_curve(None))
        ui.button('Add Random Curve', 
                 on_click=lambda: canvas.add_curve(
                     start_point=(50, 50),
                     end_point=(200, 350),
                     stroke_color="#8b5cf6"
                 ))

    # Run the application
    ui.run(
        port=8081,
        reload=True,
        title="Multi-Curve Bézier Canvas Demo",
        uvicorn_reload_includes='*.py,*.js'
    )

if __name__ in {'__main__', '__mp_main__'}:
    main()

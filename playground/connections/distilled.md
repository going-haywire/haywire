---
## `multi_curve_background.py`
---

```python
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
    
    ui.label('Interactive Bézier Canvas - New Implementation').style('font-size: 1.5em; font-weight: bold; margin-bottom: 1em;')
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
```

---
## `bezier_canvas.py`
---

```python
# bezier_canvas_new.py - Interactive Image pattern implementation
import uuid
from typing import Callable, Optional, List, Dict, Any, Tuple
from nicegui import ui
from nicegui.element import Element
from nicegui.events import GenericEventArguments, MouseEventArguments, handle_event

class BezierCanvas(Element, component='bezier_canvas.js'):
    """
    A canvas component that can contain multiple Bézier curves.
    
    This component uses the interactive_image pattern for robust event handling,
    with background elements that can always receive events and SVG curves
    with individual pointer event handlers.
    """

    def __init__(
        self,
        width: int = 600,
        height: int = 400,
        show_labels: bool = False,
        *,
        on_mouse: Optional[Callable] = None
    ) -> None:
        """
        Initialize the Bézier canvas component.
        
        Args:
            width: Width of the canvas in pixels
            height: Height of the canvas in pixels
            show_labels: Whether to show point labels
            on_mouse: Callback for all mouse events (contains event type and coordinates)
        """
        super().__init__()
        
        self._curves = {}  # Store curves by ID
        self._selected_curve_id = None
        
        # Set component properties
        self._props.update({
            'curves': [],
            'width': width,
            'height': height,
            'selectedCurveId': None,
            'showLabels': show_labels
        })
        
        # Set up mouse event handler
        if on_mouse:
            self.on_mouse(on_mouse)

    ui.add_css('''
        .bezier-foreground {
            pointer-events: none;
        }
        
        /* Comprehensive approach - target any potentially interactive element */
        .bezier-foreground *[onclick],
        .bezier-foreground *[onchange],
        .bezier-foreground *[onmousedown],
        .bezier-foreground *[class*="q-"],
        .bezier-foreground *[class*="nicegui-"],
        .bezier-foreground button,
        .bezier-foreground input,
        .bezier-foreground select,
        .bezier-foreground textarea,
        .bezier-foreground [role="button"],
        .bezier-foreground [tabindex]:not([tabindex="-1"]),
        .bezier-foreground a[href],
        .bezier-foreground [draggable="true"] {
            pointer-events: auto;
        }
        ''')


    def on_mouse(self, on_mouse: Callable) -> 'BezierCanvas':
        """Add a callback to be invoked when a mouse event occurs."""
        def handle_mouse(e: GenericEventArguments) -> None:
            args = e.args
            mouse_event_type = args.get('mouse_event_type', '')
            
            # Handle point drag events by updating curve data
            if mouse_event_type == 'point_drag':
                curve_id = args.get('curveId')
                point_type = args.get('pointType')
                x = args.get('image_x', 0.0)
                y = args.get('image_y', 0.0)
                
                print(f"Point drag: curve={curve_id}, point={point_type}, pos=({x}, {y})")
                
                if curve_id in self._curves:
                    curve = self._curves[curve_id]
                    position = {'x': x, 'y': y}
                    
                    if point_type == 'start':
                        curve['startPoint'] = position
                    elif point_type == 'end':
                        curve['endPoint'] = position
                    elif point_type == 'control1':
                        curve['controlPoint1'] = position
                    elif point_type == 'control2':
                        curve['controlPoint2'] = position
                    
                    self._update_curves()
            
            # Create mouse event arguments using a simple object with all needed properties
            class CustomMouseEvent:
                def __init__(self, args, sender, client):
                    self.sender = sender
                    self.client = client
                    self.type = args.get('mouse_event_type', '')
                    self.image_x = args.get('image_x', 0.0)
                    self.image_y = args.get('image_y', 0.0)
                    self.button = args.get('button', 0)
                    self.buttons = args.get('buttons', 0)
                    self.alt = args.get('altKey', False)
                    self.ctrl = args.get('ctrlKey', False)
                    self.meta = args.get('metaKey', False)
                    self.shift = args.get('shiftKey', False)
                    self.curveId = args.get('curveId')
                    self.pointType = args.get('pointType')
            
            # Create custom event object
            event_obj = CustomMouseEvent(args, self, self.client)
            
            # Call the user's callback
            try:
                handle_event(on_mouse, event_obj)
            except Exception as ex:
                # If handle_event doesn't work with our custom object, call directly
                print(f"Direct callback due to: {ex}")
                on_mouse(event_obj)
        
        self.on('mouse', handle_mouse)
        return self

    def add_curve(
        self,
        start_point: Tuple[float, float] = (50, 150),
        end_point: Tuple[float, float] = (350, 150),
        control_point1: Optional[Tuple[float, float]] = None,
        control_point2: Optional[Tuple[float, float]] = None,
        stroke_color: str = "#3b82f6",
        stroke_width: int = 3,
        show_control_points: bool = True,
        curve_id: Optional[str] = None
    ) -> str:
        """
        Add a new curve to the canvas.
        
        Args:
            start_point: (x, y) coordinates of the start point
            end_point: (x, y) coordinates of the end point
            control_point1: (x, y) coordinates of first control point
            control_point2: (x, y) coordinates of second control point
            stroke_color: Color of the curve line
            stroke_width: Width of the curve line
            show_control_points: Whether to show control points
            curve_id: Optional custom ID for the curve
            
        Returns:
            The ID of the created curve
        """
        if curve_id is None:
            curve_id = str(uuid.uuid4())
        
        # Auto-calculate control points if not provided
        if control_point1 is None:
            control_point1 = (start_point[0] + (end_point[0] - start_point[0]) * 0.3, start_point[1] - 50)
        if control_point2 is None:
            control_point2 = (start_point[0] + (end_point[0] - start_point[0]) * 0.7, end_point[1] - 50)
        
        curve_data = {
            'id': curve_id,
            'startPoint': {'x': start_point[0], 'y': start_point[1]},
            'endPoint': {'x': end_point[0], 'y': end_point[1]},
            'controlPoint1': {'x': control_point1[0], 'y': control_point1[1]},
            'controlPoint2': {'x': control_point2[0], 'y': control_point2[1]},
            'strokeColor': stroke_color,
            'strokeWidth': stroke_width,
            'showControlPoints': show_control_points
        }
        
        self._curves[curve_id] = curve_data
        self._update_curves()
        print(f"Added curve {curve_id} with data: {curve_data}")
        return curve_id

    def remove_curve(self, curve_id: str) -> bool:
        """
        Remove a curve from the canvas.
        
        Args:
            curve_id: ID of the curve to remove
            
        Returns:
            True if curve was removed, False if not found
        """
        if curve_id in self._curves:
            del self._curves[curve_id]
            if self._selected_curve_id == curve_id:
                self._selected_curve_id = None
                self._props['selectedCurveId'] = None
            self._update_curves()
            print(f"Removed curve {curve_id}")
            return True
        return False

    def update_curve(
        self,
        curve_id: str,
        start_point: Optional[Tuple[float, float]] = None,
        end_point: Optional[Tuple[float, float]] = None,
        control_point1: Optional[Tuple[float, float]] = None,
        control_point2: Optional[Tuple[float, float]] = None,
        stroke_color: Optional[str] = None,
        stroke_width: Optional[int] = None,
        show_control_points: Optional[bool] = None
    ) -> bool:
        """
        Update properties of an existing curve.
        
        Args:
            curve_id: ID of the curve to update
            start_point: New start point coordinates
            end_point: New end point coordinates
            control_point1: New first control point coordinates
            control_point2: New second control point coordinates
            stroke_color: New stroke color
            stroke_width: New stroke width
            show_control_points: New control points visibility
            
        Returns:
            True if curve was updated, False if not found
        """
        if curve_id not in self._curves:
            print(f"Curve {curve_id} not found for update")
            return False
        
        curve = self._curves[curve_id]
        
        if start_point is not None:
            curve['startPoint'] = {'x': start_point[0], 'y': start_point[1]}
        if end_point is not None:
            curve['endPoint'] = {'x': end_point[0], 'y': end_point[1]}
        if control_point1 is not None:
            curve['controlPoint1'] = {'x': control_point1[0], 'y': control_point1[1]}
        if control_point2 is not None:
            curve['controlPoint2'] = {'x': control_point2[0], 'y': control_point2[1]}
        if stroke_color is not None:
            curve['strokeColor'] = stroke_color
        if stroke_width is not None:
            curve['strokeWidth'] = stroke_width
        if show_control_points is not None:
            curve['showControlPoints'] = show_control_points
        
        self._update_curves()
        print(f"Updated curve {curve_id}")
        return True

    def select_curve(self, curve_id: Optional[str]) -> None:
        """
        Select a curve (affects visual styling).
        
        Args:
            curve_id: ID of curve to select, or None to deselect all
        """
        self._selected_curve_id = curve_id
        self._props['selectedCurveId'] = curve_id
        self.update()

    def get_curve(self, curve_id: str) -> Optional[Dict[str, Any]]:
        """
        Get curve data by ID.
        
        Args:
            curve_id: ID of the curve
            
        Returns:
            Curve data dictionary or None if not found
        """
        return self._curves.get(curve_id)

    def get_all_curves(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all curves data.
        
        Returns:
            Dictionary mapping curve IDs to curve data
        """
        return self._curves.copy()

    def clear_curves(self) -> None:
        """Remove all curves from the canvas."""
        self._curves.clear()
        self._selected_curve_id = None
        self._props['selectedCurveId'] = None
        self._update_curves()

    def get_curve_path_data(self, curve_id: str) -> Optional[str]:
        """
        Get SVG path data for a curve.
        
        Args:
            curve_id: ID of the curve
            
        Returns:
            SVG path data string or None if curve not found
        """
        if curve_id not in self._curves:
            return None
        
        curve = self._curves[curve_id]
        start = curve['startPoint']
        end = curve['endPoint']
        cp1 = curve['controlPoint1']
        cp2 = curve['controlPoint2']
        return f"M {start['x']},{start['y']} C {cp1['x']},{cp1['y']} {cp2['x']},{cp2['y']} {end['x']},{end['y']}"

    def _update_curves(self):
        """Update the curves prop and refresh the component."""
        self._props['curves'] = list(self._curves.values())
        self.update()
        print(f"Updated {len(self._curves)} curves")

    def foreground(self):
        """
        Returns:
            Context manager for adding elements to the foreground
        """              
        return super().add_slot('foreground')

    def background(self):
        """
        Returns:
            Context manager for adding elements to the background
        """              
        return super().add_slot('background')

```

---
## `draganddrop.py`
---

```python
from __future__ import annotations

from typing import Callable, Optional, Protocol

from nicegui import ui


class Item(Protocol):
    title: str


dragged: Optional[card] = None


class column(ui.column):

    def __init__(self, name: str, on_drop: Optional[Callable[[Item, str], None]] = None) -> None:
        super().__init__()
        with self.classes('bg-blue-grey-2 w-60 p-4 rounded shadow-2'):
            ui.label(name).classes('text-bold ml-1')
        self.name = name
        self.on('dragover.prevent', self.highlight)
        self.on('dragleave', self.unhighlight)
        self.on('drop', self.move_card)
        self.on_drop = on_drop

    def highlight(self) -> None:
        self.classes(remove='bg-blue-grey-2', add='bg-blue-grey-3')

    def unhighlight(self) -> None:
        self.classes(remove='bg-blue-grey-3', add='bg-blue-grey-2')

    def move_card(self) -> None:
        global dragged  # pylint: disable=global-statement # noqa: PLW0603
        self.unhighlight()
        dragged.parent_slot.parent.remove(dragged)
        with self:
            card(dragged.item)
        self.on_drop(dragged.item, self.name)
        dragged = None


class card(ui.card):

    def __init__(self, item: Item) -> None:
        super().__init__()
        self.item = item
        with self.props('draggable').classes('w-full cursor-pointer bg-grey-1'):
            ui.label(item.title)
        self.on('dragstart', self.handle_dragstart)

    def handle_dragstart(self) -> None:
        global dragged  # pylint: disable=global-statement # noqa: PLW0603
        dragged = self```


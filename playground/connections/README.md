# 🎨 Bézier Curve Component for NiceGUI

A custom NiceGUI component that creates interactive SVG Bézier curves with drag-and-drop functionality, customizable styling, and event handling.

## 🚀 Quick Start

### 1. Project Structure
Create the following files in your project directory:

```
your_project/
├── main.py                 # Main application (example usage)
├── bezier_curve.py         # Python component class
├── bezier_curve.js         # Vue.js frontend component
└── requirements.txt        # Dependencies
```

### 2. Dependencies

Create `requirements.txt`:
```
nicegui>=1.4.0
pyperclip>=1.8.0  # Optional: for clipboard functionality
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. File Setup

**Step 1**: Save the `bezier_curve.py` file (Python component)
**Step 2**: Save the `bezier_curve.js` file (Vue.js component) 
**Step 3**: Save the `main.py` file (example application)

### 4. Run the Application

```bash
python main.py
```

Navigate to `http://localhost:8080` to see the interactive demo.

## 🎯 Features

### ✨ Interactive Elements
- **Drag Points**: Click and drag start points, end points, and control points
- **Real-time Updates**: See curve changes instantly as you drag
- **Click Events**: Handle clicks on curves and canvas
- **Visual Feedback**: Hover effects and visual indicators

### 🎨 Customization Options
- **Colors**: Any CSS color (hex, rgb, named colors)
- **Stroke Width**: Configurable line thickness
- **Canvas Size**: Adjustable width and height
- **Control Point Visibility**: Show/hide control points and guides
- **Grid Background**: Optional grid for alignment

### 📱 Responsive Design
- Works on desktop and mobile devices
- Touch-friendly drag interactions
- Responsive layout with proper scaling

## 🔧 API Reference

### BezierCurve Class

```python
BezierCurve(
    start_point=(50, 150),              # Start point coordinates
    end_point=(350, 150),               # End point coordinates
    control_point1=None,                # First control point (auto-calculated if None)
    control_point2=None,                # Second control point (auto-calculated if None)
    stroke_color="#3b82f6",             # Curve color
    stroke_width=3,                     # Line thickness
    width=400,                          # Canvas width
    height=200,                         # Canvas height
    show_control_points=True,           # Show control points
    on_curve_click=None,                # Click event handler
    on_point_drag=None                  # Drag event handler
)
```

### Methods

#### `update_curve(start_point=None, end_point=None, control_point1=None, control_point2=None)`
Update curve points dynamically.

```python
curve.update_curve(
    start_point=(100, 100),
    end_point=(300, 200)
)
```

#### `set_stroke_style(color, width)`
Change the curve's appearance.

```python
curve.set_stroke_style("#ff0000", 5)  # Red color, 5px width
```

#### `toggle_control_points(show)`
Show or hide control points.

```python
curve.toggle_control_points(False)  # Hide control points
```

#### `get_path_data()`
Get the SVG path data string.

```python
path_data = curve.get_path_data()
print(path_data)  # "M 50,150 C 150,100 250,100 350,150"
```

### Event Handlers

#### Curve Click Events
```python
def handle_curve_click(event):
    x, y = event.args['x'], event.args['y']
    target = event.args.get('target', 'canvas')
    print(f"Clicked {target} at ({x}, {y})")

curve = BezierCurve(on_curve_click=handle_curve_click)
```

#### Point Drag Events
```python
def handle_point_drag(event):
    point_type = event.args['pointType']  # 'start', 'end', 'control1', 'control2'
    position = event.args['position']     # {'x': float, 'y': float}
    print(f"{point_type} moved to ({position['x']}, {position['y']})")

curve = BezierCurve(on_point_drag=handle_point_drag)
```

## 💡 Usage Examples

### Basic Usage
```python
from nicegui import ui
from bezier_curve import BezierCurve

# Simple curve
curve = BezierCurve(
    start_point=(50, 100),
    end_point=(350, 100),
    stroke_color="#3b82f6"
)

ui.run()
```

### Interactive Curve Editor
```python
def update_color(color):
    curve.set_stroke_style(color, 4)

curve = BezierCurve(show_control_points=True)

with ui.row():
    ui.button("Blue", on_click=lambda: update_color("#3b82f6"))
    ui.button("Red", on_click=lambda: update_color("#ef4444"))
    ui.button("Green", on_click=lambda: update_color("#10b981"))
```

### Animation Example
```python
import math
from nicegui import ui
from bezier_curve import BezierCurve

curve = BezierCurve()

def animate():
    for i in range(100):
        y_offset = 50 * math.sin(i * 0.1)
        curve.update_curve(
            control_point1=(150, 100 + y_offset),
            control_point2=(250, 100 - y_offset)
        )
        ui.timer(0.05, lambda: None)  # Small delay

ui.button("Animate", on_click=animate)
```

### Multiple Curves
```python
# Create multiple curves with different styles
curves = [
    BezierCurve(
        start_point=(50, 50),
        end_point=(350, 50),
        stroke_color="#3b82f6",
        show_control_points=False
    ),
    BezierCurve(
        start_point=(50, 150),
        end_point=(350, 150),
        stroke_color="#ef4444",
        show_control_points=False
    ),
    BezierCurve(
        start_point=(50, 250),
        end_point=(350, 250),
        stroke_color="#10b981",
        show_control_points=False
    )
]
```

## 🎨 Styling and Customization

### CSS Classes Available
The component includes these CSS classes for custom styling:

- `.bezier-curve-container`: Main container
- `.bezier-svg`: SVG element
- `.bezier-path`: The main curve path
- `.control-point`: Control point circles
- `.end-point`: Start/end point circles

### Custom Styling Example
```python
# Add custom CSS
ui.add_head_html("""
<style>
.bezier-curve-container {
    border: 2px solid #e5e7eb;
    border-radius: 8px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}

.control-point:hover {
    fill: #3b82f6 !important;
    transform: scale(1.2);
}

.end-point:hover {
    transform: scale(1.1);
}
</style>
""")
```

### Color Schemes
```python
# Predefined color schemes
COLORS = {
    'blue': '#3b82f6',
    'red': '#ef4444', 
    'green': '#10b981',
    'yellow': '#f59e0b',
    'purple': '#8b5cf6',
    'pink': '#ec4899',
    'indigo': '#6366f1',
    'cyan': '#06b6d4'
}
```

## 🔍 Advanced Features

### Path Data Export
```python
# Export curve as SVG path data
path_data = curve.get_path_data()

# Use in other SVG contexts
ui.html(f'<svg><path d="{path_data}" stroke="blue" fill="none"/></svg>')
```

### Curve Analytics
```python
def analyze_curve(curve):
    """Calculate curve properties"""
    start = curve._props['startPoint']
    end = curve._props['endPoint']
    
    # Calculate curve length (approximation)
    length = ((end['x'] - start['x'])**2 + (end['y'] - start['y'])**2)**0.5
    
    return {
        'length': length,
        'start': start,
        'end': end,
        'path': curve.get_path_data()
    }
```

### Integration with Other Components
```python
# Use with charts, diagrams, or interactive graphics
with ui.card():
    ui.label("Curve Designer")
    curve = BezierCurve()
    
    with ui.row():
        ui.chart({
            'chart': {'type': 'line'},
            'series': [{'data': [[0, 0], [1, 1]]}]
        })
```

## 🐛 Troubleshooting

### Common Issues

1. **Component not loading**: Ensure both `.py` and `.js` files are in the same directory
2. **Drag not working**: Check if mouse events are being captured by other elements
3. **Styling issues**: Verify CSS classes and SVG structure
4. **Performance**: For many curves, consider disabling control points for better performance

### Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Add debug information to events
def debug_handler(event):
    print(f"Debug: {event.args}")

curve = BezierCurve(on_curve_click=debug_handler, on_point_drag=debug_handler)
```

## 🤝 Contributing

Feel free to extend this component with additional features:

- **Quadratic Bézier curves**: Simpler curves with one control point
- **Multi-segment paths**: Connect multiple Bézier curves
- **Animation presets**: Built-in animation effects
- **Snap-to-grid**: Align points to grid intersections
- **Undo/redo**: History management for curve edits

## 📄 License

This component is provided as-is for educational and development purposes. Feel free to modify and use in your projects.

---

**Happy curve drawing! 🎨✨**
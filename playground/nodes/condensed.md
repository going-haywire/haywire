# Building an Interactive Node Editor with NiceGUI and Client-Side JavaScript

This document outlines a modern and efficient architecture for creating a node-based editor using NiceGUI. The core principle is to delegate all real-time user interactions to client-side JavaScript to ensure a smooth, responsive user experience, while using Python for state management.

---

### 1. Core Architecture: Separating State from Presentation

The recommended approach separates the application into two distinct layers:

-   **Python (NiceGUI) - The State Manager**: The Python backend is responsible for maintaining the data model, rendering the initial UI, and handling finalized state changes.
-   **JavaScript (Client-Side) - The Interaction Handler**: The browser is responsible for all real-time mouse events and visual feedback, ensuring a fluid UI without server latency.

### 2. Drawing Connections with SVG

Connections between nodes should be rendered as `<path>` elements within a single, global `<svg>` container. This vector-based approach allows for easy styling with CSS, direct DOM event handling on individual connections, and perfect quality at any zoom level.

```python
with ui.element('div').classes('relative w-full h-screen'):
    # The SVG layer is in the background
    svg_canvas = ui.svg().classes('absolute top-0 left-0 w-full h-full').style('z-index: 0;')
    
    # The node container is on top
    with ui.element('div').classes('absolute top-0 left-0 w-full h-full').style('z-index: 1;'):
        # Your draggable node panels will be created here
        pass
```

### 3. Creating Connections: A Purely Client-Side Flow

This process handles the entire drag-and-drop interaction in the browser, only notifying the server upon completion.

#### Step 1: Render Pins in Python

Render each connection pin with unique `id` and `data-*` attributes for JavaScript to use. Note the absence of Python `.on()` handlers for drag events.

```python

# In your NodePanel class
def _render_node_content(self):
    # Give the main card a unique ID
    self.node_card.props(f'id="node-{self.node.id}"') 
    # ... rest of your rendering

# In your NodePanel class
def _render_output_port(self, port):
    # Create a unique, predictable ID for the port element
    port_id = f"port-{self.node.id}-{port.name}"

    # Define the port element with data attributes for JS to use
    port_element = ui.element('div').classes(
        # A general 'port' class lets JS find all pins easily
        f'port output-port port-{port.data_type}'
    ).props({
        'id': port_id,
        'data-node-id': self.node.id,
        'data-port-name': port.name,
        'data-port-type': 'output',  # Use 'input' for input ports
    }).style(
        f'width: 12px; height: 12px; '
        f'background: {port.color}; '
        f'border: 2px solid white; border-radius: 50%; '
        f'cursor: crosshair;'
    )
```

#### Step 2: Handle Drag Logic in JavaScript

Inject a script to manage the entire drag-and-drop flow. This script creates a temporary line that follows the mouse and detects valid drop targets.

```javascript
// In a one-time script injection via ui.run_javascript
# In your main.py, after the UI is ready

def setup_connection_logic():
    js_code = """
    let isDragging = false;
    let startPin = null;
    let tempPath = null;
    const svg = document.querySelector('.bezier-canvas svg'); // Assuming your SVG canvas has this class

    // Function to get a pin's center coordinates relative to the SVG canvas
    function getPinPosition(pinElement) {
        const svgRect = svg.getBoundingClientRect();
        const pinRect = pinElement.getBoundingClientRect();
        return {
            x: pinRect.left + pinRect.width / 2 - svgRect.left,
            y: pinRect.top + pinRect.height / 2 - svgRect.top,
        };
    }

    // Function to draw the bezier curve
    function drawPath(startPos, endPos) {
        return `M ${startPos.x} ${startPos.y} C ${startPos.x + 50} ${startPos.y}, ${endPos.x - 50} ${endPos.y}, ${endPos.x} ${endPos.y}`;
    }

    // MOUSE DOWN: Start dragging a connection
    document.body.addEventListener('mousedown', (e) => {
        const targetPin = e.target.closest('.port');
        if (!targetPin) return;

        isDragging = true;
        startPin = targetPin;
        const startPos = getPinPosition(startPin);

        // Create a temporary path to show the user
        tempPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        tempPath.setAttribute('d', drawPath(startPos, startPos));
        tempPath.setAttribute('stroke', '#a0a0a0');
        tempPath.setAttribute('stroke-width', '2');
        tempPath.setAttribute('fill', 'none');
        tempPath.style.pointerEvents = 'none'; // So it doesn't interfere with mouse events
        svg.appendChild(tempPath);
    });

    // MOUSE MOVE: Update the temporary path
    document.body.addEventListener('mousemove', (e) => {
        if (!isDragging || !tempPath) return;
        
        const startPos = getPinPosition(startPin);
        // Get mouse position relative to SVG canvas
        const svgRect = svg.getBoundingClientRect();
        const mousePos = {
            x: e.clientX - svgRect.left,
            y: e.clientY - svgRect.top,
        };
        
        tempPath.setAttribute('d', drawPath(startPos, mousePos));
    });

    // MOUSE UP: Finalize or cancel the connection
    document.body.addEventListener('mouseup', (e) => {
        if (!isDragging || !startPin) {
            isDragging = false;
            return;
        }

        const endPin = e.target.closest('.port');

        // Clean up the temporary path
        if (tempPath) {
            tempPath.remove();
            tempPath = null;
        }

        // Check if the connection is valid
        if (endPin && endPin !== startPin && startPin.dataset.portType !== endPin.dataset.portType) {
            // A valid connection was made!
            console.log(`Connection made from ${startPin.id} to ${endPin.id}`);
            
            // Get the details to send to Python
            const startDetails = startPin.dataset;
            const endDetails = endPin.dataset;
            
            // Call the Python function with the connection data
            // Ensure the function name matches your Python function
            nicegui.run_py_function(
                'on_new_connection', 
                startDetails.nodeId, 
                startDetails.portName, 
                endDetails.nodeId, 
                endDetails.portName
            );

        } else {
            // Invalid connection, do nothing
            console.log("Connection cancelled.");
        }
        
        isDragging = false;
        startPin = null;
    });
    """
    ui.run_javascript(js_code)

# You would call setup_connection_logic() once in your app.
```

#### Step 3: Define the Python Callback

This function is the endpoint that JavaScript calls to finalize a new connection.

```python
# In your main Python file
def on_new_connection(start_node_id, start_port_name, end_node_id, end_port_name):
    print(f"New connection received: {start_node_id}:{start_port_name} -> {end_node_id}:{end_port_name}")
    # Here, you update your graph's data model
    # and command the UI to draw the permanent SVG path.
```

### 4. Updating Connections with `MutationObserver`

To efficiently update connections when a node moves, use a `MutationObserver` to avoid polling.

```javascript
// In a one-time script injection
# main.py, after setting up the initial UI
def setup_connection_observers():
    js_code = """
    // Function to update an SVG path based on its connected pin elements
    function updatePath(pathElement) {
        if (!pathElement) return;

        const [_, start_port_id, end_port_id] = pathElement.id.split('--');
        
        const startPin = document.getElementById(start_port_id);
        const endPin = document.getElementById(end_port_id);

        if (!startPin || !endPin) {
            // Pin might have been deleted, remove path
            pathElement.remove();
            return;
        }

        const svgRect = pathElement.ownerSVGElement.getBoundingClientRect();
        const startRect = startPin.getBoundingClientRect();
        const endRect = endPin.getBoundingClientRect();

        // Calculate coordinates relative to the SVG container
        const startX = startRect.left + startRect.width / 2 - svgRect.left;
        const startY = startRect.top + startRect.height / 2 - svgRect.top;
        const endX = endRect.left + endRect.width / 2 - svgRect.left;
        const endY = endRect.top + endRect.height / 2 - svgRect.top;
        
        // Create the 'd' attribute for a bezier curve
        const d = `M ${startX} ${startY} C ${startX + 50} ${startY}, ${endX - 50} ${endY}, ${endX} ${endY}`;
        pathElement.setAttribute('d', d);
    }

    // This observer watches for changes in the node panels' positions
    const observer = new MutationObserver((mutations) => {
        mutations.forEach(mutation => {
            // The 'target' is the node panel div whose 'style' attribute changed
            const nodeId = mutation.target.id;
            
            // Find all paths connected to this node and update them
            document.querySelectorAll(`[id*="${nodeId}"]`).forEach(el => {
                if (el.tagName.toLowerCase() === 'path') {
                    updatePath(el);
                }
            });
        });
    });

    // Start observing all node panels for attribute changes
    document.querySelectorAll('[id^="node-"]').forEach(nodePanel => {
        observer.observe(nodePanel, { 
            attributes: true, // Watch for attribute changes
            attributeFilter: ['style'] // Specifically the 'style' attribute
        });
    });
    """
    ui.run_javascript(js_code)

# Call this function once the initial nodes are rendered
setup_connection_observers()
```

## Summary

Here’s a complete strategy and a practical code example for how to achieve this with NiceGUI.

1. **Setup in Python**: In your NodePanel.py, you will render the pin elements as you are doing now, but you will not attach Python callbacks like on('mousedown', ...) for the connection logic. Instead, you'll assign unique IDs and data-* attributes that JavaScript can use to identify the pins, their types (input/output), and their parent nodes.

2. **One-Time JavaScript Injection**: You will use ui.run_javascript to inject a single, comprehensive script. This script will run once and set up all the necessary event listeners on the client side.

3. **JavaScript Handles the Interaction**: This script will:
- Listen for a mousedown event on any element with a .port class.
- When a drag starts, it will create a temporary SVG <path> that follows the mouse cursor.
- It will listen for mousemove on the whole document to update the path's end point in real-time.
- It will use mouseover on other ports to detect a valid drop target, providing visual feedback (e.g., changing the pin's color).
- On mouseup, it will check if the connection is valid (e.g., connecting an output to an input).

4. **Final Callback to Python**: Only if a valid connection is made on mouseup, the JavaScript will call a Python function using nicegui.run_py_function, sending the IDs of the start and end pins. If the drop is invalid, the temporary path is simply discarded, and no server communication happens.

IMPORTANT: The ground truth is always in the python code, the javascript is just a UI element to make the user experience smooth. So when a new node is created or a new connection is made, even though this happens on the UI side, it first send this commands to the python representation, and only once these are confirmed, a callback is sent to the javascript to update the UI.



from nicegui import ui
import uuid

from .zoom_pan_vue import ZoomPanContainer


class MinimapCanvas(ui.element):
    """
    A canvas-based minimap for the ZoomPanContainer that shows an overview
    of the content and current viewport position.

    Features:
    - Canvas-based rendering for performance
    - Draggable viewport rectangle for navigation
    - Click-to-center functionality
    - Real-time sync with main viewport
    - Toggle show/hide
    - Configurable size and position
    """

    def __init__(
        self,
        zoom_container: ZoomPanContainer,
        width: int = 200,
        position: str = "top-right",  # 'top-right', 'top-left', 'bottom-right', 'bottom-left'
        background_color: str = "#f0f0f0",
        content_color: str = "#4285f4",
        viewport_color: str = "#ea4335",
        visible: bool = True,
        **kwargs,
    ) -> None:
        """
        Initialize the MinimapCanvas.

        Args:
            zoom_container: The ZoomPanContainer to create a minimap for
            width: Minimap width in pixels (default: 200)
            height: Minimap height in pixels (default: 150)
            position: Position of the minimap (default: 'top-right')
            background_color: Background color of the minimap
            content_color: Color for content rectangles
            viewport_color: Color for viewport indicator
            visible: Whether minimap is initially visible
        """
        super().__init__("div", **kwargs)

        # Store references and configuration
        self.zoom_container = zoom_container
        self.minimap_width = width
        self.position = position
        self.background_color = background_color
        self.content_color = content_color
        self.viewport_color = viewport_color
        self.is_visible = visible

        # Generate unique ID for this minimap
        self.minimap_id = f"minimap-{uuid.uuid4().hex[:8]}"
        self.canvas_id = f"canvas-{uuid.uuid4().hex[:8]}"

        # Content tracking
        self.content_elements = []
        self.content_bounds = {"minX": 0, "minY": 0, "maxX": 0, "maxY": 0}
        self.scale_factor = 1.0

        # Setup the minimap
        self._setup_minimap()
        self._inject_styles()

        # Initialize after DOM is ready
        _ = ui.timer(0.6, self._inject_script, once=True)
        _ = ui.timer(1.1, self._scan_content, once=True)

        # Hook into the zoom container's callbacks
        self._hook_zoom_container_events()

    def _setup_minimap(self) -> None:
        """Setup the minimap container structure."""
        _ = self.classes("minimap-container")

        # Position styles based on position parameter
        position_styles = {
            "top-right": "top: 10px; right: 10px;",
            "top-left": "top: 10px; left: 10px;",
            "bottom-right": "bottom: 10px; right: 10px;",
            "bottom-left": "bottom: 10px; left: 10px;",
        }

        style = (
            f"position: absolute; "
            f"width: {self.minimap_width}px; "
            f"z-index: 1001; "
            f"border: 2px solid #ccc; "
            f"border-radius: 6px; "
            f"background: {self.background_color}; "
            f"box-shadow: 0 2px 8px rgba(0,0,0,0.2); "
            f"cursor: crosshair; "
            f"{position_styles.get(self.position, position_styles['top-right'])} "
            f"{'' if self.is_visible else 'display: none;'}"
        )

        _ = self.style(style)
        _ = self.props(f'id="{self.minimap_id}"')

        # Create canvas element
        with self:
            self.canvas = ui.element("canvas")
            self.canvas.props(f'id="{self.canvas_id}" width="{self.minimap_width}"')
            self.canvas.style("display: block; width: 100%;")

            # Toggle button
            self.toggle_btn = ui.button("×", on_click=self.toggle_visibility).props("round dense size=xs")
            self.toggle_btn.style(
                "position: absolute; top: -8px; right: -8px; width: 16px; height: 16px; min-width: 16px;"
            )
            self.toggle_btn.classes("bg-gray-600 text-white text-xs")

        self._apply_zoom_container_ratio(self.minimap_width)

    def _inject_styles(self) -> None:
        """Inject CSS styles for the minimap."""
        ui.add_css("""
            .minimap-container {
                user-select: none;
                -webkit-user-select: none;
                -moz-user-select: none;
                -ms-user-select: none;
            }
            
            .minimap-container canvas {
                border-radius: 4px;
            }
            
            .minimap-container.dragging {
                cursor: grabbing !important;
            }
        """)

    def _inject_script(self) -> None:
        """Inject JavaScript for minimap functionality."""
        script = f"""
            (function() {{
                let retryCount = 0;
                const maxRetries = 50;
                
                function initializeMinimap() {{
                    retryCount++;
                    
                    const mainContainer = document.getElementById(
                        '{self.zoom_container.container_id}'
                    );
                    const minimap = document.getElementById('{self.minimap_id}');
                    const canvas = document.getElementById('{self.canvas_id}');
                    
                    if (!minimap || !canvas || !mainContainer) {{
                        if (retryCount < maxRetries) {{
                            setTimeout(initializeMinimap, 100);
                        }}
                        return;
                    }}
                    
                    if (minimap._minimapInitialized) {{
                        return;
                    }}
                    minimap._minimapInitialized = true;
                    
                    const ctx = canvas.getContext('2d');
                    let isDragging = false;
                    let lastMouseX = 0;
                    let lastMouseY = 0;

                    let minimap_width = 200;
                    let minimap_height = 200;
                    
                    // Minimap state
                    let contentBounds = {{ minX: -500, minY: -500, maxX: 2000, maxY: 2000 }};
                    let scaleFactor = 1.0;
                    let viewportRect = {{ x: 0, y: 0, width: 50, height: 50 }};
                    
                    const MINIMAP_PADDING = 10;
                    let minimap_content_width = minimap_width - (MINIMAP_PADDING * 2);
                    let minimap_content_height = minimap_height - (MINIMAP_PADDING * 2);

                    let contentWidth = 1000;
                    let contentHeight = 1000;

                    let panX = 0;
                    let panY = 0;

                    let zoom = 1.0;
                    
                    function updateMinimapBounds(width) {{
                        minimap_width = width;
                        if (mainContainer) {{
                            const rect = mainContainer.getBoundingClientRect();
                            const aspectRatio = rect.height / rect.width;
                            minimap_height = Math.round(width * aspectRatio);
                        }}
                        minimap_content_width = minimap_width - (MINIMAP_PADDING * 2);
                        minimap_content_height = minimap_height - (MINIMAP_PADDING * 2);
                    }}  
                    
                    function updateContentBounds(bounds) {{
                        contentBounds = bounds;
                        contentWidth = contentBounds.maxX - contentBounds.minX;
                        contentHeight = contentBounds.maxY - contentBounds.minY;
                        
                        // Calculate scale to fit content in minimap
                        const scaleX = minimap_content_width / contentWidth;
                        const scaleY = minimap_content_height / contentHeight;
                        scaleFactor = Math.min(scaleX, scaleY, 1.0); // Don't scale up
                        
                        console.log(
                            'Content bounds updated:', bounds, 
                            'Scale factor:', scaleFactor
                        );
                        drawMinimap();
                    }}
                    
                    function updateViewport(_zoom, _panX, _panY) {{
                        zoom = _zoom;
                        panX = _panX / zoom;
                        panY = _panY / zoom;
                        
                        if (!mainContainer) return;
                        
                        const containerRect = mainContainer.getBoundingClientRect();
                        
                        // Calculate viewport in content coordinates
                        const viewWidth = containerRect.width / zoom;
                        const viewHeight = containerRect.height / zoom;
                        const viewX = -panX / zoom;
                        const viewY = -panY / zoom;
                        
                        // Convert content coordinates to minimap pixel coordinates
                        const minimapX = MINIMAP_PADDING + 
                            (viewX - contentBounds.minX) * scaleFactor;
                        const minimapY = MINIMAP_PADDING + 
                            (viewY - contentBounds.minY) * scaleFactor;
                        const minimapWidth = Math.max(2, viewWidth * scaleFactor);
                        const minimapHeight = Math.max(2, viewHeight * scaleFactor);
                        
                        viewportRect = {{
                            x: minimapX,
                            y: minimapY,
                            width: minimapWidth,
                            height: minimapHeight
                        }};
                        
                        drawMinimap();
                    }}
                    
                    function drawMinimap() {{
                        ctx.clearRect(0, 0, minimap_width, minimap_height);
                        
                        // Draw background
                        ctx.fillStyle = '{self.background_color}';
                        ctx.fillRect(0, 0, minimap_width, minimap_height);
                        
                        // Draw content area bounds
                        const boundsX = MINIMAP_PADDING;
                        const boundsY = MINIMAP_PADDING;
                        const boundsWidth = (contentBounds.maxX - contentBounds.minX) * scaleFactor;
                        const boundsHeight = (contentBounds.maxY - contentBounds.minY) * scaleFactor;
                        
                        // Content area background
                        ctx.fillStyle = '#fafafa';
                        ctx.fillRect(boundsX, boundsY, boundsWidth, boundsHeight);
                        
                        // Content area border
                        ctx.strokeStyle = '#ddd';
                        ctx.lineWidth = 1;
                        ctx.strokeRect(boundsX, boundsY, boundsWidth, boundsHeight);
                        
                        // Draw content representation (grid pattern)
                        ctx.fillStyle = '{self.content_color}';
                        const gridSize = Math.max(1, Math.min(4, 20 * scaleFactor));
                        const gridSpacing = Math.max(gridSize * 2, 8);
                        
                        for (let x = boundsX; x <= boundsX + boundsWidth; x += gridSize) {{
                            for (let y = boundsY; y <= boundsY + boundsHeight; y += gridSize) {{
                                if (x + gridSize <= boundsX + boundsWidth && 
                                    y + gridSize <= boundsY + boundsHeight) {{
                                    ctx.fillRect(x, y, 1, 1);
                                }}
                            }}
                        }}
                        
                        // Draw viewport rectangle
                        ctx.strokeStyle = '{self.viewport_color}';
                        ctx.fillStyle = '{self.viewport_color}33'; // Semi-transparent
                        ctx.lineWidth = 2;
                        
                        // Clamp viewport to minimap bounds
                        const clampedX = Math.max(0, Math.min(viewportRect.x, minimap_width));
                        const clampedY = Math.max(0, Math.min(viewportRect.y, minimap_height));
                        const clampedWidth = Math.max(
                            1, 
                            Math.min(viewportRect.width, minimap_width - clampedX)
                        );
                        const clampedHeight = Math.max(
                            1, 
                            Math.min(viewportRect.height, minimap_height - clampedY)
                        );
                        
                        ctx.fillRect(clampedX, clampedY, clampedWidth, clampedHeight);
                        ctx.strokeRect(clampedX, clampedY, clampedWidth, clampedHeight);
                        
                        // Debug info (remove in production)
                        ctx.fillStyle = 'black';
                        ctx.font = '10px monospace';
                        ctx.fillText(
                            `Minimap: ${{minimap_width}}x${{minimap_height}}`, 
                            5, 
                            minimap_height - 65
                        );
                        ctx.fillText(
                            `Content: ${{contentWidth.toFixed(0)}}x${{contentHeight.toFixed(0)}}`, 
                            5, 
                            minimap_height - 55
                        );
                        ctx.fillText(
                            `Pan: ${{panX.toFixed(0)}}x${{panY.toFixed(0)}}`, 
                            5, 
                            minimap_height - 45
                        );
                        ctx.fillText(`Zoom: ${{zoom.toFixed(3)}}`, 5, minimap_height - 35);
                        ctx.fillText(`Scale: ${{scaleFactor.toFixed(3)}}`, 5, minimap_height - 25);
                        ctx.fillText(
                            `Bounds: ${{Math.round(boundsWidth)}}x${{Math.round(boundsHeight)}}`, 
                            5, 
                            minimap_height - 15
                        );
                        ctx.fillText(
                            `View: ${{Math.round(clampedWidth)}}x${{Math.round(clampedHeight)}}`, 
                            5, 
                            minimap_height - 5
                        );
                    }}
                    
                    function minimapToContent(minimapX, minimapY) {{
                        const contentX = contentBounds.minX + 
                            (minimapX - MINIMAP_PADDING) / scaleFactor;
                        const contentY = contentBounds.minY + 
                            (minimapY - MINIMAP_PADDING) / scaleFactor;
                        return {{ x: contentX, y: contentY }};
                    }}
                    
                    function handleMinimapClick(e) {{
                        const rect = canvas.getBoundingClientRect();
                        const minimapX = e.clientX - rect.left;
                        const minimapY = e.clientY - rect.top;
                        
                        const contentPos = minimapToContent(minimapX, minimapY);
                        
                        // Get main container
                        if (mainContainer && mainContainer._zoomPanControls) {{
                            const containerRect = mainContainer.getBoundingClientRect();
                            const currentZoom = mainContainer._zoomPanControls.getZoom();
                            
                            // Calculate new pan to center clicked point
                            const newPanX = -(
                                contentPos.x * currentZoom - containerRect.width / 2
                            );
                            const newPanY = -(
                                contentPos.y * currentZoom - containerRect.height / 2
                            );
                            
                            mainContainer._zoomPanControls.setPan(newPanX, newPanY);
                        }}
                    }}
                    
                    function handleMinimapDrag(e) {{
                        if (!isDragging) return;
                        
                        const rect = canvas.getBoundingClientRect();
                        const currentX = e.clientX - rect.left;
                        const currentY = e.clientY - rect.top;
                        const deltaX = currentX - lastMouseX;
                        const deltaY = currentY - lastMouseY;
                        
                        // Convert delta to content coordinates
                        const contentDeltaX = deltaX / scaleFactor;
                        const contentDeltaY = deltaY / scaleFactor;
                        
                        // Apply to main container
                        if (mainContainer && mainContainer._zoomPanControls) {{
                            const currentPan = mainContainer._zoomPanControls.getPan();
                            const currentZoom = mainContainer._zoomPanControls.getZoom();
                            
                            const newPanX = currentPan.x - contentDeltaX * currentZoom;
                            const newPanY = currentPan.y - contentDeltaY * currentZoom;
                            
                            mainContainer._zoomPanControls.setPan(newPanX, newPanY);
                        }}
                        
                        lastMouseX = currentX;
                        lastMouseY = currentY;
                    }}
                    
                    // Event handlers
                    canvas.addEventListener('click', handleMinimapClick);
                    
                    canvas.addEventListener('mousedown', (e) => {{
                        if (e.button === 0) {{
                            isDragging = true;
                            const rect = canvas.getBoundingClientRect();
                            lastMouseX = e.clientX - rect.left;
                            lastMouseY = e.clientY - rect.top;
                            minimap.classList.add('dragging');
                            e.preventDefault();
                        }}
                    }});
                    
                    canvas.addEventListener('mousemove', handleMinimapDrag);
                    
                    function stopDragging() {{
                        if (isDragging) {{
                            isDragging = false;
                            minimap.classList.remove('dragging');
                        }}
                    }}
                    
                    canvas.addEventListener('mouseup', stopDragging);
                    canvas.addEventListener('mouseleave', stopDragging);
                    
                    // Expose functions for external control
                    minimap._minimapControls = {{
                        updateMinimapBounds: updateMinimapBounds,
                        updateContentBounds: updateContentBounds,
                        updateViewport: updateViewport,
                        drawMinimap: drawMinimap
                    }};
                    
                    // Initial draw
                    drawMinimap();
                }}
                
                initializeMinimap();
            }})();
        """

        ui.run_javascript(script)

    def _hook_zoom_container_events(self) -> None:
        """Hook into the zoom container's events to update minimap."""
        # Store original callbacks
        original_zoom_callback = self.zoom_container.on_zoom_change
        original_pan_callback = self.zoom_container.on_pan_change

        def zoom_callback(zoom):
            self._update_viewport()
            if original_zoom_callback:
                original_zoom_callback(zoom)

        def pan_callback(x, y):
            self._update_viewport()
            if original_pan_callback:
                original_pan_callback(x, y)

        # Replace the container's callbacks
        self.zoom_container.on_zoom_change = zoom_callback
        self.zoom_container.on_pan_change = pan_callback

    def _scan_content(self) -> None:
        """Scan the zoom container content to build minimap representation."""
        # Calculate aspect ratio first
        self._apply_zoom_container_ratio(self.minimap_width)
        # Scan content
        ui.run_javascript(f"""
            const container = document.getElementById('{self.zoom_container.container_id}');
            const content = container ? container.querySelector('.zoom-pan-content') : null;
            
            if (content) {{
                // Get current transform values
                const transform = content.style.transform;
                let currentZoom = 1.0;
                let currentPanX = 0;
                let currentPanY = 0;
                
                // Parse current transform to get actual zoom/pan values
                if (transform) {{
                    const translateMatch = transform.match(/translate\\(([^,]+),\\s*([^)]+)\\)/);
                    const scaleMatch = transform.match(/scale\\(([^)]+)\\)/);
                    
                    if (translateMatch) {{
                        currentPanX = parseFloat(translateMatch[1]) || 0;
                        currentPanY = parseFloat(translateMatch[2]) || 0;
                    }}
                    if (scaleMatch) {{
                        currentZoom = parseFloat(scaleMatch[1]) || 1.0;
                    }}
                }}
                
                // Get all meaningful content elements
                const elements = content.querySelectorAll(
                    '.zoomable-card, .card, [class*="card"], [class*="item"]'
                );
                
                let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
                
                if (elements.length > 0) {{
                    elements.forEach(el => {{
                        const rect = el.getBoundingClientRect();
                        const containerRect = container.getBoundingClientRect();
                        
                        // Convert screen coordinates to content coordinates
                        // Account for current transform: screen_pos = (content_pos * zoom) + pan
                        // So: content_pos = (screen_pos - pan) / zoom
                        const screenX = rect.left - containerRect.left;
                        const screenY = rect.top - containerRect.top;
                        
                        const contentX = (screenX - currentPanX) / currentZoom;
                        const contentY = (screenY - currentPanY) / currentZoom;
                        const contentWidth = rect.width / currentZoom;
                        const contentHeight = rect.height / currentZoom;
                        
                        minX = Math.min(minX, contentX);
                        minY = Math.min(minY, contentY);
                        maxX = Math.max(maxX, contentX + contentWidth);
                        maxY = Math.max(maxY, contentY + contentHeight);
                    }});
                }} else {{
                    // Fallback: assume a reasonable content area
                    minX = -500;
                    minY = -500;
                    maxX = 2000;
                    maxY = 2000;
                }}
                
                // Add padding in content coordinates
                const padding = 100;
                minX -= padding;
                minY -= padding;
                maxX += padding;
                maxY += padding;
                
                const bounds = {{ minX, minY, maxX, maxY }};
                
                const minimap = document.getElementById('{self.minimap_id}');
                if (minimap && minimap._minimapControls) {{
                    minimap._minimapControls.updateContentBounds(bounds);
                }}
            }}
        """)

        # Schedule periodic content rescanning
        ui.timer(5.0, self._scan_content, once=True)

    def _apply_zoom_container_ratio(self, width: int) -> None:
        """Calculate minimap height based on zoom container's aspect ratio."""
        script = f"""
                const container = document.getElementById('{self.zoom_container.container_id}');
                if (container) {{
                    const rect = container.getBoundingClientRect();
                    const aspectRatio = rect.height / rect.width;
                    const newHeight = Math.round({width} * aspectRatio);
                    
                    // Update the minimap size
                    const minimap = document.getElementById('{self.minimap_id}');
                    const canvas = document.getElementById('{self.canvas_id}');
                    
                    if (minimap && canvas) {{
                        minimap.style.height = newHeight + 'px';
                        canvas.style.height = '100%';
                        canvas.height = newHeight;

                        minimap._minimapControls.updateMinimapBounds({width});
                    }}
                }}
            """
        _ = ui.run_javascript(script)

    def _update_viewport(self) -> None:
        """Update the viewport indicator in the minimap."""
        ui.run_javascript(f"""
            const minimap = document.getElementById('{self.minimap_id}');
            const mainContainer = document.getElementById('{self.zoom_container.container_id}');
            
            if (minimap && minimap._minimapControls && 
                mainContainer && mainContainer._zoomPanControls) {{
                const currentZoom = mainContainer._zoomPanControls.getZoom();
                const currentPan = mainContainer._zoomPanControls.getPan();
                
                minimap._minimapControls.updateViewport(currentZoom, currentPan.x, currentPan.y);
            }}
        """)

    def toggle_visibility(self) -> None:
        """Toggle minimap visibility."""
        self.is_visible = not self.is_visible
        if self.is_visible:
            self.style(remove="display: none;")
            self.toggle_btn.set_text("×")
            # Rescan content when showing
            ui.timer(0.1, self._scan_content, once=True)
        else:
            self.style(add="display: none;")
            self.toggle_btn.set_text("◐")

    def set_position(self, position: str) -> None:
        """Change minimap position."""
        self.position = position
        position_styles = {
            "top-right": "top: 10px; right: 10px; bottom: auto; left: auto;",
            "top-left": "top: 10px; left: 10px; bottom: auto; right: auto;",
            "bottom-right": "bottom: 10px; right: 10px; top: auto; left: auto;",
            "bottom-left": "bottom: 10px; left: 10px; top: auto; right: auto;",
        }

        ui.run_javascript(f"""
            const minimap = document.getElementById('{self.minimap_id}');
            if (minimap) {{
                minimap.style.top = 'auto';
                minimap.style.right = 'auto';
                minimap.style.bottom = 'auto';
                minimap.style.left = 'auto';
                minimap.style.cssText += \n'{position_styles.get(position, position_styles["top-right"])}';
            }}
        """)

    def refresh_content(self) -> None:
        """Force refresh of content scanning."""
        self._scan_content()

from nicegui import ui
import uuid

from ..pan_zoom.zoom_pan_vue import ZoomPanContainer


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
        debug_info: bool = False,
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
        self.debug_info = debug_info

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
                    let nodeRects = [];
                    let showDebugInfo = {str(self.debug_info).lower()};
                    
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
                        // Derive height from the canvas aspect ratio (contentBounds),
                        // not the viewport — so it stays correct when the canvas resizes.
                        const cw = contentBounds.maxX - contentBounds.minX;
                        const ch = contentBounds.maxY - contentBounds.minY;
                        minimap_height = (cw > 0 && ch > 0)
                            ? Math.round(width * ch / cw)
                            : width; // fallback to square if bounds not yet known
                        minimap_content_width = minimap_width - (MINIMAP_PADDING * 2);
                        minimap_content_height = minimap_height - (MINIMAP_PADDING * 2);
                        // Resize the DOM elements to match.
                        minimap.style.height = minimap_height + 'px';
                        canvas.style.height = '100%';
                        canvas.height = minimap_height;
                    }}
                    
                    function updateContentBounds(bounds, nodes) {{
                        contentBounds = bounds;
                        nodeRects = nodes || [];
                        contentWidth = contentBounds.maxX - contentBounds.minX;
                        contentHeight = contentBounds.maxY - contentBounds.minY;

                        // Re-derive minimap height from canvas aspect ratio.
                        updateMinimapBounds(minimap_width);

                        // Calculate scale to fit content in minimap
                        const scaleX = minimap_content_width / contentWidth;
                        const scaleY = minimap_content_height / contentHeight;
                        scaleFactor = Math.min(scaleX, scaleY, 1.0); // Don't scale up

                        drawMinimap();
                    }}
                    
                    function updateViewport(_zoom, _panX, _panY) {{
                        zoom = _zoom;
                        panX = _panX;
                        panY = _panY;

                        if (!mainContainer) return;

                        const containerRect = mainContainer.getBoundingClientRect();

                        // Content coordinates of the viewport top-left:
                        // transform is translate(panX, panY) scale(zoom)
                        // so screen(0,0) → content(-panX/zoom, -panY/zoom)
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
                        
                        // Draw node rectangles
                        ctx.fillStyle = '{self.content_color}';
                        nodeRects.forEach(n => {{
                            const nx = MINIMAP_PADDING + (n.x - contentBounds.minX) * scaleFactor;
                            const ny = MINIMAP_PADDING + (n.y - contentBounds.minY) * scaleFactor;
                            const nw = Math.max(2, n.w * scaleFactor);
                            const nh = Math.max(2, n.h * scaleFactor);
                            ctx.fillRect(nx, ny, nw, nh);
                        }});
                        
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

                        // Debug overlay
                        if (showDebugInfo) {{
                            ctx.fillStyle = 'rgba(0,0,0,0.65)';
                            ctx.fillRect(0, minimap_height - 80, minimap_width, 80);
                            ctx.fillStyle = '#fff';
                            ctx.font = '9px monospace';
                            const lines = [
                                `zoom: ${{zoom.toFixed(3)}}`,
                                `pan:  ${{panX.toFixed(0)}}, ${{panY.toFixed(0)}}`,
                                `view: ${{Math.round(clampedWidth)}} x ${{Math.round(clampedHeight)}}`,
                                `scale: ${{scaleFactor.toFixed(4)}}`,
                                `canvas: ${{Math.round(contentBounds.maxX)}}`
                                    + ` x ${{Math.round(contentBounds.maxY)}}`,
                            ];
                            lines.forEach((line, i) => {{
                                ctx.fillText(line, 4, minimap_height - 80 + 11 + i * 13);
                            }});
                        }}
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
                        drawMinimap: drawMinimap,
                        setDebugInfo: (enabled) => {{
                            showDebugInfo = enabled;
                            drawMinimap();
                        }},
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
        """Scan node positions for minimap drawing.
        Canvas bounds are fixed at [0, 8000] to match GraphCanvasVue's physical size,
        so the viewport rectangle always reflects the true navigable space.
        """
        self._apply_zoom_container_ratio(self.minimap_width)
        ui.run_javascript(f"""
            const container = document.getElementById('{self.zoom_container.container_id}');
            const content = container ? container.querySelector('.zoom-pan-content') : null;

            if (content) {{
                // Fixed bounds matching GraphCanvasVue's 8000x8000 CSS size.
                const bounds = {{ minX: 0, minY: 0, maxX: 8000, maxY: 8000 }};

                // Node rects in content-space (inline style left/top set by graph_canvas_manager).
                const nodes = [];
                content.querySelectorAll('[data-node-id]').forEach(el => {{
                    const x = parseFloat(el.style.left) || 0;
                    const y = parseFloat(el.style.top) || 0;
                    nodes.push({{ x, y, w: el.offsetWidth, h: el.offsetHeight }});
                }});

                const minimap = document.getElementById('{self.minimap_id}');
                if (minimap && minimap._minimapControls) {{
                    minimap._minimapControls.updateContentBounds(bounds, nodes);
                }}
            }}
        """)

        # Schedule periodic content rescanning
        ui.timer(5.0, self._scan_content, once=True)

    def _apply_zoom_container_ratio(self, width: int) -> None:
        """Resize the minimap to match the canvas aspect ratio.
        The ratio is derived from the content bounds already known to the minimap JS,
        so it stays correct when the canvas size changes (e.g. auto-expand).
        """
        ui.run_javascript(f"""
            const minimap = document.getElementById('{self.minimap_id}');
            const canvas = document.getElementById('{self.canvas_id}');
            if (minimap && canvas && minimap._minimapControls) {{
                minimap._minimapControls.updateMinimapBounds({width});
            }}
        """)

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
            ui.timer(0.1, self._scan_content, once=True)
        else:
            self.style(add="display: none;")

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

    def set_enabled(self, enabled: bool) -> None:
        """Show or hide the minimap."""
        if enabled != self.is_visible:
            self.toggle_visibility()

    def set_width(self, width: int) -> None:
        """Update the minimap width and re-derive height from the container aspect ratio."""
        self.minimap_width = width
        ui.run_javascript(f"""
            const minimap = document.getElementById('{self.minimap_id}');
            const canvas = document.getElementById('{self.canvas_id}');
            if (minimap && canvas) {{
                minimap.style.width = '{width}px';
                canvas.width = {width};
            }}
        """)
        self._apply_zoom_container_ratio(width)

    def set_debug_info(self, enabled: bool) -> None:
        """Toggle debug overlay on the minimap canvas."""
        self.debug_info = enabled
        ui.run_javascript(f"""
            const minimap = document.getElementById('{self.minimap_id}');
            if (minimap && minimap._minimapControls) {{
                minimap._minimapControls.setDebugInfo({str(enabled).lower()});
            }}
        """)

    def refresh_content(self) -> None:
        """Force refresh of content scanning."""
        self._scan_content()

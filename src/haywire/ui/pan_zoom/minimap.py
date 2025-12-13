from nicegui import ui
import uuid


class MinimapCanvas(ui.element):
    """
    A canvas-based minimap for the ZoomPanContainer that shows an overview
    of the content and current viewport position.
    
    This is a cleaned-up version of your original approach that works with
    NiceGUI elements and JavaScript injection.
    """
    
    def __init__(
        self,
        zoom_container,
        width: int = 200,
        height: int = 150,
        position: str = 'top-right',
        background_color: str = '#f0f0f0',
        content_color: str = '#4285f4',
        viewport_color: str = '#ea4335',
        visible: bool = True,
        **kwargs
    ) -> None:
        super().__init__('div', **kwargs)
        
        # Store references and configuration
        self.zoom_container = zoom_container
        self.minimap_width = width
        self.minimap_height = height
        self.position = position
        self.background_color = background_color
        self.content_color = content_color
        self.viewport_color = viewport_color
        self.is_visible = visible
        
        # Generate unique IDs
        self.minimap_id = f'minimap-{uuid.uuid4().hex[:8]}'
        self.canvas_id = f'canvas-{uuid.uuid4().hex[:8]}'
        
        # Setup the minimap structure
        self._setup_minimap()
        self._inject_styles()
        
        # Initialize after DOM is ready
        ui.timer(0.1, self._inject_script, once=True)
        ui.timer(0.5, self._scan_content, once=True)
        
        # Hook into zoom container events
        ui.timer(0.6, self._hook_zoom_container_events, once=True)
    
    def _setup_minimap(self) -> None:
        """Setup the minimap container structure."""
        self.classes('minimap-container')
        
        # Position styles
        position_styles = {
            'top-right': 'top: 10px; right: 10px;',
            'top-left': 'top: 10px; left: 10px;',
            'bottom-right': 'bottom: 10px; right: 10px;',
            'bottom-left': 'bottom: 10px; left: 10px;'
        }
        
        style = (
            f'position: absolute; '
            f'width: {self.minimap_width}px; '
            f'height: {self.minimap_height}px; '
            f'z-index: 1001; '
            f'border: 2px solid #ccc; '
            f'border-radius: 6px; '
            f'background: {self.background_color}; '
            f'box-shadow: 0 2px 8px rgba(0,0,0,0.2); '
            f'cursor: crosshair; '
            f'{position_styles.get(self.position, position_styles["top-right"])} '
            f'{"" if self.is_visible else "display: none;"}'
        )
        
        self.style(style)
        self.props(f'id="{self.minimap_id}"')
        
        # Create canvas and toggle button
        with self:
            self.canvas = ui.element('canvas')
            self.canvas.props(
                f'id="{self.canvas_id}" '
                f'width="{self.minimap_width}" '
                f'height="{self.minimap_height}"'
            )
            self.canvas.style('display: block; width: 100%; height: 100%;')
            
            self.toggle_btn = ui.button(
                '×',
                on_click=self.toggle_visibility
            ).props('round dense size=xs')
            self.toggle_btn.style(
                'position: absolute; top: -8px; right: -8px; '
                'width: 16px; height: 16px; min-width: 16px;'
            )
            self.toggle_btn.classes('bg-gray-600 text-white text-xs')

    def _inject_styles(self) -> None:
        """Inject CSS styles for the minimap."""
        ui.add_css('''
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
        ''')
    
    def _inject_script(self) -> None:
        """Inject JavaScript for minimap functionality."""
        script = f'''
            (function() {{
                const minimap = document.getElementById('{self.minimap_id}');
                const canvas = document.getElementById('{self.canvas_id}');
                
                if (!minimap || !canvas) {{
                    console.error('Minimap elements not found');
                    return;
                }}
                
                const ctx = canvas.getContext('2d');
                let isDragging = false;
                let lastMouseX = 0;
                let lastMouseY = 0;
                
                // Minimap state
                let contentBounds = {{ minX: -500, minY: -500, maxX: 2000, maxY: 2000 }};
                let scaleFactor = 1.0;
                let viewportRect = {{ x: 0, y: 0, width: 50, height: 50 }};
                
                const MINIMAP_PADDING = 10;
                const MINIMAP_CONTENT_WIDTH = {self.minimap_width} - (MINIMAP_PADDING * 2);
                const MINIMAP_CONTENT_HEIGHT = {self.minimap_height} - (MINIMAP_PADDING * 2);
                
                function updateContentBounds(bounds) {{
                    contentBounds = bounds;
                    const contentWidth = contentBounds.maxX - contentBounds.minX;
                    const contentHeight = contentBounds.maxY - contentBounds.minY;
                    
                    const scaleX = MINIMAP_CONTENT_WIDTH / contentWidth;
                    const scaleY = MINIMAP_CONTENT_HEIGHT / contentHeight;
                    scaleFactor = Math.min(scaleX, scaleY, 1.0);
                    
                    drawMinimap();
                }}
                
                function updateViewport(zoom, panX, panY) {{
                    const mainContainer = document.getElementById(
                        '{self.zoom_container.container_id}'
                    );
                    if (!mainContainer) return;
                    
                    const containerRect = mainContainer.getBoundingClientRect();
                    const viewWidth = containerRect.width / zoom;
                    const viewHeight = containerRect.height / zoom;
                    const viewX = -panX / zoom;
                    const viewY = -panY / zoom;
                    
                    const minimapX = MINIMAP_PADDING + (viewX - contentBounds.minX) * scaleFactor;
                    const minimapY = MINIMAP_PADDING + (viewY - contentBounds.minY) * scaleFactor;
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
                    ctx.clearRect(0, 0, {self.minimap_width}, {self.minimap_height});
                    
                    // Draw background
                    ctx.fillStyle = '{self.background_color}';
                    ctx.fillRect(0, 0, {self.minimap_width}, {self.minimap_height});
                    
                    // Draw content area
                    const boundsX = MINIMAP_PADDING;
                    const boundsY = MINIMAP_PADDING;
                    const boundsWidth = (contentBounds.maxX - contentBounds.minX) * scaleFactor;
                    const boundsHeight = (contentBounds.maxY - contentBounds.minY) * scaleFactor;
                    
                    ctx.fillStyle = '#fafafa';
                    ctx.fillRect(boundsX, boundsY, boundsWidth, boundsHeight);
                    
                    ctx.strokeStyle = '#ddd';
                    ctx.lineWidth = 1;
                    ctx.strokeRect(boundsX, boundsY, boundsWidth, boundsHeight);
                    
                    // Draw content representation
                    ctx.fillStyle = '{self.content_color}';
                    const gridSize = Math.max(1, Math.min(4, 20 * scaleFactor));
                    const gridSpacing = Math.max(gridSize * 2, 8);
                    
                    for (let x = boundsX; x < boundsX + boundsWidth; x += gridSpacing) {{
                        for (let y = boundsY; y < boundsY + boundsHeight; y += gridSpacing) {{
                            if (x + gridSize <= boundsX + boundsWidth && 
                                y + gridSize <= boundsY + boundsHeight) {{
                                ctx.fillRect(x, y, gridSize, gridSize);
                            }}
                        }}
                    }}
                    
                    // Draw viewport rectangle
                    ctx.strokeStyle = '{self.viewport_color}';
                    ctx.fillStyle = '{self.viewport_color}33';
                    ctx.lineWidth = 2;
                    
                    const clampedX = Math.max(0, Math.min(viewportRect.x, {self.minimap_width}));
                    const clampedY = Math.max(0, Math.min(viewportRect.y, {self.minimap_height}));
                    const clampedWidth = Math.max(
                        1, 
                        Math.min(viewportRect.width, {self.minimap_width} - clampedX)
                    );
                    const clampedHeight = Math.max(
                        1, 
                        Math.min(viewportRect.height, {self.minimap_height} - clampedY)
                    );
                    
                    ctx.fillRect(clampedX, clampedY, clampedWidth, clampedHeight);
                    ctx.strokeRect(clampedX, clampedY, clampedWidth, clampedHeight);
                }}
                
                function minimapToContent(minimapX, minimapY) {{
                    const contentX = contentBounds.minX + 
                        (minimapX - MINIMAP_PADDING) / scaleFactor;
                    const contentY = contentBounds.minY + 
                        (minimapY - MINIMAP_PADDING) / scaleFactor;
                    return {{ x: contentX, y: contentY }};
                }}
                
                // Event handlers
                canvas.addEventListener('click', (e) => {{
                    const rect = canvas.getBoundingClientRect();
                    const minimapX = e.clientX - rect.left;
                    const minimapY = e.clientY - rect.top;
                    const contentPos = minimapToContent(minimapX, minimapY);
                    
                    const mainContainer = document.getElementById(
                        '{self.zoom_container.container_id}'
                    );
                    if (mainContainer && mainContainer._zoomPanControls) {{
                        const containerRect = mainContainer.getBoundingClientRect();
                        const currentZoom = mainContainer._zoomPanControls.getZoom();
                        const newPanX = -(contentPos.x * currentZoom - containerRect.width / 2);
                        const newPanY = -(contentPos.y * currentZoom - containerRect.height / 2);
                        mainContainer._zoomPanControls.setPan(newPanX, newPanY);
                    }}
                }});
                
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
                
                canvas.addEventListener('mousemove', (e) => {{
                    if (!isDragging) return;
                    
                    const rect = canvas.getBoundingClientRect();
                    const currentX = e.clientX - rect.left;
                    const currentY = e.clientY - rect.top;
                    const deltaX = currentX - lastMouseX;
                    const deltaY = currentY - lastMouseY;
                    
                    const contentDeltaX = deltaX / scaleFactor;
                    const contentDeltaY = deltaY / scaleFactor;
                    
                    const mainContainer = document.getElementById('{self.zoom_container.container_id}');
                    if (mainContainer && mainContainer._zoomPanControls) {{
                        const currentPan = mainContainer._zoomPanControls.getPan();
                        const currentZoom = mainContainer._zoomPanControls.getZoom();
                        const newPanX = currentPan.x - contentDeltaX * currentZoom;
                        const newPanY = currentPan.y - contentDeltaY * currentZoom;
                        mainContainer._zoomPanControls.setPan(newPanX, newPanY);
                    }}
                    
                    lastMouseX = currentX;
                    lastMouseY = currentY;
                }});
                
                function stopDragging() {{
                    if (isDragging) {{
                        isDragging = false;
                        minimap.classList.remove('dragging');
                    }}
                }}
                
                canvas.addEventListener('mouseup', stopDragging);
                canvas.addEventListener('mouseleave', stopDragging);
                
                // Expose functions
                minimap._minimapControls = {{
                    updateContentBounds: updateContentBounds,
                    updateViewport: updateViewport,
                    drawMinimap: drawMinimap
                }};
                
                // Initial draw
                drawMinimap();
            }})();
        '''
        
        ui.run_javascript(script)
    
    def _scan_content(self) -> None:
        """Scan content and update minimap bounds."""
        ui.run_javascript(f'''
            const container = document.getElementById(
                '{self.zoom_container.container_id}'
            );
            const content = container ? container.querySelector('.zoom-pan-content') : null;
            
            if (content) {{
                // Scan content and update bounds
                const elements = content.querySelectorAll(
                    '.zoomable-card, .card, [class*="card"], [class*="item"]'
                );
                
                let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
                
                if (elements.length > 0) {{
                    elements.forEach(el => {{
                        const rect = el.getBoundingClientRect();
                        const containerRect = container.getBoundingClientRect();
                        
                        // Convert to content coordinates
                        const transform = content.style.transform;
                        let currentZoom = 1.0;
                        let currentPanX = 0;
                        let currentPanY = 0;
                        
                        if (transform) {{
                            const translateMatch = transform.match(
                                /translate\\(([^,]+),\\s*([^)]+)\\)/
                            );
                            const scaleMatch = transform.match(/scale\\(([^)]+)\\)/);
                            
                            if (translateMatch) {{
                                currentPanX = parseFloat(translateMatch[1]) || 0;
                                currentPanY = parseFloat(translateMatch[2]) || 0;
                            }}
                            if (scaleMatch) {{
                                currentZoom = parseFloat(scaleMatch[1]) || 1.0;
                            }}
                        }}
                        
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
                    minX = -500;
                    minY = -500;
                    maxX = 2000;
                    maxY = 2000;
                }}
                
                const padding = 100;
                const bounds = {{
                    minX: minX - padding,
                    minY: minY - padding,
                    maxX: maxX + padding,
                    maxY: maxY + padding
                }};
                
                const minimap = document.getElementById('{self.minimap_id}');
                if (minimap && minimap._minimapControls) {{
                    minimap._minimapControls.updateContentBounds(bounds);
                }}
            }}
        ''')
        
        # Schedule next scan
        ui.timer(5.0, self._scan_content, once=True)
    
    def toggle_visibility(self) -> None:
        """Toggle minimap visibility."""
        self.is_visible = not self.is_visible
        if self.is_visible:
            self.style(remove='display: none;')
            self.toggle_btn.set_text('×')
            ui.timer(0.1, self._scan_content, once=True)
        else:
            self.style(add='display: none;')
            self.toggle_btn.set_text('◐')
    
    def set_position(self, position: str) -> None:
        """Change minimap position."""
        self.position = position
        position_styles = {
            'top-right': 'top: 10px; right: 10px; bottom: auto; left: auto;',
            'top-left': 'top: 10px; left: 10px; bottom: auto; right: auto;',
            'bottom-right': 'bottom: 10px; right: 10px; top: auto; left: auto;',
            'bottom-left': 'bottom: 10px; left: 10px; top: auto; right: auto;'
        }
        
        ui.run_javascript(f'''
            const minimap = document.getElementById('{self.minimap_id}');
            if (minimap) {{
                minimap.style.cssText += 
                    '{position_styles.get(position, position_styles["top-right"])}';
            }}
        ''')
    
    def refresh_content(self) -> None:
        """Force refresh of content scanning."""
        self._scan_content()
    
    def _hook_zoom_container_events(self) -> None:
        """Hook into the zoom container's events to update minimap."""
        # Store original callbacks
        original_zoom_callback = getattr(self.zoom_container, 'on_zoom_change', None)
        original_pan_callback = getattr(self.zoom_container, 'on_pan_change', None)
        
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
    
    def _update_viewport(self) -> None:
        """Update the viewport indicator in the minimap."""
        ui.run_javascript(f'''
            const minimap = document.getElementById('{self.minimap_id}');
            const mainContainer = document.getElementById('{self.zoom_container.container_id}');
            
            if (minimap && minimap._minimapControls && 
                mainContainer && mainContainer._zoomPanControls) {{
                const currentZoom = mainContainer._zoomPanControls.getZoom();
                const currentPan = mainContainer._zoomPanControls.getPan();
                
                minimap._minimapControls.updateViewport(currentZoom, currentPan.x, currentPan.y);
            }}
        ''')
        
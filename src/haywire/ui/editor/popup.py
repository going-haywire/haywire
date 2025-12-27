from nicegui import ui
from typing import Optional, Callable


class Popup:
    """
    A reusable popup component for NiceGUI with drag support.
    """
    
    _css_added = False
    _global_handlers_initialized = False
    
    @classmethod
    def _ensure_css(cls):
        if not cls._css_added:
            ui.add_css('''
                .popup-overlay { z-index: 5000 !important; }
                
                .popup-card {
                    z-index: 5001 !important;
                    pointer-events: auto !important;
                }
                
                .popup-content-area {
                    user-select: text !important;
                    -webkit-user-select: text !important;
                    cursor: auto;
                    pointer-events: auto !important;
                }
                .popup-content-area * { user-select: text !important; }
                .popup-content-area button, .popup-content-area .q-btn,
                .popup-content-area .q-item, .popup-content-area [role="button"] {
                    user-select: none !important;
                    cursor: pointer !important;
                }
                .popup-content-area input, .popup-content-area textarea {
                    user-select: text !important;
                    cursor: text !important;
                }
                .popup-title-bar {
                    user-select: none !important;
                    cursor: move !important;
                    pointer-events: auto !important;
                }
                .popup-title-bar.not-draggable { cursor: default !important; }
                .popup-title-bar button { cursor: pointer !important; }
                .popup-card.popup-dragging {
                    opacity: 0.95;
                    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3) !important;
                }
            ''')
            cls._css_added = True
        
    @classmethod
    def _ensure_global_handlers(cls):
        """Setup global drag handlers once."""
        
        script = '''
        (function() {
            // Don't re-initialize if already set up - preserve state!
            if (window._popupGlobalHandlersSetup) {
                console.log('Popup: Handlers already initialized, skipping');
                return;
            }
            window._popupGlobalHandlersSetup = true;
            
            window._popupDragState = null;
            // Use existing positions if they exist (persist across re-init)
            window._popupPositions = window._popupPositions || {};
            window._popupAnimationFrames = window._popupAnimationFrames || {};
            
            function enforcePosition(containerId) {
                const container = document.getElementById(containerId);
                const pos = window._popupPositions[containerId];
                
                if (!pos) {
                    // No position stored - stop the loop
                    if (window._popupAnimationFrames[containerId]) {
                        cancelAnimationFrame(window._popupAnimationFrames[containerId]);
                        delete window._popupAnimationFrames[containerId];
                    }
                    return;
                }
                
                if (!container) {
                    // Container temporarily missing - keep trying but don't clear position!
                    // This handles the case where NiceGUI re-renders components
                    window._popupAnimationFrames[containerId] = requestAnimationFrame(() => enforcePosition(containerId));
                    return;
                }
                
                // Apply position
                container.style.setProperty('position', 'fixed', 'important');
                container.style.setProperty('left', pos.x + 'px', 'important');
                container.style.setProperty('top', pos.y + 'px', 'important');
                container.style.setProperty('margin', '0', 'important');
                container.style.setProperty('transform', 'none', 'important');
                
                window._popupAnimationFrames[containerId] = requestAnimationFrame(() => enforcePosition(containerId));
            }
            
            window._startPopupPositionEnforcement = function(containerId, initialX, initialY) {
                // Only set initial position if not already stored
                if (!window._popupPositions[containerId]) {
                    console.log('Setting initial position:', containerId, initialX, initialY);
                    window._popupPositions[containerId] = { x: initialX, y: initialY };
                } else {
                    console.log('Using existing position:', containerId, window._popupPositions[containerId]);
                }
                
                const pos = window._popupPositions[containerId];
                const container = document.getElementById(containerId);
                if (container) {
                    container.style.setProperty('position', 'fixed', 'important');
                    container.style.setProperty('left', pos.x + 'px', 'important');
                    container.style.setProperty('top', pos.y + 'px', 'important');
                    container.style.setProperty('margin', '0', 'important');
                    container.style.setProperty('transform', 'none', 'important');
                    container.style.setProperty('max-width', '90vw', 'important');
                    container.style.setProperty('max-height', '90vh', 'important');
                    container.style.setProperty('overflow', 'auto', 'important');
                    container.style.setProperty('z-index', '5001', 'important');
                    container.style.setProperty('pointer-events', 'auto', 'important');
                }
                
                // Start loop if not already running
                if (!window._popupAnimationFrames[containerId]) {
                    enforcePosition(containerId);
                }
            };
            
            window._stopPopupPositionEnforcement = function(containerId) {
                console.log('Stopping enforcement (keeping position):', containerId);
                if (window._popupAnimationFrames[containerId]) {
                    cancelAnimationFrame(window._popupAnimationFrames[containerId]);
                    delete window._popupAnimationFrames[containerId];
                }
                // DON'T delete position - it may be needed if popup is re-rendered
            };
            
            window._cleanupPopupPosition = function(containerId) {
                console.log('Cleanup position:', containerId);
                if (window._popupAnimationFrames[containerId]) {
                    cancelAnimationFrame(window._popupAnimationFrames[containerId]);
                    delete window._popupAnimationFrames[containerId];
                }
                delete window._popupPositions[containerId];
            };
            
            document.addEventListener('mousemove', function(e) {
                const state = window._popupDragState;
                if (!state || !state.isDragging) return;
                
                const container = document.getElementById(state.containerId);
                if (!container) return;
                
                const dx = e.clientX - state.startX;
                const dy = e.clientY - state.startY;
                
                let newX = state.initialX + dx;
                let newY = state.initialY + dy;
                
                newX = Math.max(0, Math.min(newX, window.innerWidth - container.offsetWidth));
                newY = Math.max(0, Math.min(newY, window.innerHeight - container.offsetHeight));
                
                window._popupPositions[state.containerId] = { x: newX, y: newY };
                
                container.style.setProperty('left', newX + 'px', 'important');
                container.style.setProperty('top', newY + 'px', 'important');
                
                e.preventDefault();
            }, true);
            
            document.addEventListener('mouseup', function(e) {
                const state = window._popupDragState;
                if (!state || !state.isDragging) return;
                
                const finalPos = window._popupPositions[state.containerId];
                console.log('Drag ended, final position:', finalPos);
                
                const container = document.getElementById(state.containerId);
                if (container) {
                    container.classList.remove('popup-dragging');
                }
                
                if (finalPos) {
                    emitEvent('popup_position_update', {
                        containerId: state.containerId,
                        x: finalPos.x,
                        y: finalPos.y
                    });
                }
                
                window._popupDragState = null;
            }, true);
            
            console.log('Popup: Global handlers initialized');
        })();
        '''
        ui.run_javascript(script)
        cls._global_handlers_initialized = True

    # Class-level registry of popup instances by container ID
    _instances = {}

    def __init__(self, 
                 title: Optional[str] = None,
                 width: str = "auto",
                 height: str = "auto",
                 closable: bool = False,
                 backdrop_click_close: bool = False,
                 escape_close: bool = False,
                 backdrop_color: str = "rgba(0,0,0,0.5)",
                 position_x: Optional[float] = None,
                 position_y: Optional[float] = None,
                 draggable: bool = False):
        self._ensure_css()
        
        self.title = title
        self.width = width
        self.height = height
        self.closable = closable
        self.backdrop_click_close = backdrop_click_close
        self.escape_close = escape_close
        self.backdrop_color = backdrop_color
        self.position_x = position_x
        self.position_y = position_y
        self.draggable = draggable
        self._popup_element = None
        self._content_container = None
        self._content_area = None
        self._title_row = None
        self._backdrop = None
        self._is_open = False
        self._on_close_callback = None
        self._event_listener = None
        
    def __enter__(self):
        if self._popup_element is not None:
            raise RuntimeError("Popup is already created")
        
        with ui.context.client.layout:
            self._create_popup_structure()
        
        self._content_area.__enter__()
        return self._content_area
    
    def _create_popup_structure(self):
        if self.position_x is not None and self.position_y is not None:
            popup_style = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: transparent; z-index: 5000; display: none; pointer-events: none;'
            content_style = f'min-width: {self.width}; height: {self.height}; max-width: 90vw; max-height: 90vh; overflow: auto; z-index: 5001; pointer-events: auto;'
            backdrop_style = 'position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; background: transparent; pointer-events: auto;'
        else:
            popup_style = f'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: {self.backdrop_color}; z-index: 5000; display: none; align-items: center; justify-content: center; backdrop-filter: blur(2px); pointer-events: auto;'
            content_style = f'min-width: {self.width}; height: {self.height}; max-width: 90vw; max-height: 90vh; overflow: auto; margin: 20px; position: relative; z-index: 5001; pointer-events: auto;'
            backdrop_style = 'position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: -1; pointer-events: auto;'
        
        self._popup_element = ui.element('div').style(popup_style)
        self._popup_element.classes('popup-overlay')
        self._popup_element._props['data-popup'] = 'true'
        
        with self._popup_element:
            if self.backdrop_click_close:
                self._backdrop = ui.element('div').style(backdrop_style)
                self._backdrop.classes('popup-backdrop')
                self._backdrop.on('click', self._handle_backdrop_click)
            
            self._content_container = ui.card().style(content_style)
            self._content_container.classes('popup-card interactive')
            self._content_container._props['data-interactive'] = 'true'
            self._content_container._props['data-popup-container'] = 'true'
            
            # STOP CLICK PROPAGATION on the content container!
            self._content_container.on('click', lambda e: None, js_handler='(e) => e.stopPropagation()')

            with self._content_container:
                if self.title or self.closable:
                    title_bar_classes = 'popup-title-bar' if self.draggable else 'popup-title-bar not-draggable'
                    self._title_row = ui.row().classes(f'w-full justify-between items-center mb-2 {title_bar_classes}')
                    self._title_row._props['data-popup-drag-handle'] = 'true'
                    
                    with self._title_row:
                        if self.title:
                            ui.label(self.title).style('font-size: 1.1em; font-weight: 600; pointer-events: none;')
                        else:
                            ui.element('div')
                            
                        if self.closable:
                            ui.button(icon='close', on_click=self.close).props('flat round size=sm')
                    
                    if self.title:
                        ui.separator()
                    
                    if self.draggable:
                        self._setup_drag_handler()
                
                self._content_area = ui.column().classes('popup-content-area w-full interactive')
                self._content_area._props['data-interactive'] = 'true'
    
    def _setup_drag_handler(self):
        """Setup drag handler on title bar."""
        if not self._title_row or not self._content_container:
            return
        
        container_id = self._content_container.id
        
        self._title_row.on(
            'mousedown',
            js_handler=f'''(e) => {{
                if (e.target.closest('button, .q-btn')) return;
                if (document.querySelector('.q-menu')) return;
                
                const container = document.getElementById('c{container_id}');
                if (!container) return;
                
                const pos = window._popupPositions && window._popupPositions['c{container_id}'];
                let currentX, currentY;
                
                if (pos) {{
                    currentX = pos.x;
                    currentY = pos.y;
                }} else {{
                    const rect = container.getBoundingClientRect();
                    currentX = rect.left;
                    currentY = rect.top;
                }}
                
                console.log('Drag starting from:', currentX, currentY);
                
                window._popupDragState = {{
                    isDragging: true,
                    containerId: 'c{container_id}',
                    startX: e.clientX,
                    startY: e.clientY,
                    initialX: currentX,
                    initialY: currentY
                }};
                
                container.classList.add('popup-dragging');
                e.preventDefault();
                e.stopPropagation();
            }}'''
        )
    
    def _on_position_update(self, e):
        """Handle position update from JavaScript after drag."""
        args = e.args
        if not args:
            return
            
        container_id = f'c{self._content_container.id}' if self._content_container else None
        
        # Check if this event is for this popup instance
        if args.get('containerId') == container_id:
            self.position_x = args.get('x', self.position_x)
            self.position_y = args.get('y', self.position_y)
            print(f"Position updated to: ({self.position_x}, {self.position_y})")
    
    def _register_position_listener(self):
        """Register listener for position updates from JS."""
        # Use ui.on to listen for the custom event
        self._event_listener = ui.on('popup_position_update', self._on_position_update)
        
        # Register this instance in the class registry
        if self._content_container:
            container_id = f'c{self._content_container.id}'
            Popup._instances[container_id] = self

    def _unregister_position_listener(self):
        """Unregister the position listener."""
        # Remove from instance registry
        if self._content_container:
            container_id = f'c{self._content_container.id}'
            Popup._instances.pop(container_id, None)
    
    def _start_position_enforcement(self):
        """Start the continuous position enforcement loop."""
        print(f"DEBUG _start_position_enforcement called!")
        
        if not self._content_container:
            print("DEBUG: No content container!")
            return
        
        container_id = f'c{self._content_container.id}'
        initial_x = self.position_x if self.position_x is not None else 100
        initial_y = self.position_y if self.position_y is not None else 100
        
        print(f"DEBUG: Starting enforcement for {container_id} at ({initial_x}, {initial_y})")
        
        ui.run_javascript(f'''
            console.log('Python requesting start enforcement:', '{container_id}', {initial_x}, {initial_y});
            window._startPopupPositionEnforcement('{container_id}', {initial_x}, {initial_y});
        ''')
    
    def _stop_position_enforcement(self):
        """Stop the position enforcement loop."""
        if not self._content_container:
            return
        
        container_id = f'c{self._content_container.id}'
        
        print(f"DEBUG: _stop_position_enforcement called for {container_id}")

        
        ui.run_javascript(f'''
            console.log('Stopping position enforcement:', '{container_id}');
            window._stopPopupPositionEnforcement('{container_id}');
        ''')
    
    def _cleanup_position(self):
        """Clean up stored position when popup is deleted."""
        print("DEBUG _cleanup_position called!")
        
        if not self._content_container:
            return
        
        container_id = f'c{self._content_container.id}'
        ui.run_javascript(f'''
            window._cleanupPopupPosition('{container_id}');
        ''')
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._content_area:
            self._content_area.__exit__(exc_type, exc_val, exc_tb)
        if self.escape_close:
            ui.keyboard(self._handle_escape_key)
        
    def _handle_backdrop_click(self, e):
        self.close()
        
    def _handle_escape_key(self, e):
        if e.key == 'Escape' and self._is_open:
            self.close()

    def open(self):
        print(f"DEBUG open() called, _is_open={self._is_open}, _popup_element={self._popup_element is not None}")
        
        if self._popup_element and not self._is_open:
            self._ensure_global_handlers()
            
            # Register position listener
            self._register_position_listener()
            
            # Set initial position directly before showing
            if self._content_container and self.position_x is not None and self.position_y is not None:
                print(f"DEBUG: Setting initial style position: ({self.position_x}, {self.position_y})")
                self._content_container.style(
                    f'position: fixed; '
                    f'left: {self.position_x}px; '
                    f'top: {self.position_y}px; '
                    f'margin: 0; '
                    f'transform: none;'
                )
            
            self._popup_element.style('display: flex')
            self._is_open = True
            
            # Start enforcement IMMEDIATELY, not with a timer
            print(f"DEBUG: Calling _start_position_enforcement immediately")
            self._start_position_enforcement()
        else:
            print(f"DEBUG open() skipped - conditions not met")    
                
    def close(self):
        print("DEBUG close() called!")
        import traceback
        traceback.print_stack(limit=15)
        
        if self._popup_element and self._is_open:
            self._popup_element.style('display: none')
            self._is_open = False
            self._unregister_position_listener()
            self._stop_position_enforcement()
            
            if self._on_close_callback:
                self._on_close_callback()
                
    def toggle(self):
        if self._is_open:
            self.close()
        else:
            self.open()
                
    def delete(self):
        print("DEBUG delete() called!")
        import traceback
        traceback.print_stack(limit=15)
        
        if self._popup_element:
            self._unregister_position_listener()
            self._stop_position_enforcement()
            self._cleanup_position()
            
            self._popup_element.delete()
            self._popup_element = None
            self._content_container = None
            self._content_area = None
            self._title_row = None
            self._backdrop = None
            self._is_open = False
            
    def on_close(self, callback: Callable):
        self._on_close_callback = callback
        return self

    @property
    def is_open(self) -> bool:
        return self._is_open

    @classmethod
    def create_context_menu(cls, title: str, x: float, y: float, **kwargs):
        defaults = {
            'width': "auto",
            'height': "auto",
            'backdrop_click_close': True,
            'backdrop_color': "transparent",
            'closable': True,
            'draggable': True
        }
        config = {**defaults, **kwargs}
        return cls(title=title, position_x=x, position_y=y, **config)


if __name__ in {"__main__", "__mp_main__"}:
    
    def show_popup():
        popup = Popup(
            title="Drag Me - Check Console!",
            width="400px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
            draggable=True,
            position_x=200,
            position_y=150
        )
        
        with popup:
            ui.label("Open browser console (F12) to see position logs")
            ui.label("Drag, then expand sections and watch console")
            
            ui.separator()
            
            with ui.expansion("Section 1", icon="folder"):
                ui.label("Content of section 1")
            
            with ui.expansion("Section 2", icon="folder"):
                ui.label("Content of section 2")
                ui.input("Input field").classes('w-full')
        
        popup.open()
    
    ui.label("Popup Debug Test").classes('text-2xl font-bold')
    ui.button("Open Popup", on_click=show_popup).classes('mt-4')
    
    ui.run()
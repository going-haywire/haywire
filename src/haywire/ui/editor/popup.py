from nicegui import ui
from typing import Optional, Callable


class Popup:
    """
    A reusable popup component for NiceGUI with drag support.
    Uses NiceGUI's native event system for more reliable event handling.
    """
    
    _css_added = False
    
    @classmethod
    def _ensure_css(cls):
        if not cls._css_added:
            ui.add_css('''
                .popup-overlay { z-index: 5000 !important; }
                .popup-card { z-index: 5001 !important; pointer-events: auto !important; }
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
        self._drag_handlers_initialized = False
        
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
            content_style = f'position: fixed; left: {self.position_x}px; top: {self.position_y}px; min-width: {self.width}; height: {self.height}; max-width: 90vw; max-height: 90vh; overflow: auto; z-index: 5001; pointer-events: auto;'
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
                    
                    # Setup drag using NiceGUI's event system
                    if self.draggable:
                        self._setup_native_drag_events()
                
                self._content_area = ui.column().classes('popup-content-area w-full interactive')
                self._content_area._props['data-interactive'] = 'true'
    
    def _setup_native_drag_events(self):
        """Setup drag events using NiceGUI's native .on() method with js_handler."""
        if not self._title_row or not self._content_container:
            return
        
        container_id = self._content_container.id
        
        # Use NiceGUI's .on() with a js_handler that handles the drag start
        # This ensures the event is properly registered through NiceGUI's system
        self._title_row.on(
            'mousedown',
            js_handler=f'''(e) => {{
                // Skip if clicking on button
                if (e.target.closest('button, .q-btn')) return;
                
                // Skip if menu is open
                if (document.querySelector('.q-menu')) return;
                
                console.log('>>> NATIVE DRAG START <<<');
                
                const container = document.getElementById('c{container_id}');
                if (!container) return;
                
                // Initialize drag state on window to make it globally accessible
                window._popupDragState = {{
                    isDragging: true,
                    containerId: 'c{container_id}',
                    startX: e.clientX,
                    startY: e.clientY,
                    initialLeft: container.getBoundingClientRect().left,
                    initialTop: container.getBoundingClientRect().top
                }};
                
                container.classList.add('popup-dragging');
                
                e.preventDefault();
                e.stopPropagation();
            }}'''
        )
    
    def _setup_global_drag_handlers(self):
        """Setup global mousemove/mouseup handlers for drag."""
        if self._drag_handlers_initialized:
            return
        
        container_id = self._content_container.id
        
        script = f'''
        (function() {{
            // Only setup once globally
            if (window._popupGlobalDragHandlersSetup) return;
            window._popupGlobalDragHandlersSetup = true;
            
            console.log('Setting up global popup drag handlers');
            
            document.addEventListener('mousemove', function(e) {{
                const state = window._popupDragState;
                if (!state || !state.isDragging) return;
                
                const container = document.getElementById(state.containerId);
                if (!container) return;
                
                const dx = e.clientX - state.startX;
                const dy = e.clientY - state.startY;
                
                let newLeft = state.initialLeft + dx;
                let newTop = state.initialTop + dy;
                
                // Keep within viewport
                newLeft = Math.max(0, Math.min(newLeft, window.innerWidth - container.offsetWidth));
                newTop = Math.max(0, Math.min(newTop, window.innerHeight - container.offsetHeight));
                
                container.style.position = 'fixed';
                container.style.left = newLeft + 'px';
                container.style.top = newTop + 'px';
                container.style.margin = '0';
                container.style.transform = 'none';
                
                e.preventDefault();
            }}, true);
            
            document.addEventListener('mouseup', function(e) {{
                const state = window._popupDragState;
                if (!state || !state.isDragging) return;
                
                console.log('>>> NATIVE DRAG END <<<');
                
                const container = document.getElementById(state.containerId);
                if (container) {{
                    container.classList.remove('popup-dragging');
                }}
                
                window._popupDragState = null;
            }}, true);
            
            window.addEventListener('blur', function() {{
                const state = window._popupDragState;
                if (state && state.isDragging) {{
                    const container = document.getElementById(state.containerId);
                    if (container) {{
                        container.classList.remove('popup-dragging');
                    }}
                    window._popupDragState = null;
                }}
            }});
        }})();
        '''
        
        ui.run_javascript(script)
        self._drag_handlers_initialized = True
        
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
        if self._popup_element and not self._is_open:
            self._popup_element.style('display: flex')
            self._is_open = True
            
            # Setup global drag handlers
            if self.draggable:
                ui.timer(0.1, self._setup_global_drag_handlers, once=True)
            
    def close(self):
        if self._popup_element and self._is_open:
            self._popup_element.style('display: none')
            self._is_open = False
            if self._on_close_callback:
                self._on_close_callback()
                
    def toggle(self):
        if self._is_open:
            self.close()
        else:
            self.open()
                
    def delete(self):
        if self._popup_element:
            self._popup_element.delete()
            self._popup_element = None
            self._content_container = None
            self._content_area = None
            self._title_row = None
            self._backdrop = None
            self._is_open = False
            self._drag_handlers_initialized = False
            
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
            title="Drag This Title Bar!",
            width="400px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
            draggable=True
        )
        
        with popup:
            ui.label("Check browser console for debug output")
            ui.label("Try clicking on the title bar area (not the X button)")
            ui.separator()
            ui.input("Text input works").classes('w-full')
            ui.separator()
            with ui.button("Menu Test"):
                with ui.menu():
                    ui.menu_item("Option 1", lambda: ui.notify("1"))
        
        popup.open()
    
    ui.label("Popup Native Events Test").classes('text-2xl font-bold')
    ui.label("Open browser console (F12) and try to drag the popup").classes('text-gray-600')
    ui.button("Open Popup", on_click=show_popup).classes('mt-4')
    
    ui.run()
from nicegui import ui
from typing import Optional, Callable


class Popup:
    """
    A reusable popup component for NiceGUI that behaves like ui.dialog()
    but with more styling flexibility and is always attached to the page root.
    
    Features:
    - Draggable by title bar
    - Text selection works in content area
    - Configurable backdrop, positioning, and close behavior
    """
    
    # Class-level flag to track if CSS has been added
    _css_added = False
    
    @classmethod
    def _ensure_css(cls):
        """Add CSS only once per application"""
        if not cls._css_added:
            ui.add_css('''
                /* Enable text selection in popup content */
                .popup-content-area {
                    user-select: text !important;
                    -webkit-user-select: text !important;
                    -moz-user-select: text !important;
                    -ms-user-select: text !important;
                    cursor: auto;
                }
                
                .popup-content-area * {
                    user-select: text !important;
                    -webkit-user-select: text !important;
                    pointer-events: auto !important;
                }
                
                /* Draggable title bar styling */
                .popup-title-bar {
                    user-select: none !important;
                    -webkit-user-select: none !important;
                    cursor: move;
                }
                
                .popup-title-bar.not-draggable {
                    cursor: default;
                }
                       
                /* Ensure popup is above canvas z-index */
                .draggable-popup {
                    z-index: 1001 !important;
                }
                
                /* Ensure buttons in title bar have pointer cursor */
                .popup-title-bar button {
                    cursor: pointer !important;
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
        """
        Initialize the popup.
        
        Args:
            title: Optional title for the popup
            width: CSS width of the popup content
            height: CSS height of the popup content  
            closable: Whether to show a close button
            backdrop_click_close: Whether clicking backdrop closes popup
            escape_close: Whether escape key closes popup
            backdrop_color: Background color of the overlay
            position_x: Optional X position (for context menus)
            position_y: Optional Y position (for context menus)
            draggable: Whether the popup can be dragged by its title bar
        """
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
        self._popup_element: Optional[ui.element] = None
        self._content_container: Optional[ui.element] = None
        self._content_area: Optional[ui.element] = None
        self._is_open = False
        self._on_close_callback: Optional[Callable] = None
        self._original_context = None
        self._drag_script: Optional[str] = None
        
    def __enter__(self):
        """Context manager entry - creates the popup structure at page root"""
        if self._popup_element is not None:
            raise RuntimeError("Popup is already created")
        
        # CRITICAL: Save current context and switch to page root
        self._original_context = ui.context.client.layout
        
        # Create popup at the page root level, outside any containers
        with ui.context.client.layout:
            self._create_popup_structure()
        
        # Enter the content area's context so UI elements are added to it
        self._content_area.__enter__()
        return self._content_area
    
    def _create_popup_structure(self):
        """Create the popup structure at page root level"""
        # Determine positioning style
        if self.position_x is not None and self.position_y is not None:
            # Context menu positioning
            popup_style = '''
                position: fixed; 
                top: 0; 
                left: 0; 
                width: 100%; 
                height: 100%; 
                background: transparent; 
                z-index: 1000; 
                display: none;
                pointer-events: none;
            '''
            content_style = f'''
                position: fixed;
                left: {self.position_x}px;
                top: {self.position_y}px;
                min-width: {self.width};
                height: {self.height};
                max-width: 90vw;
                max-height: 90vh;
                overflow: auto;
                z-index: 1001;
                pointer-events: auto;
            '''
            backdrop_style = '''
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 0;
                background: transparent;
                pointer-events: auto;
            '''
        else:
            # Centered modal positioning  
            popup_style = f'''
                position: fixed; 
                top: 0; 
                left: 0; 
                width: 100%; 
                height: 100%; 
                background: {self.backdrop_color}; 
                z-index: 1000; 
                display: none; 
                align-items: center; 
                justify-content: center;
                backdrop-filter: blur(2px);
                pointer-events: auto;
            '''
            content_style = f'''
                min-width: {self.width};
                height: {self.height};
                max-width: 90vw;
                max-height: 90vh;
                overflow: auto;
                margin: 20px;
                position: relative;
                z-index: 1;
                pointer-events: auto;
            '''
            backdrop_style = '''
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: -1;
                pointer-events: auto;
            '''
        
        # Create the popup overlay
        self._popup_element = ui.element('div').style(popup_style)
        self._popup_element._props['data-popup'] = 'true'  # Mark as popup
            
        with self._popup_element:
            # Create backdrop for click-outside-to-close functionality
            if self.backdrop_click_close:
                backdrop = ui.element('div').style(backdrop_style)
                backdrop.on('click', self._handle_backdrop_click)
            
            # Create content container (the card)
            self._content_container = ui.card().style(content_style)
            self._content_container.classes('interactive')  # Uses existing GraphCanvas whitelist
            self._content_container._props['data-interactive'] = 'true'  # Use existing whitelist

            with self._content_container:
                # Add title bar if title or closable
                if self.title or self.closable:
                    title_bar_classes = 'popup-title-bar' if self.draggable else 'popup-title-bar not-draggable'
                    title_row = ui.row().classes(f'w-full justify-between items-center mb-2 {title_bar_classes}')
                    
                    with title_row:
                        if self.title:
                            ui.label(self.title).style(
                                'font-size: 1.1em; font-weight: 600; pointer-events: none;'
                            )
                        else:
                            ui.element('div')  # Spacer
                            
                        if self.closable:
                            ui.button(icon='close', on_click=self.close).props(
                                'flat round size=sm'
                            )
                    
                    if self.title:
                        ui.separator()
                    
                    # Setup draggable if requested
                    if self.draggable:
                        self._setup_draggable(title_row)
                
                # Create content area where user content will be placed
                self._content_area = ui.column().classes('popup-content-area w-full w-full interactive')
                self._content_area._props['data-interactive'] = 'true'

    def _setup_draggable(self, title_element):
        """Setup drag functionality for the title bar."""
        container_id = self._content_container.id
        handle_id = title_element.id
        
        # JavaScript for drag functionality
        # Key points:
        # - Only drag when mousedown is on the title bar (not buttons)
        # - Don't interfere with text selection in content area
        # - Use document-level listeners for smooth dragging
        self._drag_script = f'''
        (function() {{
            const container = document.getElementById('c{container_id}');
            const handle = document.getElementById('c{handle_id}');
            
            if (!container || !handle) {{
                console.warn('Popup drag setup: elements not found');
                return;
            }}
            
            // Prevent duplicate initialization
            if (handle.dataset.dragInitialized) return;
            handle.dataset.dragInitialized = 'true';
            
            let isDragging = false;
            let startX = 0;
            let startY = 0;
            let initialLeft = 0;
            let initialTop = 0;
            
            handle.addEventListener('mousedown', function(e) {{
                // Don't drag if clicking on interactive elements
                if (e.target.closest('button, input, a, [role="button"]')) {{
                    return;
                }}
                
                isDragging = true;
                startX = e.clientX;
                startY = e.clientY;
                
                // Get current position
                const rect = container.getBoundingClientRect();
                initialLeft = rect.left;
                initialTop = rect.top;
                
                // Prevent text selection while dragging
                e.preventDefault();
                
                // Add dragging class for visual feedback
                container.style.transition = 'none';
            }});
            
            document.addEventListener('mousemove', function(e) {{
                if (!isDragging) return;
                
                const dx = e.clientX - startX;
                const dy = e.clientY - startY;
                
                let newLeft = initialLeft + dx;
                let newTop = initialTop + dy;
                
                // Keep popup within viewport bounds
                const rect = container.getBoundingClientRect();
                const maxLeft = window.innerWidth - rect.width;
                const maxTop = window.innerHeight - rect.height;
                
                newLeft = Math.max(0, Math.min(newLeft, maxLeft));
                newTop = Math.max(0, Math.min(newTop, maxTop));
                
                container.style.position = 'fixed';
                container.style.left = newLeft + 'px';
                container.style.top = newTop + 'px';
                container.style.margin = '0';
                container.style.transform = 'none';
            }});
            
            document.addEventListener('mouseup', function() {{
                if (isDragging) {{
                    isDragging = false;
                    container.style.transition = '';
                }}
            }});
            
            // Handle mouse leaving window while dragging
            document.addEventListener('mouseleave', function() {{
                if (isDragging) {{
                    isDragging = false;
                    container.style.transition = '';
                }}
            }});
        }})();
        '''
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        # Exit the content area's context
        if self._content_area:
            self._content_area.__exit__(exc_type, exc_val, exc_tb)
            
        # Add escape key handler
        if self.escape_close:
            ui.keyboard(self._handle_escape_key)
        
    def _handle_backdrop_click(self, e):
        """Handle clicks on the backdrop"""
        self.close()
        
    def _handle_escape_key(self, e):
        """Handle escape key press"""
        if e.key == 'Escape' and self._is_open:
            self.close()
    
    def open(self):
        """Open the popup"""
        if self._popup_element and not self._is_open:
            self._popup_element.style('display: flex')
            self._is_open = True
            
            # Run drag script if draggable (after a small delay to ensure DOM is ready)
            if self.draggable and self._drag_script:
                ui.run_javascript(self._drag_script)
            
    def close(self):
        """Close the popup"""
        if self._popup_element and self._is_open:
            self._popup_element.style('display: none')
            self._is_open = False
            if self._on_close_callback:
                self._on_close_callback()
                
    def toggle(self):
        """Toggle the popup open/closed state"""
        if self._is_open:
            self.close()
        else:
            self.open()
                
    def delete(self):
        """Delete the popup completely"""
        if self._popup_element:
            self._popup_element.delete()
            self._popup_element = None
            self._content_container = None
            self._content_area = None
            self._is_open = False
            
    def on_close(self, callback: Callable):
        """Set a callback to be called when popup is closed"""
        self._on_close_callback = callback
        return self  # Allow chaining
        
    @property
    def is_open(self) -> bool:
        """Check if popup is currently open"""
        return self._is_open

    @classmethod
    def create_context_menu(cls, title: str, x: float, y: float, **kwargs):
        """Convenience method to create a context menu positioned at coordinates"""
        defaults = {
            'width': "auto",
            'height': "auto",
            'backdrop_click_close': True,
            'backdrop_color': "transparent"
        }
        config = {**defaults, **kwargs}
        
        return cls(
            title=title,
            position_x=x,
            position_y=y,
            **config
        )


# Example usage and demo
if __name__ in {"__main__", "__mp_main__"}:
    
    popup = None
    
    def show_popup():
        global popup
        if popup and popup.is_open:
            popup.close()
            return
            
        popup = Popup(
            title="Draggable Popup",
            width="400px",
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
            draggable=True
        )
        
        with popup:
            ui.label("This text should be fully selectable!")
            ui.label(
                "Try selecting this paragraph. You can highlight any text here "
                "while still being able to drag the popup by its title bar above."
            )
            ui.separator()
            ui.label("You can also interact with inputs:")
            ui.input("Type here...").classes('w-full')
            ui.textarea("Multi-line input works too...").classes('w-full')
            
        popup.open()
    
    def show_context_menu(e):
        ctx_popup = Popup.create_context_menu(
            title="Context Menu",
            x=e.args['clientX'],
            y=e.args['clientY'],
            closable=True,
            draggable=True
        )
        
        with ctx_popup:
            ui.button("Option 1", on_click=lambda: ui.notify("Option 1 clicked"))
            ui.button("Option 2", on_click=lambda: ui.notify("Option 2 clicked"))
            ui.label("Right-click brought you here. This text is selectable!")
        
        ctx_popup.open()
    
    # Demo UI
    ui.label("Popup Demo").classes('text-2xl font-bold')
    ui.button("Open Popup", on_click=show_popup).classes('mt-4')
    
    demo_area = ui.card().classes('w-96 h-48 mt-4')
    with demo_area:
        ui.label("Right-click anywhere in this card for a context menu")
    
    demo_area.on('contextmenu', show_context_menu, ['clientX', 'clientY'])
    # Prevent default browser context menu
    demo_area.on('contextmenu', js_handler='(e) => e.preventDefault()')
    
    ui.run()
from nicegui import ui, app
from typing import Optional, Callable, Any

class Popup:
    """
    A reusable popup component for NiceGUI that behaves like ui.dialog()
    but with more styling flexibility and is always attached to the page root.
    """
    
    def __init__(self, 
                 title: Optional[str] = None,
                 width: str = "auto",
                 height: str = "auto",
                 closable: bool = True,
                 backdrop_click_close: bool = True,
                 escape_close: bool = True,
                 backdrop_color: str = "rgba(0,0,0,0.5)",
                 position_x: Optional[float] = None,
                 position_y: Optional[float] = None):
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
        """
        self.title = title
        self.width = width
        self.height = height
        self.closable = closable
        self.backdrop_click_close = backdrop_click_close
        self.escape_close = escape_close
        self.backdrop_color = backdrop_color
        self.position_x = position_x
        self.position_y = position_y
        self._popup_element: Optional[ui.element] = None
        self._content_container: Optional[ui.element] = None
        self._is_open = False
        self._on_close_callback: Optional[Callable] = None
        self._original_context = None
        
    def __enter__(self):
        """Context manager entry - creates the popup structure at page root"""
        if self._popup_element is not None:
            raise RuntimeError("Popup is already created")
        
        # CRITICAL: Save current context and switch to page root
        self._original_context = ui.context.client.layout
        
        # Create popup at the page root level, outside any containers
        with ui.context.client.layout:
            self._create_popup_structure()
        
        # Enter the content container's context so UI elements are added to it
        self._content_container.__enter__()
        return self._content_container
    
    def _create_popup_structure(self):
        """Create the popup structure at page root level"""
        # Determine positioning style
        if self.position_x is not None and self.position_y is not None:
            # Context menu positioning
            popup_style = f'''
                position: fixed; 
                top: 0; 
                left: 0; 
                width: 100%; 
                height: 100%; 
                background: transparent; 
                z-index: 1000; 
                display: none;
                pointer-events: all;
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
                pointer-events: all;
            '''
            backdrop_style = '''
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 0;
                background: transparent;
                pointer-events: all;
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
                pointer-events: all;
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
                pointer-events: all;
            '''
            backdrop_style = '''
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: -1;
                pointer-events: all;
            '''
        
        # Create the popup overlay
        self._popup_element = ui.element('div').style(popup_style)
        
        with self._popup_element:
            # Create backdrop for click-outside-to-close functionality
            # For context menus, backdrop is transparent but still captures clicks
            # For modals, backdrop has visual background
            if self.backdrop_click_close:
                backdrop = ui.element('div').style(backdrop_style)
                backdrop.on('click', self._handle_backdrop_click)
            
            # Create content container
            self._content_container = ui.card().style(content_style)
            
            with self._content_container:
                # Add title and close button if specified
                if self.title or self.closable:
                    with ui.row().classes('w-full justify-between items-center mb-2'):
                        if self.title:
                            ui.label(self.title).style('font-size: 1.1em; font-weight: 600;')
                        else:
                            ui.element('div')  # Spacer
                            
                        if self.closable:
                            ui.button(icon='close', on_click=self.close).props('flat round size=sm')
                    
                    if self.title:  # Only add separator if there's a title
                        ui.separator()
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        # Exit the content container's context
        if self._content_container:
            self._content_container.__exit__(exc_type, exc_val, exc_tb)
            
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
            
    def close(self):
        """Close the popup"""
        if self._popup_element and self._is_open:
            self._popup_element.style('display: none')
            self._is_open = False
            if self._on_close_callback:
                self._on_close_callback()
                
    def delete(self):
        """Delete the popup completely"""
        if self._popup_element:
            self._popup_element.delete()
            self._popup_element = None
            self._content_container = None
            self._is_open = False
            
    def on_close(self, callback: Callable):
        """Set a callback to be called when popup is closed"""
        self._on_close_callback = callback
        
    @property
    def is_open(self) -> bool:
        """Check if popup is currently open"""
        return self._is_open

    @classmethod
    def create_context_menu(cls, title: str, x: float, y: float, **kwargs):
        """Convenience method to create a context menu positioned at coordinates"""
        return cls(
            title=title,
            position_x=x,
            position_y=y,
            width="auto",
            height="auto",
            backdrop_click_close=True,
            backdrop_color="transparent",
            **kwargs
        )

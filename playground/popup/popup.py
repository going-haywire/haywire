from nicegui import ui
from typing import Optional, Callable

class Popup:
    """
    A reusable popup component for NiceGUI that behaves like ui.dialog()
    but with more styling flexibility.
    """
    
    def __init__(self, 
                 title: Optional[str] = None,
                 width: str = "auto",
                 height: str = "auto",
                 closable: bool = True,
                 backdrop_click_close: bool = True,
                 escape_close: bool = True,
                 backdrop_color: str = "rgba(0,0,0,0.5)"):
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
        """
        self.title = title
        self.width = width
        self.height = height
        self.closable = closable
        self.backdrop_click_close = backdrop_click_close
        self.escape_close = escape_close
        self.backdrop_color = backdrop_color
        self._popup_element: Optional[ui.element] = None
        self._content_container: Optional[ui.element] = None
        self._is_open = False
        self._on_close_callback: Optional[Callable] = None
        
    def __enter__(self):
        """Context manager entry - creates the popup structure"""
        if self._popup_element is not None:
            raise RuntimeError("Popup is already created")
            
        # Create the popup overlay
        self._popup_element = ui.element('div').style(f'''
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
        ''')
        
        # Create the popup content container
        with self._popup_element:
            # Create a backdrop area that handles clicks
            backdrop = ui.element('div').style('''
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: -1;
            ''')
            
            # Handle backdrop click
            if self.backdrop_click_close:
                backdrop.on('click', self._handle_backdrop_click)
            
            self._content_container = ui.card().style(f'''
                min-width: {self.width};
                height: {self.height};
                max-width: 90vw;
                max-height: 90vh;
                overflow: auto;
                margin: 20px;
                position: relative;
                z-index: 1;
            ''')
            
            with self._content_container:
                # Add title and close button if specified
                if self.title or self.closable:
                    with ui.row().classes('w-full justify-between items-center mb-4'):
                        if self.title:
                            ui.label(self.title).style('font-size: 1.2em; font-weight: bold;')
                        else:
                            ui.element('div')  # Spacer
                            
                        if self.closable:
                            ui.button(
                                icon='close', on_click=self.close
                            ).props('flat round size=sm')
                    
                    ui.separator()
        
        # Enter the content container's context so UI elements are added to it
        self._content_container.__enter__()
        return self._content_container
        
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

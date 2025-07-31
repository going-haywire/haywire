"""
NiceGUI implementation of the notification service
"""

from typing import Optional
from services.notification_service import NotificationService

try:
    from nicegui import ui
    NICEGUI_AVAILABLE = True
except ImportError:
    NICEGUI_AVAILABLE = False


class NiceGUINotificationService(NotificationService):
    """NiceGUI implementation of notification service"""
    
    def __init__(self):
        if not NICEGUI_AVAILABLE:
            raise ImportError("NiceGUI is required for NiceGUINotificationService")
    
    def notify(self, message: str, level: str = 'info', duration: Optional[float] = None):
        """Send a notification using NiceGUI"""
        # Map our level names to NiceGUI types
        level_mapping = {
            'info': 'info',
            'success': 'positive', 
            'warning': 'warning',
            'error': 'negative'
        }
        
        nicegui_type = level_mapping.get(level, 'info')
        
        if duration is not None:
            ui.notify(message, type=nicegui_type, timeout=duration)
        else:
            ui.notify(message, type=nicegui_type)
    
    def notify_success(self, message: str):
        """Send a success notification"""
        self.notify(message, 'success')
    
    def notify_error(self, message: str):
        """Send an error notification"""
        self.notify(message, 'error')
    
    def notify_warning(self, message: str):
        """Send a warning notification"""
        self.notify(message, 'warning')


class ConsoleNotificationService(NotificationService):
    """Console-based implementation for testing/debugging"""
    
    def notify(self, message: str, level: str = 'info', duration: Optional[float] = None):
        """Print notification to console"""
        print(f"[{level.upper()}] {message}")
    
    def notify_success(self, message: str):
        """Print success notification to console"""
        self.notify(message, 'success')
    
    def notify_error(self, message: str):
        """Print error notification to console"""
        self.notify(message, 'error')
    
    def notify_warning(self, message: str):
        """Print warning notification to console"""
        self.notify(message, 'warning')

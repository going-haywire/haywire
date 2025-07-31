"""
Service interfaces for decoupling business logic from UI framework
"""

from abc import ABC, abstractmethod
from typing import Optional

class NotificationService(ABC):
    """Abstract interface for notification services"""
    
    @abstractmethod
    def notify(self, message: str, level: str = 'info', duration: Optional[float] = None):
        """
        Send a notification to the user
        
        Args:
            message: The notification message
            level: The notification level ('info', 'success', 'warning', 'error')
            duration: Optional duration in seconds (None for default)
        """
        pass
    
    @abstractmethod
    def notify_success(self, message: str):
        """Send a success notification"""
        pass
    
    @abstractmethod
    def notify_error(self, message: str):
        """Send an error notification"""
        pass
    
    @abstractmethod
    def notify_warning(self, message: str):
        """Send a warning notification"""
        pass


class NullNotificationService(NotificationService):
    """Null object implementation for testing"""
    
    def notify(self, message: str, level: str = 'info', duration: Optional[float] = None):
        pass
    
    def notify_success(self, message: str):
        pass
    
    def notify_error(self, message: str):
        pass
    
    def notify_warning(self, message: str):
        pass

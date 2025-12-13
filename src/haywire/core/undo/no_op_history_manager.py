"""
No-op implementation of IHistoryManager for when undo/redo is not needed.

This provides a null object pattern implementation that satisfies the interface
but performs no actual operations.
"""

from typing import Optional
from .interfaces import IHistoryManager, IAction


class NoOpHistoryManager(IHistoryManager):
    """
    No-op implementation of history manager.
    
    This implementation satisfies the IHistoryManager interface but performs
    no actual undo/redo operations. Useful for contexts where undo/redo is
    not needed or disabled.
    """
    
    def __init__(self):
        """Initialize no-op history manager."""
        pass
    
    def add_action(self, action: IAction) -> None:
        """No-op: action is ignored."""
        pass
    
    def add_fence(self) -> None:
        """No-op: fence is ignored."""
        pass
    
    def undo(self) -> bool:
        """No-op: always returns False (no undo performed)."""
        return False
    
    def redo(self) -> bool:
        """No-op: always returns False (no redo performed)."""
        return False
    
    def can_undo(self) -> bool:
        """No-op: always returns False (no undo available)."""
        return False
    
    def can_redo(self) -> bool:
        """No-op: always returns False (no redo available)."""
        return False
    
    def clear(self) -> None:
        """No-op: nothing to clear."""
        pass
    
    def get_undo_description(self) -> Optional[str]:
        """No-op: always returns None."""
        return None
    
    def get_redo_description(self) -> Optional[str]:
        """No-op: always returns None."""
        return None
    
    def get_history_stats(self) -> dict:
        """No-op: returns empty stats."""
        return {
            'total_items': 0,
            'current_index': -1,
            'action_count': 0,
            'pending_actions': 0,
            'can_undo': False,
            'can_redo': False,
            'memory_usage': 0
        }

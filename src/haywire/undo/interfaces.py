"""
Core interfaces for the Haywire undo system.

This module defines the fundamental interfaces that all undo system components
must implement, following the three-layer separation of concerns architecture.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class IAction(ABC):
    """
    Interface for all undoable actions.
    
    Actions encapsulate both forward (redo) and reverse (undo) transformations
    for specific operations on the graph structure.
    """
    
    @abstractmethod
    def execute(self) -> None:
        """
        Execute the action (forward operation).
        This method implements the actual change to the system state.
        """
        pass
    
    @abstractmethod
    def undo(self) -> None:
        """
        Undo the action (reverse operation).
        This method reverses the change made by execute().
        """
        pass
    
    def can_merge(self, other: 'IAction') -> bool:
        """
        Check if this action can be merged with another action.
        
        Args:
            other: Another action to potentially merge with
            
        Returns:
            True if the actions can be merged, False otherwise
        """
        return False
    
    def merge(self, other: 'IAction') -> Optional['IAction']:
        """
        Merge this action with another action.
        
        Args:
            other: Another action to merge with
            
        Returns:
            A new action representing the merged operation, or None if merge failed
        """
        return None
    
    @property
    def description(self) -> str:
        """
        Human-readable description of the action for UI display.
        
        Returns:
            A string describing what this action does
        """
        return self.__class__.__name__


class IHistoryManager(ABC):
    """
    Interface for managing the undo/redo history.
    
    The history manager maintains the chronological sequence of actions
    and provides navigation mechanisms for undo/redo operations.
    """
    
    @abstractmethod
    def add_action(self, action: IAction) -> None:
        """
        Add an action to the history.
        
        Args:
            action: The action to add to the history
        """
        pass
    
    @abstractmethod
    def add_fence(self) -> None:
        """
        Add a fence to group related actions together.
        
        Fences create logical boundaries that undo/redo operations
        respect when traversing the action history.
        """
        pass
    
    @abstractmethod
    def undo(self) -> bool:
        """
        Undo the most recent action or action group.
        
        Returns:
            True if undo was successful, False if nothing to undo
        """
        pass
    
    @abstractmethod
    def redo(self) -> bool:
        """
        Redo the most recently undone action or action group.
        
        Returns:
            True if redo was successful, False if nothing to redo
        """
        pass
    
    @abstractmethod
    def can_undo(self) -> bool:
        """
        Check if undo operation is possible.
        
        Returns:
            True if there are actions that can be undone
        """
        pass
    
    @abstractmethod
    def can_redo(self) -> bool:
        """
        Check if redo operation is possible.
        
        Returns:
            True if there are actions that can be redone
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """
        Clear all history.
        This removes all actions and resets the history state.
        """
        pass
    
    @abstractmethod
    def get_undo_description(self) -> Optional[str]:
        """
        Get description of the next action that would be undone.
        
        Returns:
            Description string or None if nothing to undo
        """
        pass
    
    @abstractmethod
    def get_redo_description(self) -> Optional[str]:
        """
        Get description of the next action that would be redone.
        
        Returns:
            Description string or None if nothing to redo
        """
        pass

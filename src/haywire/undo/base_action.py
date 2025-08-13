"""
Base action class for the Haywire undo system.

This module provides the base ActionBase class that implements common
functionality for all actions, including timing, validation, and
basic merging logic.
"""

import time
import uuid
from abc import ABC
from typing import Any, Dict, Optional

from .interfaces import IAction


class ActionBase(IAction, ABC):
    """
    Abstract base class for all undoable actions.
    
    This class provides common functionality including:
    - Unique action identification
    - Timestamp tracking
    - Basic validation
    - Error handling utilities
    """
    
    def __init__(self, description: Optional[str] = None):
        """
        Initialize the base action.
        
        Args:
            description: Human-readable description of the action
        """
        self.action_id = str(uuid.uuid4())
        self.timestamp = time.time()
        self._description = description
        self._executed = False
        self._metadata: Dict[str, Any] = {}
    
    @property
    def description(self) -> str:
        """
        Human-readable description of the action.
        
        Returns the provided description or generates one from the class name.
        """
        if self._description:
            return self._description
        
        # Generate description from class name
        class_name = self.__class__.__name__
        if class_name.endswith('Action'):
            class_name = class_name[:-6]  # Remove 'Action' suffix
        
        # Convert CamelCase to space-separated words
        import re
        return re.sub(r'([A-Z])', r' \1', class_name).strip()
    
    def execute(self) -> None:
        """
        Execute the action with error handling and validation.
        
        This method wraps the actual execution logic with common
        validation and error handling.
        """
        if self._executed:
            raise RuntimeError(f"Action {self.action_id} has already been executed")
        
        try:
            self._execute_impl()
            self._executed = True
        except Exception as e:
            raise RuntimeError(f"Failed to execute action {self.description}: {e}") from e
    
    def undo(self) -> None:
        """
        Undo the action with error handling and validation.
        
        This method wraps the actual undo logic with common
        validation and error handling.
        """
        if not self._executed:
            raise RuntimeError(f"Cannot undo action {self.action_id} that hasn't been executed")
        
        try:
            self._undo_impl()
            self._executed = False
        except Exception as e:
            raise RuntimeError(f"Failed to undo action {self.description}: {e}") from e
    
    def _execute_impl(self) -> None:
        """
        Implement the actual execution logic.
        
        Subclasses must override this method to provide the specific
        implementation for their action type.
        """
        raise NotImplementedError("Subclasses must implement _execute_impl")
    
    def _undo_impl(self) -> None:
        """
        Implement the actual undo logic.
        
        Subclasses must override this method to provide the specific
        undo implementation for their action type.
        """
        raise NotImplementedError("Subclasses must implement _undo_impl")
    
    def can_merge(self, other: IAction) -> bool:
        """
        Basic merge compatibility check.
        
        By default, actions can only merge with actions of the same type
        that happened within a short time window.
        """
        if not isinstance(other, self.__class__):
            return False
        
        # Check time window (100ms default)
        time_diff = abs(self.timestamp - other.timestamp)
        return time_diff < 0.1
    
    def merge(self, other: IAction) -> Optional[IAction]:
        """
        Base merge implementation.
        
        Subclasses should override this to provide specific merge logic.
        """
        return None
    
    def set_metadata(self, key: str, value: Any) -> None:
        """
        Set metadata for the action.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self._metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata for the action.
        
        Args:
            key: Metadata key
            default: Default value if key not found
            
        Returns:
            The metadata value or default
        """
        return self._metadata.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the action to a dictionary.
        
        This can be used for debugging, logging, or persistence.
        """
        return {
            'action_id': self.action_id,
            'action_type': self.__class__.__name__,
            'description': self.description,
            'timestamp': self.timestamp,
            'executed': self._executed,
            'metadata': self._metadata.copy()
        }
    
    def __str__(self) -> str:
        """String representation of the action."""
        return f"{self.__class__.__name__}(id={self.action_id[:8]}, desc='{self.description}')"
    
    def __repr__(self) -> str:
        """Detailed string representation of the action."""
        return (f"{self.__class__.__name__}("
                f"id='{self.action_id}', "
                f"desc='{self.description}', "
                f"executed={self._executed}, "
                f"timestamp={self.timestamp})")


class CompositeAction(ActionBase):
    """
    An action that contains multiple sub-actions.
    
    This is useful for complex operations that need to execute
    multiple atomic actions as a single logical operation.
    """
    
    def __init__(self, actions: list[IAction], description: Optional[str] = None):
        """
        Initialize the composite action.
        
        Args:
            actions: List of sub-actions to execute
            description: Description of the composite operation
        """
        super().__init__(description)
        self.actions = actions.copy()
        self._executed_actions: list[IAction] = []
    
    def _execute_impl(self) -> None:
        """Execute all sub-actions in order."""
        self._executed_actions.clear()
        
        for action in self.actions:
            try:
                action.execute()
                self._executed_actions.append(action)
            except Exception as e:
                # Rollback any actions that were executed
                self._rollback_executed_actions()
                raise e
    
    def _undo_impl(self) -> None:
        """Undo all sub-actions in reverse order."""
        # Undo in reverse order of execution
        for action in reversed(self._executed_actions):
            action.undo()
        
        self._executed_actions.clear()
    
    def _rollback_executed_actions(self) -> None:
        """Rollback any actions that were successfully executed."""
        for action in reversed(self._executed_actions):
            try:
                action.undo()
            except Exception:
                # Log but don't re-raise to avoid masking the original error
                pass
        
        self._executed_actions.clear()
    
    @property
    def description(self) -> str:
        """Generate description based on sub-actions."""
        if self._description:
            return self._description
        
        if not self.actions:
            return "Empty composite action"
        
        if len(self.actions) == 1:
            return self.actions[0].description
        
        return f"Composite action with {len(self.actions)} sub-actions"
    
    def can_merge(self, other: IAction) -> bool:
        """Composite actions generally don't merge."""
        return False

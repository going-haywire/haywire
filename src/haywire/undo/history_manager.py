"""
Core history manager implementation for the Haywire undo system.

This module provides the main HistoryManager class that implements
the IHistoryManager interface with support for fencing, grouping,
and action merging.
"""

import time
import logging
from typing import List, Optional, Union
from dataclasses import dataclass

from .interfaces import IAction, IHistoryManager
from .config import UndoConfig


@dataclass
class Fence:
    """
    A fence marks a boundary in the action history.
    
    Fences group related actions together so that undo/redo operations
    treat multiple actions as a single logical operation.
    """
    timestamp: float
    description: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class ActionGroup:
    """
    A group of actions that should be treated as a single operation.
    
    Action groups are created automatically based on fencing and can
    contain both individual actions and nested groups.
    """
    actions: List[Union[IAction, 'ActionGroup']]
    description: Optional[str] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def execute(self) -> None:
        """Execute all actions in the group in order."""
        for action in self.actions:
            if isinstance(action, ActionGroup):
                action.execute()
            else:
                action.execute()
    
    def undo(self) -> None:
        """Undo all actions in the group in reverse order."""
        for action in reversed(self.actions):
            if isinstance(action, ActionGroup):
                action.undo()
            else:
                action.undo()
    
    @property
    def action_count(self) -> int:
        """Get the total number of individual actions in this group."""
        count = 0
        for action in self.actions:
            if isinstance(action, ActionGroup):
                count += action.action_count
            else:
                count += 1
        return count


class HistoryManager(IHistoryManager):
    """
    Main implementation of the history manager for undo/redo functionality.
    
    This class maintains the chronological sequence of actions and provides
    the core undo/redo functionality with support for fencing, grouping,
    and action merging.
    """
    
    def __init__(self, config: Optional[UndoConfig] = None):
        """
        Initialize the history manager.
        
        Args:
            config: Configuration for undo system behavior
        """
        self.config = config or UndoConfig()
        
        # Core history storage
        self.history: List[Union[IAction, ActionGroup, Fence]] = []
        self.current_index = -1  # Points to the last executed action
        
        # Grouping state
        self._pending_actions: List[IAction] = []
        self._last_fence_time = time.time()
        self._gesture_in_progress = False
        
        # Performance tracking
        self._action_count = 0
        self._memory_usage = 0
        self._last_merge_time = 0
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if self.config.enable_debug_logging:
            self.logger.setLevel(logging.DEBUG)
    
    def add_action(self, action: IAction) -> None:
        """
        Add an action to the history.
        
        This method handles action merging, grouping, and history maintenance
        based on the current configuration.
        """
        current_time = time.time()
        
        # Clear any redo history when adding new action
        self._clear_redo_history()
        
        # Execute the action immediately
        try:
            action.execute()
            if self.config.enable_debug_logging:
                self.logger.debug(f"Executed action: {action.description}")
        except Exception as e:
            self.logger.error(f"Failed to execute action {action.description}: {e}")
            return  # Don't add failed actions to history
        
        # Try to merge with the last action if merging is enabled
        if (self.config.enable_action_merging and 
            self._should_merge_action(action, current_time)):
            self._merge_with_last_action(action)
            return
        
        # Add to pending actions for grouping
        self._pending_actions.append(action)
        
        # Check if we should flush pending actions
        # Always flush immediately if grouping is disabled OR in debug mode
        should_flush = (not self.config.enable_auto_grouping or 
                       self.config.enable_debug_logging or
                       self._should_flush_pending_actions(current_time))
        
        if should_flush:
            self._flush_pending_actions()
        
        # Maintain history limits
        self._maintain_history_limits()
        
        # Update tracking
        self._action_count += 1
        self._last_action_time = current_time
        
        if self.config.enable_debug_logging:
            self.logger.debug(f"Added action: {action.description}")
            self.logger.debug(f"History state: {len(self.history)} items, current_index: {self.current_index}")
            self.logger.debug(f"Can undo: {self.can_undo()}, Can redo: {self.can_redo()}")
    
    def add_fence(self) -> None:
        """
        Add a fence to group related actions together.
        
        This forces any pending actions to be flushed and creates
        a boundary for future grouping operations.
        """
        current_time = time.time()
        
        # Flush any pending actions first
        if self._pending_actions:
            self._flush_pending_actions()
        
        # Add the fence
        fence = Fence(timestamp=current_time)
        self.history.append(fence)
        self._last_fence_time = current_time
        
        if self.config.enable_debug_logging:
            self.logger.debug("Added fence")
    
    def undo(self) -> bool:
        """
        Undo the most recent action or action group.
        
        Returns:
            True if undo was successful, False if nothing to undo
        """
        # Flush pending actions first
        if self._pending_actions:
            self._flush_pending_actions()
        
        if not self.can_undo():
            return False
        
        # Find the next undoable item
        item = self._get_current_undoable_item()
        if item is None:
            return False
        
        try:
            # Execute the undo
            if isinstance(item, ActionGroup):
                item.undo()
                self.logger.debug(f"Undid action group with {item.action_count} actions")
            else:
                item.undo()
                self.logger.debug(f"Undid action: {item.description}")
            
            # Move the current index
            self._move_to_previous_action()
            
            if self.config.show_undo_notifications:
                self._show_notification(f"Undid: {self._get_item_description(item)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to undo action: {e}")
            return False
    
    def redo(self) -> bool:
        """
        Redo the most recently undone action or action group.
        
        Returns:
            True if redo was successful, False if nothing to redo
        """
        if not self.can_redo():
            return False
        
        # Get the next item to redo (don't move index yet)
        item = self._get_current_redoable_item()
        
        if item is None:
            return False
        
        try:
            # Execute the redo
            if isinstance(item, ActionGroup):
                item.execute()
                self.logger.debug(f"Redid action group with {item.action_count} actions")
            else:
                item.execute()
                self.logger.debug(f"Redid action: {item.description}")
            
            # Move the current index forward after successful execution
            self._move_to_next_action()
            
            if self.config.show_undo_notifications:
                self._show_notification(f"Redid: {self._get_item_description(item)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to redo action: {e}")
            return False
    
    def can_undo(self) -> bool:
        """Check if undo operation is possible."""
        return self._get_current_undoable_item() is not None
    
    def can_redo(self) -> bool:
        """Check if redo operation is possible."""
        return self.current_index + 1 < len(self.history) and \
               any(not isinstance(item, Fence) for item in self.history[self.current_index + 1:])
    
    def clear(self) -> None:
        """Clear all history."""
        self.history.clear()
        self.current_index = -1
        self._pending_actions.clear()
        self._action_count = 0
        self._memory_usage = 0
        
        if self.config.enable_debug_logging:
            self.logger.debug("Cleared all history")
    
    def get_undo_description(self) -> Optional[str]:
        """Get description of the next action that would be undone."""
        item = self._get_current_undoable_item()
        return self._get_item_description(item) if item else None
    
    def get_redo_description(self) -> Optional[str]:
        """Get description of the next action that would be redone."""
        if self.current_index + 1 < len(self.history):
            item = self.history[self.current_index + 1]
            if not isinstance(item, Fence):
                return self._get_item_description(item)
        return None
    
    # Private helper methods
    
    def _should_merge_action(self, action: IAction, current_time: float) -> bool:
        """Check if the action should be merged with the last action."""
        if not self.history or not self._pending_actions:
            return False
        
        last_action = self._pending_actions[-1] if self._pending_actions else self._get_last_action()
        if not last_action:
            return False
        
        # Check time window
        time_diff = (current_time - self._last_merge_time) * 1000
        if time_diff > self.config.merge_time_window_ms:
            return False
        
        # Check if actions can merge
        return last_action.can_merge(action)
    
    def _merge_with_last_action(self, action: IAction) -> None:
        """Merge the action with the last action."""
        if self._pending_actions:
            last_action = self._pending_actions[-1]
            merged_action = last_action.merge(action)
            if merged_action:
                self._pending_actions[-1] = merged_action
                self._last_merge_time = time.time()
                
                if self.config.enable_debug_logging:
                    self.logger.debug(f"Merged actions: {action.description}")
    
    def _should_flush_pending_actions(self, current_time: float) -> bool:
        """Check if pending actions should be flushed to history."""
        if not self._pending_actions:
            return False
        
        # Flush if grouping is disabled
        if not self.config.enable_auto_grouping:
            return True
        
        # Flush if time window has passed
        time_since_last_fence = (current_time - self._last_fence_time) * 1000
        if time_since_last_fence > self.config.grouping_time_window_ms:
            return True
        
        return False
    
    def _flush_pending_actions(self) -> None:
        """Flush pending actions to the main history."""
        if not self._pending_actions:
            return
        
        if len(self._pending_actions) == 1:
            # Single action, add directly
            self.history.append(self._pending_actions[0])
            self.current_index = len(self.history) - 1
        else:
            # Multiple actions, create a group
            group = ActionGroup(actions=self._pending_actions.copy())
            self.history.append(group)
            self.current_index = len(self.history) - 1
        
        self._pending_actions.clear()
    
    def _clear_redo_history(self) -> None:
        """Clear any redo history when a new action is added."""
        if self.current_index + 1 < len(self.history):
            self.history = self.history[:self.current_index + 1]
    
    def _get_current_undoable_item(self) -> Optional[Union[IAction, ActionGroup]]:
        """Get the current item that can be undone."""
        index = self.current_index
        while index >= 0:
            item = self.history[index]
            if not isinstance(item, Fence):
                return item
            index -= 1
        return None
    
    def _get_current_redoable_item(self) -> Optional[Union[IAction, ActionGroup]]:
        """Get the current item that can be redone."""
        index = self.current_index + 1
        while index < len(self.history):
            item = self.history[index]
            if not isinstance(item, Fence):
                return item
            index += 1
        return None
    
    def _move_to_previous_action(self) -> None:
        """Move the current index to the previous action, skipping fences."""
        self.current_index -= 1
        while self.current_index >= 0 and isinstance(self.history[self.current_index], Fence):
            self.current_index -= 1
    
    def _move_to_next_action(self) -> None:
        """Move the current index to the next action, skipping fences."""
        self.current_index += 1
        while (self.current_index < len(self.history) and 
               isinstance(self.history[self.current_index], Fence)):
            self.current_index += 1
    
    def _get_last_action(self) -> Optional[IAction]:
        """Get the last action in the history."""
        for item in reversed(self.history):
            if isinstance(item, IAction):
                return item
            elif isinstance(item, ActionGroup) and item.actions:
                return item.actions[-1]
        return None
    
    def _get_item_description(self, item: Union[IAction, ActionGroup, None]) -> str:
        """Get a description for a history item."""
        if item is None:
            return "Unknown"
        elif isinstance(item, ActionGroup):
            if item.description:
                return item.description
            elif item.actions:
                return f"Group of {len(item.actions)} actions"
            else:
                return "Empty group"
        else:
            return item.description
    
    def _maintain_history_limits(self) -> None:
        """Maintain history within configured limits."""
        # Remove old items if we exceed the action limit
        if len(self.history) > self.config.max_actions:
            items_to_remove = len(self.history) - self.config.max_actions
            self.history = self.history[items_to_remove:]
            self.current_index = max(-1, self.current_index - items_to_remove)
    
    def _show_notification(self, message: str) -> None:
        """Show a notification message (placeholder for UI integration)."""
        # This would integrate with the UI notification system
        if self.config.enable_debug_logging:
            self.logger.info(f"Notification: {message}")
    
    # Debug and monitoring methods
    
    def get_history_stats(self) -> dict:
        """Get statistics about the current history state."""
        return {
            'total_items': len(self.history),
            'current_index': self.current_index,
            'action_count': self._action_count,
            'pending_actions': len(self._pending_actions),
            'can_undo': self.can_undo(),
            'can_redo': self.can_redo(),
            'memory_usage': self._memory_usage
        }

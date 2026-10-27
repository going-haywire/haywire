"""
Core history manager implementation for the Haywire undo system.

This module provides the main HistoryManager class that implements
the IHistoryManager interface with support for fencing, grouping,
and action merging.
"""

import time
import logging
from typing import Any, List, Optional, Union, cast
from dataclasses import dataclass

from haywire.core.errors import report_failure

from .actions.graph_actions import VALUE_EDIT_MERGE_IDLE_S
from .base_action import ActionBase
from .interfaces import IAction, IHistoryManager
from .config import UndoConfig

logger = logging.getLogger(__name__)


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

    actions: List[Union[IAction, "ActionGroup"]]
    description: Optional[str] = None
    timestamp: float | None = None

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

    def __init__(
        self, config: Optional[UndoConfig] = None, *, error_context: Optional[dict[str, Any]] = None
    ):
        """
        Initialize the history manager.

        Args:
            config: Configuration for undo system behavior
            error_context: Boundary context (e.g. ``graph_id``) added to every failure this
                history records in the error ledger; see ``report_failure``. Also settable
                later through the ``error_context`` attribute.
        """
        self.config = config or UndoConfig()
        self.error_context: dict[str, Any] = dict(error_context or {})

        # Core history storage
        self.history: List[Union[IAction, ActionGroup, Fence]] = []
        self.current_index = -1  # Points to the last executed action

        # Grouping state
        self._pending_actions: List[IAction] = []
        self._last_fence_time = time.time()

        # Merge window: the timestamp of the last action added, which is the
        # candidate the next one may merge into.
        self._last_merge_time: float = 0.0

        self._action_count = 0

        # The step the current value-edit merge run writes into: the last step
        # add_value_action recorded or amended, until anything else touches the history.
        self._amendable: Any = None

        self._undo_redo_count = 0

    @property
    def undo_redo_count(self) -> int:
        """Return how many undos and redos this history has performed; it grows with each one.

        An undo or redo may restore a value already in place, so it is not always visible as a
        change; this count is.
        """
        return self._undo_redo_count

    def add_action(self, action: IAction) -> bool:
        """
        Execute ``action`` and add it to the history.

        This method handles action merging, grouping, and history maintenance
        based on the current configuration.

        Returns:
            ``True`` if the action executed and entered the history, ``False``
            if its execution raised. The failure is recorded in the error ledger
            (a ``Refusal`` is not), and the history, including what can be redone,
            is left unchanged.
        """
        current_time = time.time()
        self._amendable = None

        try:
            action.execute()
            if self.config.enable_debug_logging:
                logger.debug(f"Executed action: {action.description}")
        except Exception as e:
            report_failure(e, operation="Apply edit", action=action.description, **self.error_context)
            return False

        self._record_executed(action, current_time)
        return True

    def record_executed(self, action: IAction) -> None:
        """Add an already applied ``action`` to the history, without running it. See ``IHistoryManager``."""
        self._amendable = None
        if isinstance(action, ActionBase):
            action.mark_executed()
        # Its own step: never grouped with a user action still pending, nor with the next one.
        if self._pending_actions:
            self._flush_pending_actions()
        self._record_executed(action, time.time())
        if self._pending_actions:
            self._flush_pending_actions()

    def add_value_action(
        self, action: IAction, merge_owner: object | None, idle_s: float = VALUE_EDIT_MERGE_IDLE_S
    ) -> bool:
        """
        Execute a value write and record it, amending the run's step while a merge run lasts.

        A write that changed nothing records nothing and leaves the redo branch and the merge run
        alone. Otherwise the write amends the step this method last recorded or amended, while
        that step is still the newest (the pending tail, else the history tip; in a group, its
        last action) and nothing else has touched the history since — any other action, a fence,
        an undo or a redo ends the run. It amends when both share a merge key — the action's
        ``value_key()`` plus ``merge_owner`` — and the step was written less than ``idle_s`` ago. A
        ``merge_owner`` of ``None`` never amends and is never amended. The amended step stays
        the executed action it was; the amend writes nothing.

        Args:
            action: A value-write action (``SetPropertyAction``, ``SetSettingAction``, ...).
            merge_owner: The session token a run belongs to, or ``None`` for no merging.
            idle_s: Seconds after a step's last write beyond which a write starts a new step.

        Returns:
            ``False`` if the action's execution raised (recorded as above, history unchanged), else ``True``.
        """
        value_action: Any = action
        try:
            value_action.execute()
        except Exception as e:
            report_failure(e, operation="Apply edit", action=action.description, **self.error_context)
            return False

        if not value_action.changed:
            action.cleanup()
            return True

        value_key = value_action.value_key()
        key = None if merge_owner is None or value_key is None else (value_key, merge_owner)
        value_action.merge_key = key

        if key is not None:
            candidate = self._amend_candidate()
            if (
                candidate is not None
                and getattr(candidate, "merge_key", None) == key
                and time.monotonic() - candidate.last_write < idle_s
            ):
                candidate.amend_from(value_action)
                action.cleanup()
                return True

        self._record_executed(action, time.time())
        self._amendable = action
        return True

    def _amend_candidate(self) -> Any:
        """The current merge run's step, or ``None`` when no run is open.

        That is the step ``add_value_action`` last recorded or amended, provided it is still the
        newest step: the pending tail if anything is pending, else the history tip, where a group
        stands for its last action.
        """
        if self._amendable is None:
            return None
        item: Any
        if self._pending_actions:
            item = self._pending_actions[-1]
        elif self.history:
            item = self.history[-1]
        else:
            return None
        while isinstance(item, ActionGroup):
            if not item.actions:
                return None
            item = item.actions[-1]
        return item if item is self._amendable else None

    def _record_executed(self, action: IAction, current_time: float) -> None:
        """Record an already executed action: end the redo branch, merge, group, flush, trim."""
        # A new action ends the redo branch, once it has actually changed the graph.
        self._clear_redo_history()

        # Try to merge with the last action if merging is enabled
        # A merge() that returns None merged nothing, so the action takes the append path below.
        if (
            self.config.enable_action_merging
            and self._should_merge_action(action, current_time)
            and self._merge_with_last_action(action)
        ):
            self._maintain_history_limits()
            self._action_count += 1
            return

        # Every action is a merge candidate for the next one, so the window is
        # measured from the last action added — not only from the last actual
        # merge, which left the timestamp at 0.0 and made merging unreachable.
        self._last_merge_time = current_time

        # Add to pending actions for grouping
        self._pending_actions.append(action)

        # Check if we should flush pending actions
        # Always flush immediately if grouping is disabled OR in debug mode
        should_flush = (
            not self.config.enable_auto_grouping
            or self.config.enable_debug_logging
            or self._should_flush_pending_actions(current_time)
        )

        if should_flush:
            self._flush_pending_actions()

        # Maintain history limits
        self._maintain_history_limits()

        # Update tracking
        self._action_count += 1

        if self.config.enable_debug_logging:
            logger.debug(f"Added action: {action.description}")
            logger.debug(f"History state: {len(self.history)} items, current_index: {self.current_index}")
            logger.debug(f"Can undo: {self.can_undo()}, Can redo: {self.can_redo()}")

    def add_fence(self) -> None:
        """
        Add a fence to group related actions together.

        This forces any pending actions to be flushed and creates
        a boundary for future grouping operations.
        """
        current_time = time.time()
        self._amendable = None

        # Flush any pending actions first
        if self._pending_actions:
            self._flush_pending_actions()

        # Add the fence
        fence = Fence(timestamp=current_time)
        self.history.append(fence)
        self._last_fence_time = current_time

        # Fences are appended directly, bypassing add_action's maintenance, so
        # collapse consecutive ones here or empty gestures grow history forever.
        self._trim_trailing_fences()

        if self.config.enable_debug_logging:
            logger.debug("Added fence")

    def undo(self) -> bool:
        """
        Undo the most recent action or action group.

        Returns:
            ``True`` if undo was successful; ``False`` if there was nothing to undo, or if the
            undo raised, which is recorded in the error ledger (a ``Refusal`` too).
        """
        self._amendable = None

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
                logger.debug(f"Undid action group with {item.action_count} actions")
            else:
                item.undo()
                logger.debug(f"Undid action: {item.description}")

            # Move the current index
            self._move_to_previous_action()
            self._undo_redo_count += 1

            if self.config.show_undo_notifications:
                self._show_notification(f"Undid: {self._get_item_description(item)}")

            return True

        except Exception as e:
            report_failure(
                e,
                operation="Undo",
                refusals_fail=True,
                action=self._get_item_description(item),
                **self.error_context,
            )
            return False

    def redo(self) -> bool:
        """
        Redo the most recently undone action or action group.

        Returns:
            ``True`` if redo was successful; ``False`` if there was nothing to redo, or if the
            redo raised, which is recorded in the error ledger (a ``Refusal`` too).
        """
        self._amendable = None

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
                logger.debug(f"Redid action group with {item.action_count} actions")
            else:
                item.execute()
                logger.debug(f"Redid action: {item.description}")

            # Move the current index forward after successful execution
            self._move_to_next_action()
            self._undo_redo_count += 1

            if self.config.show_undo_notifications:
                self._show_notification(f"Redid: {self._get_item_description(item)}")

            return True

        except Exception as e:
            report_failure(
                e,
                operation="Redo",
                refusals_fail=True,
                action=self._get_item_description(item),
                **self.error_context,
            )
            return False

    def can_undo(self) -> bool:
        """Check if undo operation is possible."""
        # Pending actions count: undo() flushes them before undoing, so an
        # action still inside the grouping window is undoable even though
        # nothing has reached `history` yet.
        return bool(self._pending_actions) or self._get_current_undoable_item() is not None

    def can_redo(self) -> bool:
        """Check if redo operation is possible."""
        return self.current_index + 1 < len(self.history) and any(
            not isinstance(item, Fence) for item in self.history[self.current_index + 1 :]
        )

    def clear(self) -> None:
        """Clear all history."""
        # Cleanup all items in history
        for item in self.history:
            self._cleanup_item(item)

        # Cleanup pending actions
        for action in self._pending_actions:
            action.cleanup()

        self.history.clear()
        self.current_index = -1
        self._pending_actions.clear()
        self._action_count = 0
        self._amendable = None

        if self.config.enable_debug_logging:
            logger.debug("Cleared all history")

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
        """Check if the action should be merged with the last action.

        Only ``_pending_actions`` matters: merging rewrites the pending tail,
        so an empty ``history`` (nothing flushed yet) is no obstacle. Requiring
        a non-empty ``history`` here used to block merging for the whole first
        group of a session.
        """
        if not self._pending_actions:
            return False

        last_action = self._pending_actions[-1]
        if not last_action:
            return False

        # Check time window
        time_diff = (current_time - self._last_merge_time) * 1000
        if time_diff > self.config.merge_time_window_ms:
            return False

        # Check if actions can merge
        return last_action.can_merge(action)

    def _merge_with_last_action(self, action: IAction) -> bool:
        """Merge the action into the last pending action; return ``True`` if a merge happened.

        Returns ``False`` when ``merge()`` returns ``None``, leaving the pending tail unchanged.
        On a merge, both operands are superseded by the merged action and can never be
        undone or redone again, so each is cleaned up — the same contract
        eviction and redo-branch discard honour.
        """
        if self._pending_actions:
            last_action = self._pending_actions[-1]
            merged_action = last_action.merge(action)
            if merged_action:
                self._pending_actions[-1] = merged_action
                self._last_merge_time = time.time()

                last_action.cleanup()
                action.cleanup()

                if self.config.enable_debug_logging:
                    logger.debug(f"Merged actions: {action.description}")
                return True
        return False

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
            group = ActionGroup(
                actions=cast(List[Union[IAction, ActionGroup]], self._pending_actions.copy())
            )
            self.history.append(group)
            self.current_index = len(self.history) - 1

        self._pending_actions.clear()

    def _clear_redo_history(self) -> None:
        """Clear any redo history when a new action is added."""
        if self.current_index + 1 < len(self.history):
            # Cleanup all discarded items
            for item in self.history[self.current_index + 1 :]:
                self._cleanup_item(item)

            # Remove from history
            self.history = self.history[: self.current_index + 1]

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
        while self.current_index < len(self.history) and isinstance(self.history[self.current_index], Fence):
            self.current_index += 1

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
        """Maintain history within configured limits.

        ``max_actions`` caps *undoable* items. Fences are boundaries, not
        actions, so they are not counted — a canvas drag emits two per gesture
        and counting them evicted real undo steps well before the user's limit.
        Fences leading the trimmed history are dropped too, since a fence with
        nothing before it groups nothing.
        """
        action_count = sum(1 for item in self.history if not isinstance(item, Fence))
        if action_count <= self.config.max_actions:
            return

        excess = action_count - self.config.max_actions

        # Walk forward until `excess` actions have been passed; everything up
        # to that point (actions and the fences among them) is discarded.
        items_to_remove = 0
        seen = 0
        for index, item in enumerate(self.history):
            if not isinstance(item, Fence):
                seen += 1
                if seen == excess:
                    items_to_remove = index + 1
                    break

        # Also drop fences now stranded at the head of the history.
        while items_to_remove < len(self.history) and isinstance(self.history[items_to_remove], Fence):
            items_to_remove += 1

        for item in self.history[:items_to_remove]:
            self._cleanup_item(item)

        self.history = self.history[items_to_remove:]
        self.current_index = max(-1, self.current_index - items_to_remove)

    def _trim_trailing_fences(self) -> None:
        """Collapse repeated fences at the tail of the history.

        Gestures that produce no action (a click that starts and ends a drag)
        still bracket themselves with fences. Without this they accumulate
        unboundedly, since fences do not count towards ``max_actions``.
        """
        while (
            len(self.history) >= 2
            and isinstance(self.history[-1], Fence)
            and isinstance(self.history[-2], Fence)
        ):
            self.history.pop()
            if self.current_index >= len(self.history):
                self.current_index = len(self.history) - 1

    def _show_notification(self, message: str) -> None:
        """Show a notification message (placeholder for UI integration)."""
        # This would integrate with the UI notification system
        if self.config.enable_debug_logging:
            logger.info(f"Notification: {message}")

    def _cleanup_item(self, item: Union[IAction, ActionGroup, Fence]) -> None:
        """
        Clean up a history item.

        Calls cleanup() on actions and recursively on action groups.
        Fences have no cleanup needed.

        Args:
            item: The history item to cleanup
        """
        if self._amendable is not None and self._holds(item, self._amendable):
            self._amendable = None
        if isinstance(item, Fence):
            # Fences have no cleanup
            return
        elif isinstance(item, ActionGroup):
            # Recursively cleanup all actions in the group
            for action in item.actions:
                if isinstance(action, ActionGroup):
                    self._cleanup_item(action)
                else:
                    action.cleanup()
        else:
            # Regular action
            item.cleanup()

    @staticmethod
    def _holds(item: Union[IAction, ActionGroup, Fence], action: Any) -> bool:
        """Whether ``item`` is ``action`` or a group containing it at any depth."""
        if isinstance(item, ActionGroup):
            return any(HistoryManager._holds(child, action) for child in item.actions)
        return item is action

    # Debug and monitoring methods

    def get_history_stats(self) -> dict:
        """Get statistics about the current history state."""
        return {
            "total_items": len(self.history),
            "current_index": self.current_index,
            "action_count": self._action_count,
            "pending_actions": len(self._pending_actions),
            "can_undo": self.can_undo(),
            "can_redo": self.can_redo(),
        }

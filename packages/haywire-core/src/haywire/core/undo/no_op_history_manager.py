"""
No-op implementation of IHistoryManager for when undo/redo is not needed.

This provides a null object pattern implementation that satisfies the interface
but performs no actual operations.
"""

from collections.abc import Callable
from typing import Optional
from .interfaces import IHistoryManager, IAction
from .origin import HistoryEntry, HistoryMove, StepOrigin


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

    def add_action(self, action: IAction, *, origin: StepOrigin | None = None) -> bool:
        """No-op: the action is ignored and never runs, so this returns ``False``."""
        return False

    def add_value_action(
        self,
        action: IAction,
        merge_owner: object | None,
        idle_s: float = 3.0,
        *,
        origin: StepOrigin | None = None,
    ) -> bool:
        """No-op: the action is ignored and never runs, so this returns ``False``."""
        return False

    def record_executed(self, action: IAction, *, origin: StepOrigin | None = None) -> None:
        """No-op: the action is not recorded."""

    def add_fence(self) -> None:
        """No-op: fence is ignored."""
        pass

    def undo(self, *, origin: StepOrigin | None = None) -> bool:
        """No-op: always returns False (no undo performed)."""
        return False

    def redo(self, *, origin: StepOrigin | None = None) -> bool:
        """No-op: always returns False (no redo performed)."""
        return False

    def snapshot(self) -> list[HistoryEntry]:
        """No-op: always returns an empty list."""
        return []

    def last_move(self) -> Optional[HistoryMove]:
        """No-op: always returns None."""
        return None

    def add_listener(self, listener: Callable[[], None]) -> None:
        """No-op: the listener is never called."""

    def remove_listener(self, listener: Callable[[], None]) -> None:
        """No-op: nothing to remove."""

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
            "total_items": 0,
            "current_index": -1,
            "action_count": 0,
            "pending_actions": 0,
            "can_undo": False,
            "can_redo": False,
        }

"""
Core interfaces for the Haywire undo system.

This module defines the fundamental interfaces that all undo system components
must implement, following the three-layer separation of concerns architecture.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .origin import HistoryEntry, HistoryMove, StepOrigin


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

    def can_merge(self, other: "IAction") -> bool:
        """
        Check if this action can be merged with another action.

        Args:
            other: Another action to potentially merge with

        Returns:
            True if the actions can be merged, False otherwise
        """
        return False

    def merge(self, other: "IAction") -> Optional["IAction"]:
        """
        Merge this action with another action.

        Args:
            other: Another action to merge with

        Returns:
            A new action representing the merged operation, or None if merge failed
        """
        return None

    def cleanup(self) -> None:
        """
        Clean up resources held by this action.

        This method is called when the action is being permanently removed
        from the history stack (e.g., due to history limits or clearing).
        Actions that hold references to removed nodes/edges should perform
        final cleanup here to prevent resource leaks.

        This is separate from undo() because resources must be preserved
        for potential redo operations. Only when the action is truly
        discarded should cleanup() be called.
        """
        pass

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
    def add_action(self, action: IAction, *, origin: "StepOrigin | None" = None) -> bool:
        """
        Execute ``action`` and add it to the history.

        Args:
            action: The action to add to the history
            origin: Who records it; kept beside the step for ``snapshot()``.

        Returns:
            ``True`` if the action executed and entered the history, ``False``
            if it did not run or its execution raised. A failed action leaves
            the history, including what can be redone, unchanged.
        """
        pass

    @abstractmethod
    def add_value_action(
        self,
        action: IAction,
        merge_owner: object | None,
        idle_s: float = ...,
        *,
        origin: "StepOrigin | None" = None,
    ) -> bool:
        """
        Execute a value write and record it, amending the newest step while a merge run lasts.

        A write that changed nothing records nothing. ``merge_owner`` is the session token a
        merge run belongs to; ``None`` never amends and is never amended.

        Args:
            action: A value-write action (a port or settings-field write).
            merge_owner: The session token a run belongs to, or ``None`` for no merging.
            idle_s: Seconds after a step's last write beyond which a write starts a new step.
            origin: Who records it; an amended step keeps the origin it was recorded with.

        Returns:
            ``False`` if the action did not run or its execution raised, else ``True``.
        """
        pass

    @abstractmethod
    def record_executed(self, action: IAction, *, origin: "StepOrigin | None" = None) -> None:
        """
        Add an action that has already been applied to the history, without running it.

        For a change made outside an action, whose undo the action carries. It
        ends the redo branch like any new step and never amends a running value
        edit.

        Args:
            action: The applied change; ``undo()`` must reverse it and a later
                ``execute()`` must apply it again.
            origin: Who records it; kept beside the step for ``snapshot()``.
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
    def undo(self, *, origin: "StepOrigin | None" = None) -> bool:
        """
        Undo the most recent action or action group.

        A successful undo becomes ``last_move()``, credited to ``origin``.

        Returns:
            True if undo was successful, False if nothing to undo
        """
        pass

    @abstractmethod
    def redo(self, *, origin: "StepOrigin | None" = None) -> bool:
        """
        Redo the most recently undone action or action group.

        A successful redo becomes ``last_move()``, credited to ``origin``.

        Returns:
            True if redo was successful, False if nothing to redo
        """
        pass

    @property
    def undo_redo_count(self) -> int:
        """Return how many undos and redos this history has performed; it grows with each one."""
        return 0

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

    @abstractmethod
    def snapshot(self) -> list["HistoryEntry"]:
        """
        Return the history as read-only rows, oldest first.

        Rows cover the whole history, redo branch and fences included, followed by the
        steps still pending in the grouping window. Building a snapshot changes nothing:
        it neither flushes pending steps nor ends a merge run.
        """
        pass

    @abstractmethod
    def last_move(self) -> Optional["HistoryMove"]:
        """Return the latest successful undo or redo since the last ``clear()``, or ``None``."""
        pass

    @abstractmethod
    def add_listener(self, listener: Callable[[], None]) -> None:
        """
        Call ``listener`` with no arguments whenever ``snapshot()`` would list different rows.

        That is: a step recorded, a group flushed, a fence, an undo, a redo, a trim or a clear.
        A step merged into the pending one, or a value write that amends an open step, lists no
        new row and does not call it. Listeners run on
        the thread that changed the history; one that raises is logged and skipped.
        """
        pass

    @abstractmethod
    def remove_listener(self, listener: Callable[[], None]) -> None:
        """Stop calling ``listener``; a listener that was never added is ignored."""
        pass

"""
Configuration for the Haywire undo system.

Every field here is read by :class:`~haywire.core.undo.history_manager.HistoryManager`.
Earlier revisions carried a wider set (memory caps, action compression, lazy
execution, integrity validation, keyboard-shortcut toggles) describing behaviour
that was never implemented; those were removed rather than left as knobs that
silently did nothing.
"""

from dataclasses import dataclass, field


def _default_max_actions() -> int:
    """Read the user's undo limit, falling back if settings aren't up yet.

    Resolved lazily (per construction) rather than at import: this module is
    imported early, before ``UndoSettings`` is necessarily registered. Same
    tolerate-absence approach as ``ActivityTracker._sync_history_size``.
    """
    try:
        from .settings import UndoSettings

        return UndoSettings().max_actions
    except Exception:
        return 100


@dataclass
class UndoConfig:
    """
    Configuration for the undo system behavior.

    Most fields are internal tuning. ``max_actions`` is the exception: it is
    the one knob users see, so it defaults to ``UndoSettings.max_actions``
    rather than a literal. An explicit value still wins — that is how
    ``DEVELOPMENT_CONFIG`` pins its own limit.
    """

    # History limits
    max_actions: int = field(default_factory=_default_max_actions)
    """Maximum number of actions to keep in history.

    Defaults to the user's ``UndoSettings.max_actions``, read at construction.
    """

    # Grouping behavior
    enable_auto_grouping: bool = True
    """Enable automatic grouping of related actions"""

    grouping_time_window_ms: int = 500
    """Time window for grouping rapid actions in milliseconds"""

    # Action merging
    enable_action_merging: bool = True
    """Enable merging of compatible consecutive actions"""

    merge_time_window_ms: int = 100
    """Time window for merging actions in milliseconds"""

    # UI behavior
    show_undo_notifications: bool = True
    """Show notifications when undo/redo operations complete"""

    # Debug and development
    enable_debug_logging: bool = False
    """Enable detailed logging for debugging.

    Also forces every action to flush immediately instead of grouping, so the
    log reads one line per action — see ``HistoryManager.add_action``.
    """


DEVELOPMENT_CONFIG = UndoConfig(
    max_actions=50,
    enable_debug_logging=True,
    show_undo_notifications=True,
)
"""Configuration optimized for development and debugging.

Note that pinning ``max_actions`` opts out of the user's ``UndoSettings``.
"""

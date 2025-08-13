"""
Configuration for the Haywire undo system.

This module provides configuration options for customizing the behavior
of the undo system, including performance settings, grouping behavior,
and user interface options.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class UndoConfig:
    """
    Configuration for the undo system behavior.
    
    This class encapsulates all configurable aspects of the undo system,
    allowing fine-tuning of performance, behavior, and user experience.
    """
    
    # History limits
    max_actions: int = 100
    """Maximum number of actions to keep in history"""
    
    max_memory_mb: int = 50
    """Maximum memory usage for action history in megabytes"""
    
    # Grouping behavior
    enable_auto_grouping: bool = True
    """Enable automatic grouping of related actions"""
    
    grouping_time_window_ms: int = 500
    """Time window for grouping rapid actions in milliseconds"""
    
    auto_fence_on_gesture_end: bool = True
    """Automatically add fences when user gestures complete"""
    
    # Action merging
    enable_action_merging: bool = True
    """Enable merging of compatible consecutive actions"""
    
    merge_move_actions: bool = True
    """Merge consecutive node move actions"""
    
    merge_selection_actions: bool = True
    """Merge consecutive selection change actions"""
    
    merge_time_window_ms: int = 100
    """Time window for merging actions in milliseconds"""
    
    # UI behavior
    show_undo_notifications: bool = True
    """Show notifications when undo/redo operations complete"""
    
    enable_keyboard_shortcuts: bool = True
    """Enable Ctrl+Z/Ctrl+Y keyboard shortcuts"""
    
    undo_notification_duration_ms: int = 2000
    """Duration to show undo notifications"""
    
    # Performance
    lazy_action_execution: bool = False
    """Defer expensive calculations until undo/redo execution"""
    
    compress_old_actions: bool = True
    """Compress old actions to save memory"""
    
    compression_threshold_actions: int = 50
    """Number of actions after which compression starts"""
    
    # Debug and development
    enable_debug_logging: bool = False
    """Enable detailed logging for debugging"""
    
    track_performance_metrics: bool = False
    """Track detailed performance metrics"""
    
    validate_action_integrity: bool = True
    """Validate action state before and after execution"""


# Default configurations for different use cases

DEVELOPMENT_CONFIG = UndoConfig(
    max_actions=50,
    enable_debug_logging=True,
    track_performance_metrics=True,
    show_undo_notifications=True,
    validate_action_integrity=True
)
"""Configuration optimized for development and debugging"""

PERFORMANCE_CONFIG = UndoConfig(
    max_actions=200,
    enable_action_merging=True,
    lazy_action_execution=True,
    compress_old_actions=True,
    enable_debug_logging=False,
    track_performance_metrics=False,
    validate_action_integrity=False
)
"""Configuration optimized for performance"""

MINIMAL_CONFIG = UndoConfig(
    max_actions=25,
    enable_auto_grouping=False,
    enable_action_merging=False,
    show_undo_notifications=False,
    compress_old_actions=False,
    track_performance_metrics=False
)
"""Minimal configuration with basic undo functionality only"""

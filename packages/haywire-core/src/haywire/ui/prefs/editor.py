# haywire/ui/prefs/editor.py
"""Editor behaviour preference singleton."""

from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.barn.builtin.types import BOOL, CHOICES, INT, STRING

# TODO: Find the right place for EditorSettings


class EditorSettings(FrameworkSettings, namespace="editor"):
    """Global preferences controlling editor interaction and behaviour."""

    # Undo/Redo
    undo_limit = setting[INT](
        100,
        label="Undo Limit",
        description="Maximum number of undo steps",
        category="editor",
        min=10,
        max=1000,
    )
    group_undo_actions = setting[BOOL](
        True,
        label="Group Undo Actions",
        description="Group related actions into single undo step",
        category="editor",
    )

    # Auto-save
    auto_save = setting[BOOL](
        True, label="Auto Save", description="Automatically save changes", category="editor"
    )
    auto_save_interval_seconds = setting[INT](
        60,
        label="Auto Save Interval (s)",
        description="Seconds between auto-saves",
        category="editor",
        min=10,
        max=600,
    )
    create_backups = setting[BOOL](
        True,
        label="Create Backups",
        description="Create backup files before saving",
        category="editor",
    )
    max_backups = setting[INT](
        5,
        label="Max Backups",
        description="Maximum number of backup files to keep",
        category="editor",
        min=1,
        max=50,
    )

    # Selection and interaction
    confirm_delete = setting[BOOL](
        True,
        label="Confirm Delete",
        description="Ask for confirmation when deleting nodes",
        category="editor",
    )
    select_on_create = setting[BOOL](
        True, label="Select on Create", description="Select newly created nodes", category="editor"
    )
    focus_on_create = setting[BOOL](
        True,
        label="Focus on Create",
        description="Pan canvas to show newly created nodes",
        category="editor",
    )
    multi_select_modifier = setting[CHOICES](
        "ctrl",
        label="Multi-Select Modifier",
        description="Key modifier for multi-selection",
        category="editor",
        widget_config={"options": ["ctrl", "shift", "alt"]},
    )

    # Mouse controls
    pan_button = setting[CHOICES](
        "middle",
        label="Pan Mouse Button",
        description="Mouse button for canvas panning",
        category="editor",
        widget_config={"options": ["left", "middle", "right"]},
    )
    context_menu_button = setting[CHOICES](
        "right",
        label="Context Menu Button",
        description="Mouse button for context menu",
        category="editor",
        widget_config={"options": ["right", "middle"]},
    )
    double_click_action = setting[CHOICES](
        "edit",
        label="Double Click Action",
        description="Action when double-clicking a node",
        category="editor",
        widget_config={"options": ["edit", "collapse", "inspect", "none"]},
    )

    # External tools
    external_editor_command = setting[STRING](
        "code --goto {file}:{line}",
        label="External Editor Command",
        description=(
            "Command template for opening files externally. "
            "{file} and {line} are substituted. Leave the fallback list if empty."
        ),
        category="editor",
    )

    # Clipboard
    copy_with_connections = setting[BOOL](
        True,
        label="Copy with Connections",
        description="Include internal connections when copying multiple nodes",
        category="editor",
    )
    paste_offset = setting[INT](
        20,
        label="Paste Offset",
        description="Offset in pixels when pasting nodes",
        category="editor",
        min=0,
        max=100,
    )

    # Node creation
    quick_add_enabled = setting[BOOL](
        True,
        label="Enable Quick Add",
        description="Enable quick node creation with spacebar",
        category="editor",
    )
    quick_add_key = setting[CHOICES](
        "space",
        label="Quick Add Key",
        description="Key to open quick add menu",
        category="editor",
        widget_config={"options": ["space", "tab", "a"]},
    )
    show_recent_nodes = setting[BOOL](
        True,
        label="Show Recent Nodes",
        description="Show recently used nodes in quick add menu",
        category="editor",
    )
    recent_nodes_count = setting[INT](
        10,
        label="Recent Nodes Count",
        description="Number of recent nodes to show",
        category="editor",
        min=3,
        max=30,
    )

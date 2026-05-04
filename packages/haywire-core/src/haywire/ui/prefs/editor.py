# haywire/ui/prefs/editor.py
"""Editor behaviour preference singleton."""

from haywire.core.settings import field
from haywire.core.settings.schema import FrameworkSettings


class EditorSettings(FrameworkSettings, namespace="editor"):
    """Global preferences controlling editor interaction and behaviour."""

    # Undo/Redo
    undo_limit = field[int](
        100,
        label="Undo Limit",
        description="Maximum number of undo steps",
        category="editor",
        order=10,
        min=10,
        max=1000,
    )
    group_undo_actions = field[bool](
        True,
        label="Group Undo Actions",
        description="Group related actions into single undo step",
        category="editor",
        order=11,
    )

    # Auto-save
    auto_save = field[bool](
        True, label="Auto Save", description="Automatically save changes", category="editor", order=20
    )
    auto_save_interval_seconds = field[int](
        60,
        label="Auto Save Interval (s)",
        description="Seconds between auto-saves",
        category="editor",
        order=21,
        min=10,
        max=600,
    )
    create_backups = field[bool](
        True,
        label="Create Backups",
        description="Create backup files before saving",
        category="editor",
        order=22,
    )
    max_backups = field[int](
        5,
        label="Max Backups",
        description="Maximum number of backup files to keep",
        category="editor",
        order=23,
        min=1,
        max=50,
    )

    # Selection and interaction
    confirm_delete = field[bool](
        True,
        label="Confirm Delete",
        description="Ask for confirmation when deleting nodes",
        category="editor",
        order=30,
    )
    select_on_create = field[bool](
        True, label="Select on Create", description="Select newly created nodes", category="editor", order=31
    )
    focus_on_create = field[bool](
        True,
        label="Focus on Create",
        description="Pan canvas to show newly created nodes",
        category="editor",
        order=32,
    )
    multi_select_modifier = field[str](
        "ctrl",
        label="Multi-Select Modifier",
        description="Key modifier for multi-selection",
        category="editor",
        order=33,
        choices=["ctrl", "shift", "alt"],
    )

    # Mouse controls
    pan_button = field[str](
        "middle",
        label="Pan Mouse Button",
        description="Mouse button for canvas panning",
        category="editor",
        order=40,
        choices=["left", "middle", "right"],
    )
    context_menu_button = field[str](
        "right",
        label="Context Menu Button",
        description="Mouse button for context menu",
        category="editor",
        order=41,
        choices=["right", "middle"],
    )
    double_click_action = field[str](
        "edit",
        label="Double Click Action",
        description="Action when double-clicking a node",
        category="editor",
        order=42,
        choices=["edit", "collapse", "inspect", "none"],
    )

    # Clipboard
    copy_with_connections = field[bool](
        True,
        label="Copy with Connections",
        description="Include internal connections when copying multiple nodes",
        category="editor",
        order=50,
    )
    paste_offset = field[int](
        20,
        label="Paste Offset",
        description="Offset in pixels when pasting nodes",
        category="editor",
        order=51,
        min=0,
        max=100,
    )

    # Node creation
    quick_add_enabled = field[bool](
        True,
        label="Enable Quick Add",
        description="Enable quick node creation with spacebar",
        category="editor",
        order=60,
    )
    quick_add_key = field[str](
        "space",
        label="Quick Add Key",
        description="Key to open quick add menu",
        category="editor",
        order=61,
        choices=["space", "tab", "a"],
    )
    show_recent_nodes = field[bool](
        True,
        label="Show Recent Nodes",
        description="Show recently used nodes in quick add menu",
        category="editor",
        order=62,
    )
    recent_nodes_count = field[int](
        10,
        label="Recent Nodes Count",
        description="Number of recent nodes to show",
        category="editor",
        order=63,
        min=3,
        max=30,
    )

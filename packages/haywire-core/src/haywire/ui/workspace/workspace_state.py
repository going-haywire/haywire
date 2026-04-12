# packages/haywire-core/src/haywire/ui/workspace/workspace_state.py
"""
Workspace state dataclasses for the Haywire UI layout system.

The workspace is divided into four **slots** — ``left``, ``right``, ``main``,
and ``bottom``. Each slot has a **bar** (the control strip: vertical icons for
left/right, horizontal tabs for main/bottom) and an **area** (the content
panel where the active editor renders). A slot's active editor is always
referenced by its full registry key via ``active_tab_key``.

WorkspaceState is serializable to JSON for persistence. All editor_key values
are full registry_key strings (e.g. 'studio:editor:graph_editor') supplied by
the host application — this module contains no host-specific strings.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class TabState:
    """
    State of a single tab in a tabbed slot bar.

    Attributes:
        editor_key: Full registry_key of the editor in this tab.
        label: Tab display label.
        metadata: Editor-specific state (e.g., which graph is open).
    """

    editor_key: Optional[str] = None
    label: str = "Graph"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SlotState:
    """
    State of a left or right slot.

    Left and right slots host one editor at a time, selected via their
    icon-style bar (ActivityBar / ContextBar). The active editor is stored in
    ``active_tab_key`` — the same name used by main/bottom slots so that slot
    code can treat all four slots uniformly.

    Attributes:
        active_tab_key: Full registry_key of the editor currently in this slot.
        visible: Whether the slot's area is visible/expanded.
        size: Size in pixels (width for left/right).
    """

    active_tab_key: Optional[str] = None
    visible: bool = True
    size: int = 300


@dataclass
class MainSlotState:
    """
    State of the main slot — the primary tabbed editor region in the middle
    of the shell.

    The main slot always shows its tab bar (MainTabBar) when it has at least
    one tab. Its tab list is persisted because host applications may open or
    close main-slot editors during a session.

    Attributes:
        tabs: List of open tabs.
        active_tab_key: Full registry_key of the active tab. Resolved against
            the tab list on load; falls back to the first tab if the key is
            no longer present.
    """

    tabs: List[TabState] = field(default_factory=lambda: [TabState()])
    active_tab_key: Optional[str] = None


@dataclass
class BottomSlotState:
    """
    State of the bottom slot — a tabbed editor region below the main slot
    that can retract to a bar-only state.

    The tab list itself is **not** persisted — it is auto-populated from the
    editor registry on every load (one tab per editor whose ``default_slot``
    is ``"bottom"``). Only UI state (which tab is active, whether the content
    is expanded, and the last dragged height) survives across sessions.

    Attributes:
        tabs: Runtime-only tab list, repopulated on every load. Not persisted.
        active_tab_key: Full registry_key of the active bottom tab. Persisted;
            resolved against the freshly auto-populated tab list on load,
            falling back to the first tab if the key no longer exists.
        visible: Whether the bottom content area is expanded. When False, the
            BottomTabBar is still visible (as a retracted dock strip) but the
            area below it is hidden.
        size: Height of the expanded content area in pixels.
    """

    tabs: List[TabState] = field(default_factory=list)
    active_tab_key: Optional[str] = None
    visible: bool = False
    size: int = 200


@dataclass
class WorkspaceState:
    """
    Complete workspace configuration.

    Serializable to JSON for persistence. Four slots, each with its own
    bar+area, plus a workspace name.

    Attributes:
        name: Workspace name.
        haystack: Name of the last-loaded haystack (stem of the TOML file
            in ``haystacks/``), or None if no haystack has been loaded.
        left: Left slot state (ActivityBar-driven).
        right: Right slot state (ContextBar-driven).
        main: Main slot state (MainTabBar-driven, tabbed).
        bottom: Bottom slot state (BottomTabBar-driven, tabbed, retractable).
    """

    name: str = "default"
    haystack: Optional[str] = None
    left: SlotState = field(default_factory=SlotState)
    right: SlotState = field(default_factory=SlotState)
    main: MainSlotState = field(default_factory=MainSlotState)
    bottom: BottomSlotState = field(default_factory=BottomSlotState)

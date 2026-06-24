from nicegui import ui
from typing import Any, Dict, List, Optional, Callable
from haywire.core.node.info import NodeInfo
from haywire.core.node.factory import NodeFactory
from haywire.ui import elements as hui

# Above the context-menu popup card (z-index 7001); Quasar QMenu defaults to 6000.
_MENU_Z = "z-index: 7100"

# Flyout to the right of the anchor, cascading rightward for nested submenus.
_FLYOUT_PROPS = 'anchor="top end" self="top start"'


class NodeMenuBuilder:
    """Builds organized, hierarchical menus using node identity information
    from the NodeFactory, based on the menu paths defined in node decorators
    (e.g., menu='core/basic').
    """

    def __init__(
        self,
        node_factory: NodeFactory,
        on_node_selected: Callable[[NodeInfo], None],
        on_context_click: Optional[Callable[[NodeInfo], None]] = None,
    ):
        self.node_factory = node_factory
        self._on_node_selected = on_node_selected
        self._on_context_click = on_context_click
        self._menu_cache: Optional[Dict[str, List[NodeInfo]]] = None
        self._menu_tree_cache: Optional[Dict] = None

    def invalidate_cache(self):
        """Invalidate menu caches when nodes are hot-reloaded."""
        self._menu_cache = None
        self._menu_tree_cache = None

    def create_node_menu(
        self,
        recent_nodes: Optional[List[str]] = None,
        show_search: bool = True,
    ) -> ui.column:
        """
        Create a complete node menu with optional recent nodes and search.

        Args:
            recent_nodes: List of recently used node registry keys to show at top
            show_search: Whether to include search functionality

        Returns:
            ui.column containing the complete menu interface
        """
        with ui.column().classes("w-full") as menu_container:
            # Search functionality if requested
            if show_search:
                hui.input_field(
                    placeholder="Search nodes...",
                    on_change=lambda e: self._handle_search(e.value, menu_container),
                    autofocus=True,
                ).classes("w-96 mb-2")

                # Container for search results (initially hidden)
                self._search_results = ui.column().classes("w-96 gap-1").style("display: none")

            # Main menu content — the "Add Nodes" trigger and its flyout menu.
            self._main_menu = ui.column().classes("w-full")

            with self._main_menu:
                with (
                    ui.button("➕ Add Nodes")
                    .props("flat")
                    .classes("w-full hw-text-body hw-list-item-hover text-sm")
                ):
                    # Click-opened menu, raised above the popup and flown to the right.
                    with ui.menu().props(_FLYOUT_PROPS).style(_MENU_Z):
                        # Top-level flyouts are siblings: opening one closes the rest.
                        top_level: List[ui.menu] = []

                        # Recent nodes section if provided
                        if recent_nodes:
                            self._add_recent_nodes_section(recent_nodes, top_level)
                            ui.separator()

                        # Build hierarchical category tree
                        self._build_hierarchical_menu(top_level)

        return menu_container

    def _handle_search(self, query: str, container: ui.column):
        """Handle search input changes."""
        if not query.strip():
            # Show main menu, hide search results
            self._search_results.style("display: none")
            self._main_menu.style("display: block")
            return

        # Show search results, hide main menu
        self._search_results.style("display: block")
        self._main_menu.style("display: none")

        # Update search results
        self._update_search_results(query)

    def _update_search_results(self, query: str):
        """Update search results based on query."""
        # Clear previous results
        self._search_results.clear()

        # Get search results from factory
        results = self.node_factory.search_nodes(query)

        with self._search_results:
            if not results:
                ui.label("No nodes found").classes("hw-text-muted text-sm p-2")
            else:
                with ui.scroll_area():
                    ui.label(f"Found {len(results)} node(s)").classes(
                        "text-xs font-semibold hw-text-dim mb-2"
                    ).props("dense")

                    for node_info in results[:10]:  # Limit to 10 results
                        self._create_search_result_item(node_info)

    def _create_search_result_item(self, node_info: NodeInfo):
        """Create a search result item."""
        library_id = node_info.library.label if node_info.library else "Unknown"
        deprecation_warning = getattr(node_info.identity, "deprecation_warning", "")

        btn = ui.button(
            f"+ {node_info.identity.label}",
            on_click=lambda ni=node_info: self._on_node_selected(ni),
        )
        btn.props("flat dense align=left")
        btn.classes("w-full justify-start px-3 py-1.5 hw-text-body hw-list-item-hover text-sm")
        if self._on_context_click is not None:
            btn.on("contextmenu.prevent", lambda ni=node_info: self._on_context_click(ni))

        with btn:
            if deprecation_warning:
                ui.icon("warning").classes("text-amber-500 text-sm")
            ui.badge(library_id).classes("ml-auto text-xs hw-text-dim")

        tooltip_parts = [node_info.identity.description or "No description available"]
        tooltip_parts.append(f"Library: {library_id}")
        if deprecation_warning:
            tooltip_parts.append(f"⚠ Deprecated: {deprecation_warning}")
        btn.tooltip("\n".join(tooltip_parts))

    def _add_recent_nodes_section(self, recent_nodes: List[str], siblings: List[ui.menu]):
        """Add a hover-opening flyout submenu for recently created nodes."""
        if not recent_nodes:
            return

        with ui.menu_item("⏱️ Recent Nodes", auto_close=False).props("dense") as item:
            with ui.item_section().props("side"):
                ui.icon("keyboard_arrow_right")

            submenu = ui.menu().props(f"{_FLYOUT_PROPS} auto-close").style(_MENU_Z)
            with submenu:
                for registry_key in recent_nodes:
                    node_info = self.node_factory.get_node_info(registry_key)
                    if node_info:
                        self._create_menu_item_for_node(node_info)

            siblings.append(submenu)
            self._open_on_hover(item, submenu, siblings)

    def _build_hierarchical_menu(self, siblings: List[ui.menu]):
        """Build hierarchical menu using menu paths from node identities.

        ``siblings`` is the open-flyout group for this level: the top-level
        categories share it with the recent-nodes flyout so only one stays open.
        """
        # Get menu structure from factory
        menu_structure = self._get_menu_structure()

        # Build hierarchical tree
        menu_tree = self._build_menu_tree(menu_structure)

        # Create menu UI elements
        self._create_menu_tree_ui(menu_tree, siblings)

    def _get_menu_structure(self) -> Dict[str, List[NodeInfo]]:
        """Get menu structure from factory with caching."""
        if self._menu_cache is None:
            self._menu_cache = self.node_factory.get_menu_structure()
        return self._menu_cache

    def _build_menu_tree(self, menu_structure: Dict[str, List[NodeInfo]]) -> Dict:
        """Build hierarchical tree structure from flat menu paths."""
        if self._menu_tree_cache is not None:
            return self._menu_tree_cache

        tree: Dict[str, Any] = {}

        for menu_path, nodes in menu_structure.items():
            if not nodes:
                continue

            # Split menu path (e.g., 'core/basic' -> ['core', 'basic'])
            path_parts = menu_path.split("/")

            # Navigate through tree, creating structure as needed
            current_level = tree
            for i, part in enumerate(path_parts):
                part_title = part.replace("_", " ").title()

                if part_title not in current_level:
                    current_level[part_title] = {
                        "_nodes": [],
                        "_children": {},
                        "_path": "/".join(path_parts[: i + 1]),
                    }

                # If this is the final part, add the nodes
                if i == len(path_parts) - 1:
                    current_level[part_title]["_nodes"].extend(nodes)
                else:
                    current_level = current_level[part_title]["_children"]

        self._menu_tree_cache = tree
        return tree

    def _create_menu_tree_ui(self, menu_tree: Dict, siblings: List[ui.menu]):
        """Render the menu tree as a category list with nested flyout submenus.

        Each category becomes a ``ui.menu_item`` whose nested ``ui.menu``
        flyout opens on hover; direct nodes are clickable menu items, and
        subcategories recurse into further flyouts. ``siblings`` is the shared
        open-flyout group for this level (see ``_open_on_hover``).
        """
        for category_name, category_data in sorted(menu_tree.items()):
            self._create_category_submenu(category_name, category_data, siblings)

    def _create_category_submenu(self, category_name: str, category_data: Dict, siblings: List[ui.menu]):
        """Render one category as a hover-opening flyout holding its nodes and subcategories."""
        nodes: List[NodeInfo] = category_data.get("_nodes", [])
        children: Dict = category_data.get("_children", {})

        if not nodes and not children:
            return

        with ui.menu_item(f"📁 {category_name}", auto_close=False).props("dense") as item:
            with ui.item_section().props("side"):
                ui.icon("keyboard_arrow_right")

            submenu = ui.menu().props(f"{_FLYOUT_PROPS} auto-close").style(_MENU_Z)
            # Child flyouts form their own sibling group, one level deeper.
            child_siblings: List[ui.menu] = []
            with submenu:
                # Direct nodes first
                for node_info in sorted(nodes, key=lambda x: x.identity.label):
                    self._create_menu_item_for_node(node_info)

                if nodes and children:
                    ui.separator()

                # Nested subcategories
                for subcat_name, subcat_data in sorted(children.items()):
                    self._create_category_submenu(subcat_name, subcat_data, child_siblings)

            submenu._child_flyouts = child_siblings  # type: ignore[attr-defined]
            siblings.append(submenu)
            self._open_on_hover(item, submenu, siblings)

    def _create_menu_item_for_node(self, node_info: NodeInfo):
        """Create a clickable menu item for a single node."""
        deprecation_warning = getattr(node_info.identity, "deprecation_warning", "")

        menu_item = ui.menu_item(
            f"+ {node_info.identity.label}", lambda ni=node_info: self._on_node_selected(ni)
        ).props("dense")

        if self._on_context_click is not None:
            menu_item.on("contextmenu.prevent", lambda ni=node_info: self._on_context_click(ni))

        with menu_item:
            if deprecation_warning:
                ui.icon("warning").classes("text-amber-500 text-sm ml-1")

        tooltip_parts = []
        if node_info.identity.description:
            tooltip_parts.append(node_info.identity.description)
        if node_info.identity.search_tags:
            tooltip_parts.append(f"Tags: {', '.join(node_info.identity.search_tags)}")
        if deprecation_warning:
            tooltip_parts.append(f"⚠ Deprecated: {deprecation_warning}")
        if tooltip_parts:
            menu_item.tooltip("\n".join(tooltip_parts))

        return menu_item

    def _open_on_hover(self, anchor: ui.menu_item, submenu: ui.menu, siblings: List[ui.menu]) -> None:
        """Open ``submenu`` on hover of ``anchor``, closing its sibling flyouts.

        Quasar's QMenu opens on its anchor's *click*, not hover, so we open it
        explicitly on ``mouseenter``. ``auto-close`` dismisses a flyout on item
        selection or click-away, but NOT when the mouse moves to a *sibling*
        category at the same level — so each open first closes the other flyouts
        in its ``siblings`` group (and their open descendants), leaving exactly
        one open path from the root at a time. Closing on click-away is still
        left to ``auto-close``, which avoids the close-timer machinery that broke
        this under NiceGUI 3.x's render model.
        """

        def open_and_close_siblings() -> None:
            for other in siblings:
                if other is not submenu:
                    self._close_flyout(other)
            submenu.open()

        anchor.on("mouseenter", open_and_close_siblings)

    def _close_flyout(self, submenu: ui.menu) -> None:
        """Close ``submenu`` and any open descendant flyouts (depth-first)."""
        for child in getattr(submenu, "_child_flyouts", ()):
            self._close_flyout(child)
        submenu.close()

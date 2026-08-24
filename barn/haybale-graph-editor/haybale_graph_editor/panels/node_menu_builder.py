from nicegui import ui
from typing import Any, Dict, List, Optional, Callable
from haywire.core.node.info import NodeInfo
from haywire.core.node.factory import NodeFactory
from haywire.ui import elements as hui
from haywire.ui.elements.flyout import FlyoutSiblings, flyout_category


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
        with ui.column().classes("w-full gap-1") as menu_container:
            # Search functionality if requested
            if show_search:
                with ui.row().classes("w-full items-center gap-2 flex-nowrap"):
                    hui.input_field(
                        placeholder="Search nodes...",
                        on_change=lambda e: self._handle_search(e.value, menu_container),
                        autofocus=True,
                    ).classes("flex-1 max-w-xs")

                    with (
                        hui.toolbar_button(icon=hui.icon.add, tooltip="Add Node")
                        .props("flat")
                        .classes("hw-text-body hw-list-item-hover text-sm shrink-0")
                    ):
                        # Click-opened menu, raised above the popup and flown to the right.
                        with ui.menu().props(hui.FLYOUT_PROPS).style(hui.FLYOUT_Z):
                            # Top-level flyouts are siblings: opening one closes the rest.
                            top_level: FlyoutSiblings = []

                            # Recent nodes section if provided
                            if recent_nodes:
                                self._add_recent_nodes_section(recent_nodes, top_level)
                                ui.separator()

                            # Build hierarchical category tree
                            self._build_hierarchical_menu(top_level)

                # Container for search results (initially hidden), own line below the row.
                self._search_results = ui.column().classes("w-full gap-1")
                self._search_results.set_visibility(False)

        return menu_container

    def _handle_search(self, query: str, container: ui.column):
        """Handle search input changes."""
        if not query.strip():
            # Hide search results, back to the create-node button/flyout.
            self._search_results.set_visibility(False)
            return

        # Show search results.
        self._search_results.set_visibility(True)

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
                # No scroll_area: results are capped at 10, and QScrollArea's
                # internal absolute positioning would block the popup's
                # shrink-to-fit width from seeing the buttons' natural width.
                # The popup card already scrolls (`overflow: auto`) for the
                # rare case content still exceeds 90vh.
                ui.label(f"Found {len(results)} node(s)").classes(
                    "text-xs font-semibold hw-text-dim mb-2"
                ).props("dense")

                for node_info in results[:20]:  # Limit to 10 results
                    self._create_search_result_item(node_info)

    def _create_search_result_item(self, node_info: NodeInfo):
        """Create a search result item."""
        library_id = node_info.library.label if node_info.library else "Unknown"
        deprecation_warning = node_info.identity.deprecation_warning

        # Built from our own children rather than QBtn's ``label`` arg: that
        # text lands in a Quasar-owned inner <span> ``.truncate`` can't reach
        # (design-guide §3.5), and its implicit gap to the badge is `ml-auto`
        # — zero once a long name leaves no leftover space to push through.
        btn = ui.button(on_click=lambda ni=node_info: self._on_node_selected(ni))
        btn.props("flat dense align=left no-wrap")
        btn.classes("w-full justify-start px-3 py-1.5 hw-text-body hw-list-item-hover text-sm")
        if self._on_context_click is not None:
            cb = self._on_context_click
            btn.on("contextmenu.prevent", lambda ni=node_info: cb(ni))

        with btn:
            ui.label(f"+ {node_info.identity.label}").classes("truncate min-w-0 flex-1 text-left")
            if deprecation_warning:
                ui.icon("warning").classes("text-amber-500 text-sm shrink-0 ml-2")
            ui.badge(library_id).classes("shrink-0 ml-2 text-xs hw-text-dim")

        with btn:
            tip = ui.tooltip().classes("text-xs").props("no-parent-event")
            with tip:
                ui.label(node_info.identity.description or "No description available")
                ui.label(f"Library: {library_id}").classes("hw-text-dim")
                if deprecation_warning:
                    with ui.row().classes("items-center gap-1 text-amber-500 mt-1"):
                        ui.icon("warning").classes("text-sm")
                        ui.label(deprecation_warning)
        btn.on("mouseenter", lambda _: tip.run_method("show"))
        btn.on("mouseleave", lambda _: tip.run_method("hide"))

    def _add_recent_nodes_section(self, recent_nodes: List[str], siblings: FlyoutSiblings):
        """Add a hover-opening flyout submenu for recently created nodes."""
        if not recent_nodes:
            return

        with flyout_category("⏱️ Recent Nodes", siblings):
            for registry_key in recent_nodes:
                node_info = self.node_factory.get_node_info(registry_key)
                if node_info:
                    self._create_menu_item_for_node(node_info)

    def _build_hierarchical_menu(self, siblings: FlyoutSiblings):
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

    def _create_menu_tree_ui(self, menu_tree: Dict, siblings: FlyoutSiblings):
        """Render the menu tree as a category list with nested flyout submenus.

        Each category becomes a hover-opening ``flyout_category``; direct nodes
        are clickable menu items, and subcategories recurse into further flyouts.
        ``siblings`` is the shared open-flyout group for this level.
        """
        for category_name, category_data in sorted(menu_tree.items()):
            self._create_category_submenu(category_name, category_data, siblings)

    def _create_category_submenu(self, category_name: str, category_data: Dict, siblings: FlyoutSiblings):
        """Render one category as a hover-opening flyout holding its nodes and subcategories."""
        nodes: List[NodeInfo] = category_data.get("_nodes", [])
        children: Dict = category_data.get("_children", {})

        if not nodes and not children:
            return

        with flyout_category(f"📁 {category_name}", siblings) as child_siblings:
            # Direct nodes first
            for node_info in sorted(nodes, key=lambda x: x.identity.label):
                self._create_menu_item_for_node(node_info)

            if nodes and children:
                ui.separator()

            # Nested subcategories
            for subcat_name, subcat_data in sorted(children.items()):
                self._create_category_submenu(subcat_name, subcat_data, child_siblings)

    def _create_menu_item_for_node(self, node_info: NodeInfo):
        """Create a clickable menu item for a single node."""
        deprecation_warning = node_info.identity.deprecation_warning

        menu_item = ui.menu_item(
            f"+ {node_info.identity.label}", lambda ni=node_info: self._on_node_selected(ni)
        ).props("dense")

        if self._on_context_click is not None:
            cb = self._on_context_click
            menu_item.on("contextmenu.prevent", lambda ni=node_info: cb(ni))

        with menu_item:
            if deprecation_warning:
                ui.icon("warning").classes("text-amber-500 text-sm ml-1")

        has_tooltip = node_info.identity.description or node_info.identity.search_tags or deprecation_warning
        if has_tooltip:
            with menu_item:
                tip = ui.tooltip().classes("text-xs").props("no-parent-event")
                with tip:
                    if node_info.identity.description:
                        ui.label(node_info.identity.description)
                    if node_info.identity.search_tags:
                        ui.label(f"Tags: {', '.join(node_info.identity.search_tags)}").classes("hw-text-dim")
                    if deprecation_warning:
                        with ui.row().classes("items-center gap-1 text-amber-500 mt-1"):
                            ui.icon("warning").classes("text-sm")
                            ui.label(deprecation_warning)
            menu_item.on("mouseenter", lambda _: tip.run_method("show"))
            menu_item.on("mouseleave", lambda _: tip.run_method("hide"))

        return menu_item

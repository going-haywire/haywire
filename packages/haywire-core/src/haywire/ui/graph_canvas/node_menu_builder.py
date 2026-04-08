"""
This component builds organized, hierarchical menus using node identity information
from the NodeFactory, creating nested ui.menu structures based on the menu paths
defined in node decorators (e.g., menu='core/basic').
"""

from nicegui import ui
from typing import Dict, List, Optional, Callable
from haywire.core.node.factory import NodeFactory
from haywire.ui import elements as hui


class NodeMenuBuilder:
    """Builds hierarchical NiceGUI menus from NodeFactory node information."""

    def __init__(self, node_factory: NodeFactory):
        self.node_factory = node_factory
        self._menu_cache: Optional[Dict] = None
        self._menu_tree_cache: Optional[Dict] = None

    def invalidate_cache(self):
        """Invalidate menu caches when nodes are hot-reloaded."""
        self._menu_cache = None
        self._menu_tree_cache = None

    def create_node_menu(
        self,
        on_node_selected: Callable[[str], None],
        recent_nodes: Optional[List[str]] = None,
        show_search: bool = True,
    ) -> ui.column:
        """
        Create a complete node menu with optional recent nodes and search.

        Args:
            on_node_selected: Callback when a node is selected (receives registry_key)
            recent_nodes: List of recently used node registry keys to show at top
            show_search: Whether to include search functionality

        Returns:
            ui.column containing the complete menu interface
        """
        # Store the callback for use in search results
        self._on_node_selected = on_node_selected

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

            # Main menu content - "Add Nodes" button with menu
            self._main_menu = ui.column().classes("w-full")

            with self._main_menu:
                # Create "Add Nodes" button with complete menu
                with (
                    ui.button("➕ Add Nodes")
                    .props("flat")
                    .classes("w-full hw-text-body hw-list-item-hover text-sm")
                ):
                    with ui.menu():
                        # Add recent nodes section if provided
                        if recent_nodes:
                            self._add_recent_nodes_section(recent_nodes, on_node_selected)
                            ui.separator()

                        # Build hierarchical menu
                        self._build_hierarchical_menu(on_node_selected)

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
                    )

                    for node_info in results[:10]:  # Limit to 10 results
                        self._create_search_result_item(node_info)

    def _create_search_result_item(self, node_info: Dict[str, str]):
        """Create a search result item."""
        library_id = node_info.get("library", "Unknown")

        btn = ui.button(
            f"+ {node_info['label']}", on_click=lambda ni=node_info: self._on_node_selected(ni["key"])
        )
        btn.props("flat align=left")
        btn.classes(f"w-full justify-start px-3 py-2 hw-text-body hw-list-item-hover text-sm")

        # Add library badge
        with btn:
            ui.badge(library_id).classes("ml-auto text-xs hw-text-dim")

        # Enhanced tooltip
        description = node_info.get("description", "No description available")
        tooltip_text = f"{description}\nLibrary: {library_id}"
        btn.tooltip(tooltip_text)

    def _add_recent_nodes_section(self, recent_nodes: List[str], on_node_selected: Callable[[str], None]):
        """Add section for recently created nodes using native menu with hover functionality."""
        if not recent_nodes:
            return

        with ui.menu_item("⏱️ Recent Nodes", auto_close=False) as menu_item:
            with ui.item_section().props("side"):
                ui.icon("keyboard_arrow_right")

            # Create submenu that opens on hover
            submenu = ui.menu().props('anchor="top end" self="top start" auto-close')
            with submenu:
                for registry_key in recent_nodes:
                    node_info = self.node_factory.get_node_info(registry_key)
                    if node_info:
                        self._create_menu_item_for_node(node_info, on_node_selected)

            # Add hover functionality with better mouse handling
            self._add_hover_behavior(menu_item, submenu)

    def _build_hierarchical_menu(self, on_node_selected: Callable[[str], None]):
        """Build hierarchical menu using menu paths from node identities."""
        # Get menu structure from factory
        menu_structure = self._get_menu_structure()

        # Build hierarchical tree
        menu_tree = self._build_menu_tree(menu_structure)

        # Create menu UI elements
        self._create_menu_tree_ui(menu_tree, on_node_selected)

    def _get_menu_structure(self) -> Dict[str, List[Dict[str, str]]]:
        """Get menu structure from factory with caching."""
        if self._menu_cache is None:
            self._menu_cache = self.node_factory.get_menu_structure()
        return self._menu_cache

    def _build_menu_tree(self, menu_structure: Dict[str, List[Dict[str, str]]]) -> Dict:
        """Build hierarchical tree structure from flat menu paths."""
        if self._menu_tree_cache is not None:
            return self._menu_tree_cache

        tree = {}

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

    def _create_menu_tree_ui(self, menu_tree: Dict, on_node_selected: Callable[[str], None], level: int = 0):
        """Create UI elements for the menu tree using native ui.menu components."""
        for category_name, category_data in sorted(menu_tree.items()):
            nodes = category_data.get("_nodes", [])
            children = category_data.get("_children", {})

            if not nodes and not children:
                continue

            # Create menu button and associated menu
            if children and nodes:
                # Category has both subcategories and direct nodes
                self._create_mixed_category_menu(category_name, nodes, children, on_node_selected)
            elif children:
                # Category only has subcategories
                self._create_submenu_category(category_name, children, on_node_selected)
            else:
                # Category only has direct nodes
                self._create_leaf_category_menu(category_name, nodes, on_node_selected)

    def _create_mixed_category_menu(
        self, category_name: str, nodes: List[Dict], children: Dict, on_node_selected: Callable[[str], None]
    ):
        """Create menu for category that has both direct nodes and
        subcategories with hover functionality."""
        with ui.menu_item(f"📁 {category_name}", auto_close=False) as menu_item:
            with ui.item_section().props("side"):
                ui.icon("keyboard_arrow_right")

            # Create submenu that opens on hover
            submenu = ui.menu().props('anchor="top end" self="top start" auto-close')
            with submenu:
                # Add direct nodes first
                for node_info in sorted(nodes, key=lambda x: x["label"]):
                    node_item = self._create_menu_item_for_node(node_info, on_node_selected)
                    # Add hover behavior to prevent menu closing on leaf nodes
                    node_item.on("mouseenter", lambda: None)  # Keep menu open

                if nodes:  # Add separator if we have both nodes and subcategories
                    ui.separator()

                # Add subcategories
                for subcat_name, subcat_data in sorted(children.items()):
                    self._create_submenu_item(subcat_name, subcat_data, on_node_selected)

            # Add hover functionality with better mouse handling
            self._add_hover_behavior(menu_item, submenu)

    def _create_submenu_category(
        self, category_name: str, children: Dict, on_node_selected: Callable[[str], None]
    ):
        """Create menu for category that only has subcategories with hover functionality."""
        with ui.menu_item(f"📁 {category_name}", auto_close=False) as menu_item:
            with ui.item_section().props("side"):
                ui.icon("keyboard_arrow_right")

            # Create submenu that opens on hover
            submenu = ui.menu().props('anchor="top end" self="top start" auto-close')
            with submenu:
                for subcat_name, subcat_data in sorted(children.items()):
                    self._create_submenu_item(subcat_name, subcat_data, on_node_selected)

            # Add hover functionality with better mouse handling
            self._add_hover_behavior(menu_item, submenu)

    def _create_leaf_category_menu(
        self, category_name: str, nodes: List[Dict], on_node_selected: Callable[[str], None]
    ):
        """Create menu for category that only has direct nodes with hover functionality."""
        with ui.menu_item(f"📁 {category_name}", auto_close=False) as menu_item:
            with ui.item_section().props("side"):
                ui.icon("keyboard_arrow_right")

            # Create submenu that opens on hover
            submenu = ui.menu().props('anchor="top end" self="top start" auto-close')
            with submenu:
                for node_info in sorted(nodes, key=lambda x: x["label"]):
                    self._create_menu_item_for_node(node_info, on_node_selected)

            # Add hover functionality with better mouse handling
            self._add_hover_behavior(menu_item, submenu)

    def _create_submenu_item(
        self, subcat_name: str, subcat_data: Dict, on_node_selected: Callable[[str], None]
    ):
        """Create a submenu item for a subcategory with hover functionality."""
        subnodes = subcat_data.get("_nodes", [])
        subchildren = subcat_data.get("_children", {})

        if not subnodes and not subchildren:
            return

        # Create menu item with hover-triggered submenu
        with ui.menu_item(f"📁 {subcat_name}", auto_close=False) as menu_item:
            with ui.item_section().props("side"):
                ui.icon("keyboard_arrow_right")

            # Create submenu that opens on hover
            submenu = ui.menu().props('anchor="top end" self="top start" auto-close')
            with submenu:
                # Add direct nodes if any
                for node_info in sorted(subnodes, key=lambda x: x["label"]):
                    self._create_menu_item_for_node(node_info, on_node_selected)

                if subnodes and subchildren:
                    ui.separator()

                # Add nested subcategories
                for nested_name, nested_data in sorted(subchildren.items()):
                    self._create_submenu_item(nested_name, nested_data, on_node_selected)

            # Add hover functionality with better mouse handling
            self._add_hover_behavior(menu_item, submenu)

    def _create_menu_item_for_node(self, node_info: Dict[str, str], on_node_selected: Callable[[str], None]):
        """Create a menu item for a single node."""
        # Get the correct key field
        registry_key = node_info.get("registry_key") or node_info.get("key")

        menu_item = ui.menu_item(f"+ {node_info['label']}", lambda rk=registry_key: on_node_selected(rk))

        # Add tooltip with description and tags if available
        if node_info.get("description"):
            tooltip_text = node_info["description"]
            if node_info.get("search_tags"):
                tooltip_text += f"\nTags: {', '.join(node_info['search_tags'])}"
            menu_item.tooltip(tooltip_text)

        return menu_item

    def _add_hover_behavior(self, menu_item, submenu):
        """Add hover behavior with delay to prevent premature closing."""
        import asyncio

        # Store timer reference
        close_timer = None

        def open_submenu():
            nonlocal close_timer
            # Cancel any pending close timer
            if close_timer:
                close_timer.cancel()
                close_timer = None
            submenu.open()

        def schedule_close():
            nonlocal close_timer

            # Schedule closing with a longer delay
            async def delayed_close():
                await asyncio.sleep(0.8)  # Increased to 800ms delay
                submenu.close()

            if close_timer:
                close_timer.cancel()
            close_timer = asyncio.create_task(delayed_close())

        def cancel_close():
            nonlocal close_timer
            # Cancel scheduled close when mouse enters submenu
            if close_timer:
                close_timer.cancel()
                close_timer = None

        # Add hover events to menu item - only trigger close when leaving the menu item
        menu_item.on("mouseenter", open_submenu)
        menu_item.on("mouseleave", schedule_close)

        # Add hover events to submenu to prevent closing when mouse is over submenu content
        submenu.on("mouseenter", cancel_close)

        # Store the cancel_close function on the submenu so child nodes can access it
        submenu._cancel_close = cancel_close

    def _create_global_menu_leave_handler(self):
        """Create a handler that closes all open submenus when leaving the main menu area."""
        import asyncio

        async def close_all_submenus():
            await asyncio.sleep(0.5)  # Longer delay for main menu
            # This will close all open submenus
            # The individual submenu close handlers will handle their own menus
            pass

        return lambda: asyncio.create_task(close_all_submenus())

    def _create_node_button(self, node_info: Dict[str, str], on_node_selected: Callable[[str], None]):
        """Create a button for a single node (used in recent nodes section)."""
        # Get the correct key field
        registry_key = node_info.get("registry_key") or node_info.get("key")

        btn = ui.button(f"+ {node_info['label']}", on_click=lambda rk=registry_key: on_node_selected(rk))
        btn.props("flat align=left")
        btn.classes(f"w-full justify-start px-3 py-2 hw-text-body hw-list-item-hover text-sm")

        # Add tooltip with description and tags if available
        if node_info.get("description"):
            tooltip_text = node_info["description"]
            if node_info.get("search_tags"):
                tooltip_text += f"\nTags: {', '.join(node_info['search_tags'])}"
            btn.tooltip(tooltip_text)

        return btn

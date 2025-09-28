"""
NodeMenuBuilder - Creates hierarchical NiceGUI menus from NodeFactory data

This component builds organized, hierarchical menus using node identity information
from the NodeFactory, creating nested ui.menu structures based on the menu paths
defined in node decorators (e.g., menu='core/basic').
"""

from nicegui import ui
from typing import Dict, List, Optional, Callable, Any
from haywire.core.node.node_factory import NodeFactory


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
    
    def create_node_menu(self, 
                        on_node_selected: Callable[[str], None],
                        recent_nodes: Optional[List[str]] = None,
                        show_search: bool = True) -> ui.column:
        """
        Create a complete node menu with optional recent nodes and search.
        
        Args:
            on_node_selected: Callback when a node is selected (receives registry_key)
            recent_nodes: List of recently used node registry keys to show at top
            show_search: Whether to include search functionality
            
        Returns:
            ui.column containing the complete menu interface
        """
        with ui.column().classes('w-full') as menu_container:
            
            # Search functionality if requested
            if show_search:
                search_input = ui.input(
                    placeholder='Search nodes...',
                    on_change=lambda e: self._handle_search(e.value, menu_container)
                ).classes('w-full mb-2')
                
                # Container for search results (initially hidden)
                self._search_results = ui.column().classes('w-full gap-1').style('display: none')
            
            # Main menu content
            self._main_menu = ui.column().classes('w-full')
            
            with self._main_menu:
                # Add recent nodes section if provided
                if recent_nodes:
                    self._add_recent_nodes_section(recent_nodes, on_node_selected)
                    ui.separator().classes('my-2')
                
                # Build hierarchical menu
                self._build_hierarchical_menu(on_node_selected)
        
        return menu_container
    
    def _handle_search(self, query: str, container: ui.column):
        """Handle search input changes."""
        if not query.strip():
            # Show main menu, hide search results
            self._search_results.style('display: none')
            self._main_menu.style('display: block')
            return
        
        # Show search results, hide main menu
        self._search_results.style('display: block')
        self._main_menu.style('display: none')
        
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
                ui.label('No nodes found').classes('text-gray-500 text-sm p-2')
            else:
                ui.label(f'Found {len(results)} node(s)').classes('text-xs font-semibold text-gray-600 mb-2')
                
                for node_info in results[:10]:  # Limit to 10 results
                    self._create_search_result_item(node_info)
    
    def _create_search_result_item(self, node_info: Dict[str, str]):
        """Create a search result item."""
        library_name = node_info.get('library', 'Unknown')
        
        btn = ui.button(
            f"+ {node_info['label']}", 
            on_click=lambda ni=node_info: self._handle_node_selection(ni['key'])
        )
        btn.props('flat align=left')
        btn.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
        
        # Add library badge
        with btn:
            ui.badge(library_name).classes('ml-auto text-xs bg-gray-200 text-gray-600')
        
        # Enhanced tooltip
        description = node_info.get('description', 'No description available')
        tooltip_text = f"{description}\nLibrary: {library_name}"
        btn.tooltip(tooltip_text)
    
    def _add_recent_nodes_section(self, recent_nodes: List[str], on_node_selected: Callable[[str], None]):
        """Add section for recently created nodes."""
        ui.label('Recent').classes('text-xs font-semibold text-gray-600 uppercase mb-1')
        
        with ui.column().classes('w-full gap-1 ml-2'):
            for registry_key in recent_nodes:
                node_info = self.node_factory.get_node_info(registry_key)
                if node_info:
                    self._create_node_button(node_info, on_node_selected)
    
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
            path_parts = menu_path.split('/')
            
            # Navigate through tree, creating structure as needed
            current_level = tree
            for i, part in enumerate(path_parts):
                part_title = part.replace('_', ' ').title()
                
                if part_title not in current_level:
                    current_level[part_title] = {
                        '_nodes': [],
                        '_children': {},
                        '_path': '/'.join(path_parts[:i+1])
                    }
                
                # If this is the final part, add the nodes
                if i == len(path_parts) - 1:
                    current_level[part_title]['_nodes'].extend(nodes)
                else:
                    current_level = current_level[part_title]['_children']
        
        self._menu_tree_cache = tree
        return tree
    
    def _create_menu_tree_ui(self, menu_tree: Dict, on_node_selected: Callable[[str], None], level: int = 0):
        """Create UI elements for the menu tree."""
        for category_name, category_data in sorted(menu_tree.items()):
            nodes = category_data.get('_nodes', [])
            children = category_data.get('_children', {})
            
            if not nodes and not children:
                continue
            
            # Create expandable section for this category
            with ui.expansion(category_name, icon='folder').classes('w-full') as expansion:
                expansion.props('dense')
                
                # Add nodes in this category
                if nodes:
                    with ui.column().classes('w-full gap-1 ml-2'):
                        for node_info in sorted(nodes, key=lambda x: x['label']):
                            self._create_node_button(node_info, on_node_selected)
                
                # Add subcategories recursively
                if children:
                    if nodes:  # Add some spacing if we have both nodes and children
                        ui.space().classes('h-2')
                    self._create_menu_tree_ui(children, on_node_selected, level + 1)
    
    def _create_node_button(self, node_info: Dict[str, str], on_node_selected: Callable[[str], None]):
        """Create a button for a single node."""
        # Get the correct key field
        registry_key = node_info.get('registry_key') or node_info.get('key')
        
        btn = ui.button(
            f"+ {node_info['label']}", 
            on_click=lambda rk=registry_key: on_node_selected(rk)
        )
        btn.props('flat align=left')
        btn.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
        
        # Add tooltip with description and tags if available
        if node_info.get('description'):
            tooltip_text = node_info['description']
            if node_info.get('search_tags'):
                tooltip_text += f"\nTags: {', '.join(node_info['search_tags'])}"
            btn.tooltip(tooltip_text)
        
        return btn
    
    def _handle_node_selection(self, registry_key: str):
        """Handle node selection - to be overridden by container."""
        # This will be set by the callback passed to create_node_menu
        pass
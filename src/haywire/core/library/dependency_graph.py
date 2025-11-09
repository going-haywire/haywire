"""
Dependency graph management for hot-reload system
"""

import ast
import sys
import logging
from pathlib import Path
from typing import Set, List, Dict, Optional
from dataclasses import dataclass

@dataclass
class ReloadPlan:
    """Plan for reloading modules in correct order"""
    non_managed_modules: List[str]  # Helper modules to reload first
    managed_modules: List[str]       # Managed classes to reload after helpers


class DependencyGraph:
    """
    Manages dependencies for managed modules in a hot-reload system.
    
    CORE CONCEPT
    ============
    When a Python module changes, all modules that depend on it must be reloaded in the correct
    order to maintain consistency. This class tracks dependencies between managed modules (modules
    containing registered classes) and their helper modules, then generates ordered reload plans
    when changes are detected.
    
    The key insight: Build dependency trees upfront when registering modules, then use these
    pre-built trees for fast lookup when changes occur.
    
    SCOPE-BASED FILTERING
    ======================
    Each managed module can track dependencies across MULTIPLE scope prefixes. This allows
    modules to track dependencies in:
    - Their own library (always tracked)
    - Declared library dependencies (from LibraryIdentity.dependencies)
    - Core framework (haywire.core, always tracked)
    
    Example:
        Module: 'mylib.nodes.workflow'
        Library dependencies: ['otherlib', 'thirdlib']
        Scopes tracked: ['mylib.', 'otherlib.', 'thirdlib.', 'haywire.core.']
        
        Tracks:   ✅ mylib.nodes.utils (own library)
                  ✅ otherlib.types.CustomType (declared dependency)
                  ✅ haywire.core.node.BaseNode (core framework)
        Ignores:  ❌ randomlib.something (not in scope)
    
    WORKFLOW
    ========
    1. Registration Phase (called once per managed module):
       - Call add_managed_module(module_name, scope_prefix)
       - Builds complete transitive dependency tree by parsing AST
       - Stores tree for fast lookup: {module -> set of all dependencies}
    
    2. Change Detection Phase (called when file watcher detects change):
       - Call get_reload_plan(changed_module)
       - Checks which managed modules have changed_module in their dependency trees
       - Merges reload lists from all affected managed modules
       - Separates helpers (reload first) from managed modules (reload after)
       - Returns ReloadPlan with both lists in topologically sorted order
    
    3. Reload Execution Phase (handled by caller):
       - Reload helper modules using importlib.reload()
       - Reload managed modules using registry's special handling (snapshot, rollback, re-register)
    
    ALGORITHM STEPS
    ===============
    When get_reload_plan(changed_module) is called:
    
    Step 1: Determine reload order for each affected managed class
            For each managed module:
                If changed_module in dependency_tree[managed_module]:
                    reload_list = [all dependencies] + [managed_module itself]
                    
    Step 2: Merge lists from different managed classes
            Combine all reload_lists, removing duplicates
            Apply topological sort to preserve dependency order
            
    Step 3: Separate helpers from managed modules
            helpers = [modules not in _managed_modules]
            managed = [modules in _managed_modules]
            
    Step 4: Return ReloadPlan(helpers, managed)
    
    USAGE EXAMPLE
    =============
    # Setup
    dep_graph = DependencyGraph()
    
    # Register managed modules (during initial folder scan)
    dep_graph.add_managed_module(
        'mylib.nodes.workflow',
        'mylib.nodes'  # scope prefix
    )
    dep_graph.add_managed_module(
        'mylib.nodes.processor',
        'mylib.nodes'
    )
    
    # When a file changes (file watcher callback)
    reload_plan = dep_graph.get_reload_plan('mylib.nodes.utils')
    
    # Execute reload plan
    for helper in reload_plan.non_managed_modules:
        importlib.reload(sys.modules[helper])
    
    for managed in reload_plan.managed_modules:
        registry.reload_managed_class(managed)  # With snapshots, rollback, etc.
    
    DEPENDENCY TREE STRUCTURE
    =========================
    Given this file structure:
    
        nodes/
        ├── workflow.py       (managed, imports processor, validator)
        ├── processor.py      (managed, imports utils, transformers)
        ├── validator.py      (managed, imports utils)
        ├── transformers.py   (helper, imports utils, helpers)
        ├── utils.py          (helper, imports helpers)
        └── helpers.py        (helper, no dependencies)
    
    Dependency trees built:
    
        workflow: {processor, validator, utils, transformers, helpers}
        processor: {utils, transformers, helpers}
        validator: {utils, helpers}
    
    When helpers.py changes:
    
        Affected: workflow, processor, validator (all have helpers in their trees)
        Reload order: [helpers, utils, transformers, validator, processor, workflow]
        Helpers: [helpers, utils, transformers]
        Managed: [validator, processor, workflow]
    
    PERFORMANCE
    ===========
    - add_managed_module(): O(D) where D = total transitive dependencies
      Upfront cost paid once per module during registration
      
    - get_reload_plan(): O(M + N log N) where M = managed modules, N = affected modules
      Fast lookup using pre-built trees, with topological sort for ordering
    
    THREAD SAFETY
    =============
    This class is not thread-safe. It assumes single-threaded access or external synchronization.
    """
   
    def __init__(self):
        # Track which modules contain managed classes
        self._managed_modules: Set[str] = set()
        
        # Pre-built dependency trees: managed_module -> set of all dependencies (transitive)
        self._dependency_trees: Dict[str, Set[str]] = {}
        
        # Track scope prefix for each managed module: managed_module -> scope_prefix
        # Only dependencies matching this prefix are tracked
        self._module_scope_prefix: Dict[str, str] = {}
    
    def add_managed_module(self, module_name: str, scope_prefix: str):
        """
        Register a module as containing a managed class and build its dependency tree.
        
        Only dependencies that start with scope_prefix are tracked. This prevents
        tracking dependencies from parent libraries (e.g., haywire.core base classes).
        
        Args:
            module_name: The module to track (e.g., 'example.nodes.workflow')
            scope_prefix: Prefix to filter dependencies (e.g., 'example.nodes')
                         Only modules starting with this prefix will be tracked
        
        Example:
            add_managed_module(
                'example.nodes.workflow',
                'example.nodes'
            )
            # Will track: example.nodes.utils, example.nodes.helpers
            # Will NOT track: example.widgets.widget, haywire.core.node.base
        """
        self._managed_modules.add(module_name)
        self._module_scope_prefix[module_name] = scope_prefix
        
        # Build complete dependency tree for this module within the scope
        dependency_tree = self._build_dependency_tree(module_name, scope_prefix)
        self._dependency_trees[module_name] = dependency_tree
        
        logging.debug(
            f"Module '{module_name}' registered as managed with scope '{scope_prefix}' "
            f"and {len(dependency_tree)} dependencies"
        )
    
    def remove_managed_module(self, module_name: str):
        """
        Remove a managed module from tracking.
        
        Args:
            module_name: The module to remove
        """
        if module_name in self._managed_modules:
            self._managed_modules.discard(module_name)
            if module_name in self._dependency_trees:
                del self._dependency_trees[module_name]
            if module_name in self._module_scope_prefix:
                del self._module_scope_prefix[module_name]
            logging.debug(f"Module '{module_name}' removed from managed modules")
    
    def get_reload_plan(self, changed_module: str) -> ReloadPlan:
        """
        Generate a reload plan for when a module changes.
        
        Uses pre-built dependency trees to quickly determine which managed modules
        are affected and in what order everything should be reloaded.
        
        Args:
            changed_module: The module that changed
            
        Returns:
            ReloadPlan with ordered lists of modules to reload
        """
        # regenerate dependency tree if it is a managed module to catch new imports
        if changed_module in self._managed_modules:
            self.add_managed_module(changed_module, self._module_scope_prefix.get(changed_module, ''))

        # Step 1: Determine reload order for each affected managed class
        reload_lists = []
        affected_managed = []
        
        for managed_module in self._managed_modules:
            dependency_tree = self._dependency_trees.get(managed_module, set())
            
            # Check if this managed module is affected by the change
            if changed_module in dependency_tree or changed_module == managed_module:
                affected_managed.append(managed_module)
                # Build reload list: all dependencies + the managed module itself
                reload_list = list(dependency_tree) + [managed_module]
                reload_lists.append(reload_list)
        
        if not affected_managed:
            # No managed modules affected
            return ReloadPlan(non_managed_modules=[], managed_modules=[])
        
        # Step 2: Merge the lists from different managed classes
        merged_list = self._merge_reload_lists(reload_lists)
        
        # Step 3: Separate helpers from managed modules
        helpers = [m for m in merged_list if m not in self._managed_modules]
        managed = [m for m in merged_list if m in self._managed_modules]
        
        logging.debug(
            f"Reload plan for '{changed_module}': "
            f"{len(helpers)} helpers, {len(managed)} managed"
        )
        
        return ReloadPlan(
            non_managed_modules=helpers,
            managed_modules=managed
        )
    
    def _build_dependency_tree(self, module_name: str, scope_prefix: str) -> Set[str]:
        """
        Build complete transitive dependency tree for a module within a scope.
        
        Recursively follows all imports, but only tracks modules that match the scope_prefix.
        
        Args:
            module_name: The module to analyze
            scope_prefix: Only track dependencies starting with this prefix
            
        Returns:
            Set of all modules this module depends on (transitively, within scope)
        """
        all_deps = set()
        visited = set()
        to_process = [module_name]
        
        while to_process:
            current = to_process.pop()
            if current in visited:
                continue
            visited.add(current)
            
            # Extract direct dependencies within scope
            direct_deps = self._extract_direct_dependencies(current, scope_prefix)
            
            # Add new dependencies to process
            new_deps = direct_deps - visited
            to_process.extend(new_deps)
            
            # Add to result
            all_deps.update(direct_deps)
        
        # Remove the module itself from its own dependencies
        all_deps.discard(module_name)
        
        return all_deps
    
    def _merge_reload_lists(self, reload_lists: List[List[str]]) -> List[str]:
        """
        Merge multiple reload lists into a single ordered list.
        
        Preserves dependency order and removes duplicates using topological sort.
        
        Args:
            reload_lists: List of reload order lists from different managed modules
            
        Returns:
            Single merged list in correct dependency order
        """
        # Collect all unique modules
        all_modules = set()
        for reload_list in reload_lists:
            all_modules.update(reload_list)
        
        # Sort topologically to get correct reload order
        return self._topological_sort(list(all_modules))
    
    def _extract_direct_dependencies(self, module_name: str, scope_prefix: str) -> Set[str]:
        """
        Extract direct (first-order) module dependencies by parsing source code.
        
        Only returns dependencies that match the scope_prefix.
        
        Args:
            module_name: The module to analyze
            scope_prefix: Only include dependencies starting with this prefix
            
        Returns:
            Set of module names that this module directly imports (within scope only)
        """
        try:
            module = sys.modules.get(module_name)
            if not module or not hasattr(module, '__file__'):
                return set()
            
            file_path = Path(module.__file__)
            if not file_path.exists():
                return set()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(file_path))
            
            dependencies = set()
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    # import math, mylib.utils
                    for alias in node.names:
                        dep = alias.name
                        if self._is_in_scope(dep, scope_prefix):
                            dependencies.add(dep)
                
                elif isinstance(node, ast.ImportFrom):
                    # from .utils import something
                    # from mylib.nodes import Node
                    if node.module:
                        if node.level > 0:  # Relative import
                            dep = self._resolve_relative_import(
                                module_name, node.module, node.level
                            )
                            if dep and self._is_in_scope(dep, scope_prefix):
                                dependencies.add(dep)
                        else:  # Absolute import
                            if self._is_in_scope(node.module, scope_prefix):
                                dependencies.add(node.module)
                    elif node.level > 0:  # from . import something
                        dep = self._resolve_relative_import(
                            module_name, '', node.level
                        )
                        if dep and self._is_in_scope(dep, scope_prefix):
                            dependencies.add(dep)
            
            return dependencies
            
        except Exception as e:
            logging.warning(
                f"Failed to extract dependencies from '{module_name}': {e}"
            )
            return set()
    
    def _topological_sort(self, modules: List[str]) -> List[str]:
        """
        Sort modules in dependency order (dependencies before dependents).
        
        Uses Kahn's algorithm for topological sorting.
        
        Args:
            modules: List of module names to sort
            
        Returns:
            Ordered list where dependencies come before modules that use them
        """
        if not modules:
            return []
        
        # Build dependency graph for these modules
        # We need to use the scope prefix for each module
        module_set = set(modules)
        in_degree = {m: 0 for m in modules}
        edges = {m: set() for m in modules}
        
        for module in modules:
            # Get the scope prefix for this module
            # If it's managed, use its registered scope; otherwise infer from first managed module
            scope_prefix = self._module_scope_prefix.get(module)
            if not scope_prefix:
                # Find scope from any managed module that includes this in its tree
                for managed_mod, deps in self._dependency_trees.items():
                    if module in deps or module == managed_mod:
                        scope_prefix = self._module_scope_prefix.get(managed_mod)
                        break
            
            if not scope_prefix:
                # Fallback: use the module's own prefix
                parts = module.split('.')
                scope_prefix = '.'.join(parts[:-1]) if len(parts) > 1 else module
            
            # Get direct dependencies within our module set and scope
            direct_deps = self._extract_direct_dependencies(module, scope_prefix)
            local_deps = direct_deps & module_set
            
            for dep in local_deps:
                edges[dep].add(module)  # dep -> module edge
                in_degree[module] += 1
        
        # Kahn's algorithm
        queue = [m for m in modules if in_degree[m] == 0]
        result = []
        
        while queue:
            # Sort for deterministic behavior
            queue.sort()
            current = queue.pop(0)
            result.append(current)
            
            # Process modules that depend on current
            for dependent in edges[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # Check for cycles
        if len(result) != len(modules):
            logging.warning(
                f"Circular dependency detected in modules: "
                f"{set(modules) - set(result)}"
            )
            # Add remaining modules anyway (best effort)
            result.extend(m for m in modules if m not in result)
        
        return result
    
    def _is_in_scope(self, module_name: str, scope_prefix: str) -> bool:
        """
        Check if a module name is within the specified scope.
        
        Args:
            module_name: The module to check
            scope_prefix: The scope prefix (e.g., 'haywire.libraries.mylib.nodes')
            
        Returns:
            True if module_name starts with scope_prefix
        """
        return module_name.startswith(scope_prefix)
    
    def _resolve_relative_import(
        self, importing_module: str, relative_module: str, level: int
    ) -> Optional[str]:
        """
        Resolve a relative import to an absolute module name.
        
        Args:
            importing_module: The module doing the import
            relative_module: The module being imported
            level: Number of dots (1 for '.', 2 for '..', etc.)
        
        Returns:
            Absolute module name, or None if invalid
        """
        try:
            parts = importing_module.split('.')
            
            if level > len(parts):
                logging.warning(
                    f"Relative import level {level} too high for "
                    f"'{importing_module}'"
                )
                return None
            
            # Go up 'level' packages
            base_parts = parts[:-level]
            
            if relative_module:
                return '.'.join(base_parts + [relative_module])
            else:
                return '.'.join(base_parts)
                
        except Exception as e:
            logging.warning(
                f"Failed to resolve relative import in '{importing_module}': {e}"
            )
            return None
    
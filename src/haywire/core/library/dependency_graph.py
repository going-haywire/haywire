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
        Scopes tracked: ['mylib.', 'otherlib.', 'thirdlib.', 'core.']
        
        Tracks:   ✅ mylib.nodes.utils (own library)
                  ✅ otherlib.types.CustomType (declared dependency)
                  ✅ haywire.core.node.BaseNode (core framework)
        Ignores:  ❌ randomlib.something (not in scope)
    
    WORKFLOW
    ========
    1. Registration Phase (called once per managed module):
       - Call add_managed_module(module_name, scope_prefixes)
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
    
    Step 0: Check if changed_module is a managed module
            If changed_module IS managed:
                reload_list = [changed_module only]
                (helpers unchanged, no need to reload)
            Otherwise (changed_module is a helper):
                Proceed to Step 1
    
    Step 1: Find affected managed modules
            If changed_module IS managed:
                affected = [changed_module]
            Otherwise (changed_module is helper):
                affected = [all managed modules with changed_module in their dependency_tree]
    
    Step 2: Build reload plan
            If changed_module IS managed:
                helpers = []
                managed = [changed_module]
            Otherwise (changed_module is helper):
                helpers = [changed_module + all helpers that transitively depend on it]
                managed = [all affected managed modules]
            
    Step 3: Return ReloadPlan(helpers, managed)
    
    Note: We only reload what changed + the managed modules that depend on it.
          Other dependencies remain loaded and will be reused by Python's import system.
    
    USAGE EXAMPLE
    =============
    # Setup
    dep_graph = DependencyGraph()
    
    # Register managed modules (during initial folder scan)
    dep_graph.add_managed_module(
        'mylib.nodes.workflow',
        ['mylib.', 'otherlib.', 'core.']  # scope prefixes
    )
    dep_graph.add_managed_module(
        'mylib.nodes.processor',
        ['mylib.', 'otherlib.', 'core.']
    )
    
    # When a file changes (file watcher callback)
    reload_plan = dep_graph.get_reload_plan('mylib.nodes.utils')
    # OR when a cross-library dependency changes
    reload_plan = dep_graph.get_reload_plan('otherlib.types.CustomType')
    
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
        Reload order: [helpers] + [validator, processor, workflow]
        Helpers: [helpers]
        Managed: [validator, processor, workflow]
        
        Note: utils and transformers are NOT reloaded because they didn't change.
              Python will use the already-loaded versions.
    
    When workflow.py changes (a managed module):
    
        Affected: workflow only (managed modules don't trigger helper reloads)
        Reload order: [workflow]
        Helpers: []
        Managed: [workflow]
    
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
        
        # Track scope prefixes for each managed module: managed_module -> list[scope_prefix]
        # Multiple scopes allow tracking across library boundaries
        self._module_scope_prefixes: Dict[str, List[str]] = {}
        
        # Cache of direct dependencies: module -> set of direct dependencies
        # Built during add_managed_module, used for topological sorting
        self._direct_dependencies_cache: Dict[str, Set[str]] = {}
        
        # Reverse dependency map: module -> set of modules that directly depend on it
        # Key insight: We only traverse upward (who depends on X), so we only need reverse map
        # Built during add_managed_module for O(1) lookup during reload
        self._reverse_dependencies: Dict[str, Set[str]] = {}
    
    def add_managed_module(self, module_name: str, scope_prefixes: List[str]):
        """
        Register a module as containing a managed class and build its dependency tree.
        
        Dependencies matching ANY of the scope_prefixes are tracked. This allows
        cross-library dependency tracking while filtering out irrelevant modules.
        
        Args:
            module_name: The module to track (e.g., 'mylib.nodes.workflow')
            scope_prefixes: List of prefixes to filter dependencies
                           (e.g., ['mylib.', 'otherlib.', 'core.'])
                           Modules starting with any prefix will be tracked
        
        Example:
            add_managed_module(
                'mylib.nodes.workflow',
                ['mylib.', 'otherlib.', 'core.']
            )
            # Will track: mylib.nodes.utils, otherlib.types.CustomType, haywire.core.node.BaseNode
            # Will NOT track: randomlib.widget, external.package
        """
        self._managed_modules.add(module_name)
        self._module_scope_prefixes[module_name] = scope_prefixes
        
        # Build reverse dependency map by traversing all imports
        # This is a single-pass operation that builds both caches
        dep_count = self._build_reverse_dependencies(module_name, scope_prefixes)
        
        logging.debug(
            f"Module '{module_name}' registered as managed with scopes {scope_prefixes} "
            f"and {dep_count} dependencies"
        )
    
    def remove_managed_module(self, module_name: str):
        """
        Remove a managed module from tracking.
        
        Args:
            module_name: The module to remove
        """
        if module_name in self._managed_modules:
            self._managed_modules.discard(module_name)
            
            # Remove from reverse dependencies
            # Need to find all modules that this module depended on and remove the reverse link
            if module_name in self._direct_dependencies_cache:
                direct_deps = self._direct_dependencies_cache[module_name]
                for dep in direct_deps:
                    if dep in self._reverse_dependencies:
                        self._reverse_dependencies[dep].discard(module_name)
                        if not self._reverse_dependencies[dep]:
                            del self._reverse_dependencies[dep]
                del self._direct_dependencies_cache[module_name]
            
            # Remove as a dependency target
            if module_name in self._reverse_dependencies:
                del self._reverse_dependencies[module_name]
            
            if module_name in self._module_scope_prefixes:
                del self._module_scope_prefixes[module_name]
            
            logging.debug(f"Module '{module_name}' removed from managed modules")
    
    def get_reload_plan(self, changed_module: str, exclude_modules: Optional[Set[str]] = None) -> ReloadPlan:
        """
        Generate a reload plan for when a module changes.
        
        Uses pre-built dependency trees to quickly determine which managed modules
        are affected and in what order everything should be reloaded.
        
        Args:
            changed_module: The module that changed
            exclude_modules: Set of modules to exclude from reload (already reloaded)
            
        Returns:
            ReloadPlan with ordered lists of modules to reload
        """
        if exclude_modules is None:
            exclude_modules = set()
        
        # regenerate dependency tree if it is a managed module to catch new imports
        if changed_module in self._managed_modules:
            self.add_managed_module(
                changed_module, 
                self._module_scope_prefixes.get(changed_module, [])
            )

        # Step 1: Find all modules affected by the change using BFS on reverse dependencies
        to_reload = set()
        queue = [changed_module]
        visited = set()
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            to_reload.add(current)
            
            # Get all modules that directly depend on current
            dependents = self._reverse_dependencies.get(current, set())
            for dependent in dependents:
                if dependent not in visited:
                    queue.append(dependent)
        
        # Step 2: Separate helpers from managed modules
        helpers_to_reload = [m for m in to_reload if m not in self._managed_modules]
        managed_to_reload = [m for m in to_reload if m in self._managed_modules]
        
        # Step 3: Filter out excluded modules
        helpers = [m for m in helpers_to_reload if m not in exclude_modules]
        managed = [m for m in managed_to_reload if m not in exclude_modules]
        
        # Step 4: Topologically sort helpers (dependencies before dependents)
        if len(helpers) > 1:
            helpers = self._topological_sort(helpers)
        
        logging.debug(
            f"Reload plan for '{changed_module}': "
            f"{len(helpers)} helpers, {len(managed)} managed "
            f"(excluded {len(exclude_modules)} already reloaded)"
        )
        
        return ReloadPlan(
            non_managed_modules=helpers,
            managed_modules=managed
        )
    
    def _build_reverse_dependencies(self, module_name: str, scope_prefixes: List[str]) -> int:
        """
        Build reverse dependency map by traversing all imports from a managed module.
        
        This is a single-pass operation that:
        1. Caches direct dependencies for each module visited
        2. Builds reverse map: for each dependency, tracks which modules import it
        
        Args:
            module_name: The managed module to start from
            scope_prefixes: List of scope prefixes to track
            
        Returns:
            Number of dependencies found (for logging)
        """
        visited = set()
        to_process = [module_name]
        dep_count = 0
        
        while to_process:
            current = to_process.pop()
            if current in visited:
                continue
            visited.add(current)
            
            # Extract and cache direct dependencies
            direct_deps = self._extract_direct_dependencies(current, scope_prefixes)
            self._direct_dependencies_cache[current] = direct_deps
            
            # Build reverse map: for each dependency, add current as a dependent
            for dep in direct_deps:
                if dep not in self._reverse_dependencies:
                    self._reverse_dependencies[dep] = set()
                self._reverse_dependencies[dep].add(current)
                dep_count += 1
            
            # Ensure current exists in reverse map (even if no one depends on it yet)
            if current not in self._reverse_dependencies:
                self._reverse_dependencies[current] = set()
            
            # Add new dependencies to process
            new_deps = direct_deps - visited
            to_process.extend(new_deps)
        
        return dep_count
    

    
    def _extract_direct_dependencies(self, module_name: str, scope_prefixes: List[str]) -> Set[str]:
        """
        Extract direct (first-order) module dependencies by parsing source code.
        
        Only returns dependencies that match ANY of the scope_prefixes.
        
        Args:
            module_name: The module to analyze
            scope_prefixes: List of scope prefixes to include
            
        Returns:
            Set of module names that this module directly imports (within scopes only)
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
                        if self._is_in_scopes(dep, scope_prefixes):
                            dependencies.add(dep)
                
                elif isinstance(node, ast.ImportFrom):
                    # from .utils import something
                    # from mylib.nodes import Node
                    if node.module:
                        if node.level > 0:  # Relative import
                            dep = self._resolve_relative_import(
                                module_name, node.module, node.level
                            )
                            if dep and self._is_in_scopes(dep, scope_prefixes):
                                dependencies.add(dep)
                        else:  # Absolute import
                            if self._is_in_scopes(node.module, scope_prefixes):
                                dependencies.add(node.module)
                    elif node.level > 0:  # from . import something
                        dep = self._resolve_relative_import(
                            module_name, '', node.level
                        )
                        if dep and self._is_in_scopes(dep, scope_prefixes):
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
            # Get direct dependencies from cache (already built during add_managed_module)
            direct_deps = self._direct_dependencies_cache.get(module, set())
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
    
    def _is_in_scopes(self, module_name: str, scope_prefixes: List[str]) -> bool:
        """
        Check if a module name is within any of the specified scopes.
        
        Args:
            module_name: The module to check
            scope_prefixes: List of scope prefixes to check against
            
        Returns:
            True if module_name starts with any of the scope_prefixes
        """
        return any(module_name.startswith(prefix) for prefix in scope_prefixes)
    
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
    
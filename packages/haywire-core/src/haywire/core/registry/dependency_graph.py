import ast
import sys
import logging
from pathlib import Path
from typing import Set, List, Dict, Optional
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class ReloadPlan:
    """Plan for reloading modules in correct order"""

    non_managed_modules: List[str]  # Helper modules to reload first
    managed_modules: List[str]  # Managed classes to reload after helpers


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
                - Only reload the changed module + any managed modules that depend on it
                - No helper reloads needed (managed modules are self-contained)
            Otherwise (changed_module is a helper):
                - Proceed to Step 1 to find all affected modules

    Step 1: Find affected managed modules (for helper changes)
            affected = [all managed modules with changed_module in their dependency_tree]

    Step 2: Build reload plan (for helper changes)
            helpers = [changed_module + all helpers that transitively depend on it]
            managed = [all affected managed modules]

    Step 3: Sort both helpers and managed modules topologically

    Step 4: Return ReloadPlan(helpers, managed)

    Note: We only reload what changed + the modules that depend on it.
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

    When helpers.py changes (a helper module):

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

        If processor imports workflow and processor is also managed:
        Reload order: [workflow, processor]
        Helpers: []
        Managed: [workflow, processor]

    PERFORMANCE
    =======================
    - add_managed_module(): O(D × L) where D = total transitive dependencies
      Upfront cost paid once per module during registration

    - get_reload_plan(): O(L + N + E + N log N) where:
      * L = file size of changed module (must parse AST)
      * N = affected modules
      * E = edges in affected subgraph
      * N log N for topological sorting

      Breakdown:
      - O(L) for incremental dependency refresh (re-parses changed module's AST)
      - O(N + E) for BFS to find affected modules using pre-built reverse dependency map
      - O(N log N) for topological sorting of affected modules

    - _refresh_module_dependencies(): O(L) where L = file size
      Must read and parse the file, then walk AST

    THREAD SAFETY
    =============
    This class is not thread-safe. It assumes single-threaded access or external synchronization.
    """

    def __init__(self):
        # Track which modules contain managed classes
        self._managed_modules: Set[str] = set()

        # Track scope prefixes for ALL modules: module -> list[scope_prefix]
        # Multiple scopes allow tracking across library boundaries
        # Stored for both managed AND helper modules to enable proper re-scanning
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

        logger.debug(
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

            logger.debug(f"Module '{module_name}' removed from managed modules")

    def _refresh_module_dependencies(self, module_name: str, scope_prefixes: List[str]) -> None:
        """
        Incrementally refresh only direct dependencies of a module without full tree traversal.

        This is much more efficient than rebuilding the entire dependency tree when a single
        module changes. Only re-parses the changed module's AST and updates the affected edges.

        Complexity: O(L) where L = file size (must read and parse file)

        Args:
            module_name: The module whose dependencies need refreshing
            scope_prefixes: List of scope prefixes to track
        """
        old_deps = self._direct_dependencies_cache.get(module_name, set())
        new_deps = self._extract_direct_dependencies(module_name, scope_prefixes)

        # Calculate what changed
        removed = old_deps - new_deps
        added = new_deps - old_deps

        # Update reverse dependencies incrementally
        for dep in removed:
            if dep in self._reverse_dependencies:
                self._reverse_dependencies[dep].discard(module_name)
                # Clean up empty entries
                if not self._reverse_dependencies[dep]:
                    del self._reverse_dependencies[dep]

        for dep in added:
            if dep not in self._reverse_dependencies:
                self._reverse_dependencies[dep] = set()
            self._reverse_dependencies[dep].add(module_name)

            # Store scope prefixes for newly discovered modules
            if dep not in self._module_scope_prefixes:
                self._module_scope_prefixes[dep] = scope_prefixes

        # Update the cache
        self._direct_dependencies_cache[module_name] = new_deps

        logger.debug(
            f"Refreshed dependencies for '{module_name}': "
            f"+{len(added)} -{len(removed)} (total: {len(new_deps)})"
        )

    def get_reload_plan(self, changed_module: str, exclude_modules: Optional[Set[str]] = None) -> ReloadPlan:
        """
        Generate a reload plan for when a module changes.

        Uses pre-built dependency trees to quickly determine which managed modules
        are affected and in what order everything should be reloaded.

        OPTIMIZATION: If the changed module is a managed module, we only reload it and
        any managed modules that depend on it. We don't reload any helper modules because
        managed modules are self-contained registration units.

        Complexity: O(L + N + E + N log N) where:
            L = file size of changed module
            N = affected modules
            E = edges in dependency graph

        Args:
            changed_module: The module that changed
            exclude_modules: Set of modules to exclude from reload (already reloaded)

        Returns:
            ReloadPlan with ordered lists of modules to reload
        """
        if exclude_modules is None:
            exclude_modules = set()

        # STEP 0: Optimization for managed module changes
        is_managed = changed_module in self._managed_modules

        if is_managed:
            # Managed module changed - only reload it and managed modules that depend on it
            # No helpers needed because managed modules are self-contained
            if changed_module in self._module_scope_prefixes:
                scope_prefixes = self._module_scope_prefixes[changed_module]
                self._refresh_module_dependencies(changed_module, scope_prefixes)

            # Find managed modules that depend on this one
            managed_dependents = self._find_managed_dependents(changed_module)
            managed_dependents.add(changed_module)  # Include the changed module itself

            # Filter excluded
            managed = [m for m in managed_dependents if m not in exclude_modules]

            # Sort managed modules topologically
            if len(managed) > 1:
                managed = self._topological_sort(managed)

            logger.debug(f"Reload plan (managed changed): 0 helpers, {len(managed)} managed")

            return ReloadPlan(non_managed_modules=[], managed_modules=managed)

        # STEP 1: Helper changed - refresh and find ALL affected modules
        # Incrementally refresh dependencies for the changed module to catch new imports
        if changed_module in self._module_scope_prefixes:
            scope_prefixes = self._module_scope_prefixes[changed_module]
            self._refresh_module_dependencies(changed_module, scope_prefixes)
        else:
            # Module not tracked yet - might be a new file
            logger.debug(f"Module '{changed_module}' not in dependency graph, skipping refresh")

        # Use BFS with deque for O(1) popleft instead of O(n) list.pop(0)
        to_reload = set()
        queue = deque([changed_module])
        visited = set()

        while queue:
            current = queue.popleft()  # O(1) operation with deque
            if current in visited:
                continue
            visited.add(current)
            to_reload.add(current)

            # Get all modules that directly depend on current
            dependents = self._reverse_dependencies.get(current, set())
            for dependent in dependents:
                if dependent not in visited:
                    queue.append(dependent)

        # STEP 2: Separate helpers from managed modules
        helpers_to_reload = [m for m in to_reload if m not in self._managed_modules]
        managed_to_reload = [m for m in to_reload if m in self._managed_modules]

        # STEP 3: Filter out excluded modules
        helpers = [m for m in helpers_to_reload if m not in exclude_modules]
        managed = [m for m in managed_to_reload if m not in exclude_modules]

        # STEP 4: Topologically sort BOTH helpers and managed modules
        if len(helpers) > 1:
            helpers = self._topological_sort(helpers)
        if len(managed) > 1:
            managed = self._topological_sort(managed)

        logger.debug(
            f"Reload plan (helper changed): {len(helpers)} helpers, {len(managed)} managed "
            f"(excluded {len(exclude_modules)} already reloaded)"
        )

        return ReloadPlan(non_managed_modules=helpers, managed_modules=managed)

    def _find_managed_dependents(self, module_name: str) -> Set[str]:
        """
        Find all managed modules that transitively depend on the given module.

        Uses BFS to traverse the reverse dependency graph and collect only managed modules.

        Args:
            module_name: The module to find dependents for

        Returns:
            Set of managed module names that depend on module_name
        """
        managed_deps = set()
        queue = deque([module_name])
        visited = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            # Get all modules that directly depend on current
            dependents = self._reverse_dependencies.get(current, set())
            for dep in dependents:
                # Collect if it's a managed module
                if dep in self._managed_modules:
                    managed_deps.add(dep)
                # Continue traversal regardless
                if dep not in visited:
                    queue.append(dep)

        return managed_deps

    def _build_reverse_dependencies(self, module_name: str, scope_prefixes: List[str]) -> int:
        """
        Build reverse dependency map by traversing all imports from a managed module.

        This is a single-pass operation that:
        1. Caches direct dependencies for each module visited
        2. Builds reverse map: for each dependency, tracks which modules import it
        3. Stores scope prefixes for ALL modules (managed and helpers)

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

            # Store scope prefixes for this module (even if it's a helper)
            # This enables proper re-scanning when the module changes
            if current not in self._module_scope_prefixes:
                self._module_scope_prefixes[current] = scope_prefixes

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
            if not module or not module.__file__:
                return set()

            file_path = Path(module.__file__)
            if not file_path.exists():
                return set()

            with open(file_path, "r", encoding="utf-8") as f:
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
                            resolved = self._resolve_relative_import(module_name, node.module, node.level)
                            if resolved and self._is_in_scopes(resolved, scope_prefixes):
                                dependencies.add(resolved)
                        else:  # Absolute import
                            if self._is_in_scopes(node.module, scope_prefixes):
                                dependencies.add(node.module)
                    elif node.level > 0:  # from . import something
                        resolved = self._resolve_relative_import(module_name, "", node.level)
                        if resolved and self._is_in_scopes(resolved, scope_prefixes):
                            dependencies.add(resolved)

            return dependencies

        except Exception as e:
            logger.warning(f"Failed to extract dependencies from '{module_name}': {e}")
            return set()

    def _topological_sort(self, modules: List[str]) -> List[str]:
        """
        Sort modules in dependency order (dependencies before dependents).

        Uses Kahn's algorithm for topological sorting.
        Optimized to use cached dependencies directly without rebuilding.

        Complexity: O(N log N + E log D) where N = modules, E = edges, D = average out-degree
            - O(N + E) for building graph and Kahn's algorithm
            - O(N log N) for sorting queue for deterministic output

        Args:
            modules: List of module names to sort

        Returns:
            Ordered list where dependencies come before modules that use them
        """
        if not modules:
            return []

        # Build dependency graph for these modules using cached data
        module_set = set(modules)
        in_degree = {m: 0 for m in modules}
        edges: dict[str, list[str]] = {m: [] for m in modules}

        for module in modules:
            # Direct lookup from cache - already filtered by scope during building
            direct_deps = self._direct_dependencies_cache.get(module, set())
            local_deps = direct_deps & module_set

            for dep in local_deps:
                edges[dep].append(module)  # dep -> module edge
                in_degree[module] += 1

        # Kahn's algorithm with deque for efficiency
        # Sort initial queue for deterministic behavior
        queue = deque(sorted([m for m in modules if in_degree[m] == 0]))
        result = []

        while queue:
            current = queue.popleft()
            result.append(current)

            # Process modules that depend on current
            # Sort for deterministic ordering of dependents
            for dependent in sorted(edges[current]):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for cycles
        if len(result) != len(modules):
            remaining = set(modules) - set(result)
            logger.error(
                f"CIRCULAR DEPENDENCY DETECTED in modules: {remaining}. "
                f"This will likely cause reload failures. Please fix your import structure."
            )
            # Add remaining modules in sorted order for determinism
            result.extend(sorted(remaining))

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
            parts = importing_module.split(".")

            if level > len(parts):
                logger.warning(f"Relative import level {level} too high for '{importing_module}'")
                return None

            # Go up 'level' packages
            base_parts = parts[:-level]

            if relative_module:
                return ".".join(base_parts + [relative_module])
            else:
                return ".".join(base_parts)

        except Exception as e:
            logger.warning(f"Failed to resolve relative import in '{importing_module}': {e}")
            return None

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
    """Modules to reload, each list ordered so dependencies come first."""

    non_managed_modules: List[str]  # Helper modules; reload before the managed ones
    managed_modules: List[str]


class DependencyGraph:
    """Import graph behind hot-reload, answering which modules a change forces to reload.

    Register every module that holds a registered class with
    :meth:`add_managed_module`; helper modules they import are discovered by
    parsing imports and need no registration. :meth:`get_reload_plan` then
    returns the modules to reload, helpers first, each list topologically
    sorted.

    Only modules under one of a managed module's ``scope_prefixes`` are
    tracked, so imports of third-party packages are ignored. Pass the
    library's own prefix, the prefixes of its declared dependencies, and the
    framework's.

    Modules that did not change are left alone and keep their loaded state.
    Not thread-safe: call from one thread, or synchronize externally.

    Example::

        graph = DependencyGraph()
        graph.add_managed_module("mylib.nodes.workflow", ["mylib.", "otherlib.", "core."])

        plan = graph.get_reload_plan("mylib.nodes.utils")
        for helper in plan.non_managed_modules:
            importlib.reload(sys.modules[helper])
        for managed in plan.managed_modules:
            registry.reload_managed_class(managed)
    """

    def __init__(self):
        self._managed_modules: Set[str] = set()

        # Kept for helpers too, so a changed helper can be re-scanned with the
        # scopes of the managed module that pulled it in.
        self._module_scope_prefixes: Dict[str, List[str]] = {}

        self._direct_dependencies_cache: Dict[str, Set[str]] = {}

        # module -> modules importing it. Reloads only ever walk this direction.
        self._reverse_dependencies: Dict[str, Set[str]] = {}

    def add_managed_module(self, module_name: str, scope_prefixes: List[str]):
        """Register a module holding a managed class and walk its imports.

        Args:
            module_name: Dotted module path, e.g. ``'mylib.nodes.workflow'``.
            scope_prefixes: Dotted prefixes, each ending in a dot. An imported
                module is tracked when it starts with any of them, so
                ``['mylib.', 'core.']`` follows ``mylib.nodes.utils`` and
                ignores ``randomlib.widget``.

        Example::

            graph.add_managed_module("mylib.nodes.workflow", ["mylib.", "otherlib.", "core."])
        """
        self._managed_modules.add(module_name)
        self._module_scope_prefixes[module_name] = scope_prefixes

        dep_count = self._build_reverse_dependencies(module_name, scope_prefixes)

        # Restore reverse edges from modules that were already registered and
        # depend on this module.
        for other, deps in self._direct_dependencies_cache.items():
            if other != module_name and module_name in deps:
                self._reverse_dependencies[module_name].add(other)

        logger.debug(
            f"Module '{module_name}' registered as managed with scopes {scope_prefixes} "
            f"and {dep_count} dependencies"
        )

    def remove_managed_module(self, module_name: str):
        """Drop a managed module and its edges. Does nothing if it isn't registered."""
        if module_name in self._managed_modules:
            self._managed_modules.discard(module_name)

            if module_name in self._direct_dependencies_cache:
                direct_deps = self._direct_dependencies_cache[module_name]
                for dep in direct_deps:
                    if dep in self._reverse_dependencies:
                        self._reverse_dependencies[dep].discard(module_name)
                        if not self._reverse_dependencies[dep]:
                            del self._reverse_dependencies[dep]
                del self._direct_dependencies_cache[module_name]

            if module_name in self._reverse_dependencies:
                del self._reverse_dependencies[module_name]

            if module_name in self._module_scope_prefixes:
                del self._module_scope_prefixes[module_name]

            logger.debug(f"Module '{module_name}' removed from managed modules")

    def _refresh_module_dependencies(self, module_name: str, scope_prefixes: List[str]) -> None:
        """Re-read one module's imports and update only the edges that changed.

        Args:
            scope_prefixes: Prefixes deciding which imports are tracked, as in
                :meth:`add_managed_module`. Newly seen dependencies inherit them.
        """
        old_deps = self._direct_dependencies_cache.get(module_name, set())
        new_deps = self._extract_direct_dependencies(module_name, scope_prefixes)

        removed = old_deps - new_deps
        added = new_deps - old_deps

        for dep in removed:
            if dep in self._reverse_dependencies:
                self._reverse_dependencies[dep].discard(module_name)
                if not self._reverse_dependencies[dep]:
                    del self._reverse_dependencies[dep]

        for dep in added:
            if dep not in self._reverse_dependencies:
                self._reverse_dependencies[dep] = set()
            self._reverse_dependencies[dep].add(module_name)

            if dep not in self._module_scope_prefixes:
                self._module_scope_prefixes[dep] = scope_prefixes

        self._direct_dependencies_cache[module_name] = new_deps

        logger.debug(
            f"Refreshed dependencies for '{module_name}': "
            f"+{len(added)} -{len(removed)} (total: {len(new_deps)})"
        )

    def get_reload_plan(self, changed_module: str, exclude_modules: Optional[Set[str]] = None) -> ReloadPlan:
        """Return the modules to reload after ``changed_module`` was edited.

        Re-reads the changed module's imports first, so an import added since
        registration is honoured. A changed managed module yields only itself
        and the managed modules depending on it, with no helpers: a managed
        module is a self-contained registration unit.

        Args:
            changed_module: Dotted path of the edited module, managed or helper.
                One the graph has never seen comes back as the sole helper.
            exclude_modules: Modules already reloaded in this pass, left out of
                both lists.

        Returns:
            Lists topologically sorted, helpers to reload before managed modules.
        """
        if exclude_modules is None:
            exclude_modules = set()

        is_managed = changed_module in self._managed_modules

        if is_managed:
            if changed_module in self._module_scope_prefixes:
                scope_prefixes = self._module_scope_prefixes[changed_module]
                self._refresh_module_dependencies(changed_module, scope_prefixes)

            managed_dependents = self._find_managed_dependents(changed_module)
            managed_dependents.add(changed_module)

            managed = [m for m in managed_dependents if m not in exclude_modules]

            if len(managed) > 1:
                managed = self._topological_sort(managed)

            logger.debug(f"Reload plan (managed changed): 0 helpers, {len(managed)} managed")

            return ReloadPlan(non_managed_modules=[], managed_modules=managed)

        if changed_module in self._module_scope_prefixes:
            scope_prefixes = self._module_scope_prefixes[changed_module]
            self._refresh_module_dependencies(changed_module, scope_prefixes)
        else:
            logger.debug(f"Module '{changed_module}' not in dependency graph, skipping refresh")

        # Walk the reverse edges to collect everything reachable from the change.
        to_reload = set()
        queue = deque([changed_module])
        visited = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            to_reload.add(current)

            dependents = self._reverse_dependencies.get(current, set())
            for dependent in dependents:
                if dependent not in visited:
                    queue.append(dependent)

        helpers_to_reload = [m for m in to_reload if m not in self._managed_modules]
        managed_to_reload = [m for m in to_reload if m in self._managed_modules]

        helpers = [m for m in helpers_to_reload if m not in exclude_modules]
        managed = [m for m in managed_to_reload if m not in exclude_modules]

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
        """Return the managed modules transitively depending on *module_name*, excluding it."""
        managed_deps = set()
        queue = deque([module_name])
        visited = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            dependents = self._reverse_dependencies.get(current, set())
            for dep in dependents:
                if dep in self._managed_modules:
                    managed_deps.add(dep)
                # Keep walking past a managed module: helpers above it may lead to more.
                if dep not in visited:
                    queue.append(dep)

        return managed_deps

    def _build_reverse_dependencies(self, module_name: str, scope_prefixes: List[str]) -> int:
        """Walk every import reachable from *module_name*, recording edges both ways.

        Args:
            scope_prefixes: Prefixes deciding which imports are followed, as in
                :meth:`add_managed_module`. Every module reached, helpers
                included, inherits them for later re-scans.

        Returns:
            The number of edges recorded, for logging.
        """
        visited = set()
        to_process = [module_name]
        dep_count = 0

        while to_process:
            current = to_process.pop()
            if current in visited:
                continue
            visited.add(current)

            if current not in self._module_scope_prefixes:
                self._module_scope_prefixes[current] = scope_prefixes

            direct_deps = self._extract_direct_dependencies(current, scope_prefixes)
            self._direct_dependencies_cache[current] = direct_deps

            for dep in direct_deps:
                if dep not in self._reverse_dependencies:
                    self._reverse_dependencies[dep] = set()
                self._reverse_dependencies[dep].add(current)
                dep_count += 1

            if current not in self._reverse_dependencies:
                self._reverse_dependencies[current] = set()

            new_deps = direct_deps - visited
            to_process.extend(new_deps)

        return dep_count

    def _extract_direct_dependencies(self, module_name: str, scope_prefixes: List[str]) -> Set[str]:
        """Return the in-scope modules *module_name* imports directly, relative imports resolved.

        Reads the file named by the already-imported module, so an unimported
        or unreadable module yields an empty set, as does a parse failure or
        any other error, logged as a warning.

        Args:
            scope_prefixes: Prefixes an import must start with to be returned,
                as in :meth:`add_managed_module`.
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
                    for alias in node.names:
                        dep = alias.name
                        if self._is_in_scopes(dep, scope_prefixes):
                            dependencies.add(dep)

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        if node.level > 0:
                            resolved = self._resolve_relative_import(module_name, node.module, node.level)
                            if resolved and self._is_in_scopes(resolved, scope_prefixes):
                                dependencies.add(resolved)
                        else:
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
        """Order *modules* so each comes after the ones it imports.

        Only edges among the given modules count. Ties break alphabetically, so
        the same input always yields the same order. Modules caught in an import
        cycle are logged as an error and appended in sorted order.
        """
        if not modules:
            return []

        module_set = set(modules)
        in_degree = {m: 0 for m in modules}
        edges: dict[str, list[str]] = {m: [] for m in modules}

        for module in modules:
            direct_deps = self._direct_dependencies_cache.get(module, set())
            local_deps = direct_deps & module_set

            for dep in local_deps:
                edges[dep].append(module)
                in_degree[module] += 1

        # Sorted at every step so equal-rank modules come out in a stable order.
        queue = deque(sorted([m for m in modules if in_degree[m] == 0]))
        result = []

        while queue:
            current = queue.popleft()
            result.append(current)

            for dependent in sorted(edges[current]):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(modules):
            remaining = set(modules) - set(result)
            logger.error(
                f"CIRCULAR DEPENDENCY DETECTED in modules: {remaining}. "
                f"This will likely cause reload failures. Please fix your import structure."
            )
            result.extend(sorted(remaining))

        return result

    def _is_in_scopes(self, module_name: str, scope_prefixes: List[str]) -> bool:
        """True when *module_name* starts with any of *scope_prefixes*."""
        return any(module_name.startswith(prefix) for prefix in scope_prefixes)

    def _resolve_relative_import(
        self, importing_module: str, relative_module: str, level: int
    ) -> Optional[str]:
        """Return the absolute name of a relative import, or ``None``.

        Args:
            importing_module: Dotted path of the module containing the import.
            relative_module: The part after the dots, empty for ``from . import x``.
            level: Number of leading dots, 1 for ``.`` and 2 for ``..``.

        Returns:
            ``None`` when the level climbs above the top-level package, logged
            as a warning.
        """
        try:
            parts = importing_module.split(".")

            # A package is its own namespace: inside __init__.py, one dot stays
            # in the package instead of climbing out of it.
            mod = sys.modules.get(importing_module)
            mod_file: str | None = getattr(mod, "__file__", None) if mod else None
            is_package = bool(mod_file and mod_file.endswith("__init__.py"))
            effective_level = level - 1 if is_package else level

            if effective_level > len(parts):
                logger.warning(f"Relative import level {level} too high for '{importing_module}'")
                return None

            base_parts = parts if effective_level == 0 else parts[:-effective_level]

            if relative_module:
                return ".".join(base_parts + [relative_module])
            else:
                return ".".join(base_parts)

        except Exception as e:
            logger.warning(f"Failed to resolve relative import in '{importing_module}': {e}")
            return None

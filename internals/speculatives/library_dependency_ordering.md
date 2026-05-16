# Topologically-Ordered Library Enable — Design Sketch

**Status:** speculative / not scheduled
**Driver:** `HaystackState.on_enable` reads `app_data[GraphAppState]` (introduced by the GraphEditor carve-out, commit `0f467afd`). It works today because `haybale-graph-editor` happens to be enabled before `haybale-haystack` in the discovery order produced by [`LibraryRegistry.scan_for_libraries`](../../packages/haywire-core/src/haywire/core/library/registry.py). Nothing in the framework guarantees this. The `dependencies=["haybale_graph_editor"]` declaration in `@library` exists but is consumed only as a hot-reload module-prefix scope ([see registry/base.py:_get_tracked_scopes](../../packages/haywire-core/src/haywire/core/registry/base.py)) — it does NOT influence enable order. The next time someone writes an `on_enable` that needs another library's AppState, they'll either depend on discovery-order luck or hit a `container.get(...) is None` they have to defend against.

## Problem

[`LibraryRegistry.enable_all_libraries`](../../packages/haywire-core/src/haywire/core/library/registry.py) iterates `self._libraries.values()` in insertion order, which is discovery order: core libraries first, then pip-installed, then folder paths, with alphabetical or filesystem-iteration order within each group. The state container's [`on_library_enabled` catch-up dispatch](../../packages/haywire-core/src/haywire/core/state/container.py) — which instantiates every AppState of a freshly-enabled library and runs each state's `on_enable` — fires synchronously after each `library.enable()` returns, before the next library starts.

So the inter-library ordering of state instantiation is:

```
discovery order → library.enable() order → state.on_enable() order
```

A library author whose state's `on_enable` reaches into `app_data[OtherState]` is silently betting that `OtherState`'s library was discovered first.

This isn't a bug today — only one state (`HaystackState`) does this, and the order happens to work. But it's a latent trap. The fact that `identity.dependencies` exists and looks declarative makes it worse: authors will reasonably assume declaring a dep gives them ordering guarantees, when in fact it only affects hot-reload scope tracking.

## Goal

Make [`enable_all_libraries`](../../packages/haywire-core/src/haywire/core/library/registry.py) iterate in a topological order derived from `library.identity.dependencies`, so that a library's `on_enable` can rely on its declared dependencies' states already being instantiated and enabled.

## Proposed change

1. **Add a `library_id ↔ package_name` index** in `LibraryRegistry`. Today `self._libraries` is keyed by library `id` (e.g. `"haystack"`), but `identity.dependencies` lists package names (e.g. `"haybale_haystack"`). Build a side index at scan time:

    ```python
    self._libraries_by_package: Dict[str, str] = {}  # package_name → library_id
    # Populated by reading library_instance.identity.module_name at register time.
    ```

2. **Topological sort in `enable_all_libraries`**:

    ```python
    def enable_all_libraries(self):
        ordered = self._toposort_libraries()
        for library in ordered:
            library.enable()
            self._fire_library_enabled(library)

    def _toposort_libraries(self) -> list[BaseLibrary]:
        # Kahn's algorithm. Edges: dep_package → dependent_library
        # Unknown deps treated as already-satisfied (warn).
        # Cycles: log error naming the cycle members, fall back to
        #         discovery order for the cycle's members so the app
        #         still boots.
    ```

3. **Warning on missing dep:** if a library declares `dependencies=["haybale_foo"]` and `haybale_foo` isn't loaded, emit a warning at scan-completion time. This catches typos (like the `"graph_editor"` vs `"haybale_graph_editor"` bug from the carve-out — see [`.insights/project_library_dependencies_use_package_names.md`](../../.insights/project_library_dependencies_use_package_names.md)). Doesn't fail the boot.

4. **No changes** to:

    - [`LibraryStateContainer._add_app_class`](../../packages/haywire-core/src/haywire/core/state/container.py) — instantiation order within a library is already correct (instance is stored in `_app` before its `on_enable` runs).
    - `enable_library(id)` (single-library re-enable) — only runs one library at a time; no inter-library ordering question.
    - `disable_library` / `disable_all_libraries` — symmetric reverse order would be nice but isn't required for the immediate problem. Worth filing a follow-up if the symmetry matters.

## Behaviour after the change

For every pair of libraries A → B where B declares A as a dependency:

- A's `register_components`, `on_library_enable`, and every AppState's `on_enable` run completely.
- A's library_id is added to `_enabled_library_ids` in the state container.
- THEN B starts to enable.
- B's `on_enable` for any of its states can call `container.get(SomeAState)` and reliably get the live instance.

For libraries with no declared dependency relationship, order is undefined but stable (preserves discovery order among independent libraries).

## Why this is worth doing

- **Removes the latent trap.** New cross-library state references can be added without worrying about discovery order.
- **Makes `dependencies=` semantically load-bearing.** Today the field looks declarative but only affects hot-reload. After the change, it also affects enable order — matching the author's intuition.
- **Cheap.** ~30 LOC change to `LibraryRegistry`, no `state/container.py` change, no editor changes, no API surface change.
- **The warning catches the silent-typo class of bug** that bit the carve-out.

## Why not do this in the carve-out PR

The carve-out's "no haywire-core changes" property is a feature — it confines the architectural change to the barn. Topo-sort is a framework change that benefits every future cross-library state. It deserves its own PR with its own tests.

## Risks

- **Existing implicit-order dependencies.** Someone may have a library that relies on enabling after another without declaring the dep. Topo-sort doesn't break that case (independent libraries keep their relative discovery order), but it could subtly change order in a way that surfaces a previously-hidden race. Mitigation: the missing-dep warning + a release note pointing to it.
- **Cycle behavior.** A cycle is currently silently "tolerated" by the dependency check (it does nothing) but produces non-deterministic state-availability. Adding topo-sort exposes cycles. Default: warn and fall back to discovery order for cycle members; don't crash. Aggressive default would be to crash — friendlier as a `STRICT_LIBRARY_ORDER` env flag for CI.
- **Hot-reload re-enable.** When a library is disabled and then re-enabled, today's flow runs `library.enable()` once and fires the catch-up. After topo-sort it should be safe to re-enable in any order because the *other* libraries are already in `_app` — but worth confirming via test that disabling and re-enabling a depended-upon library doesn't strand its dependents.

## Suggested implementation order

1. Add the `library_id ↔ package_name` index.
2. Implement `_toposort_libraries` with cycle/missing-dep fallback + warnings.
3. Add tests: 3-library fixture where the discovery order (alphabetical) doesn't match dependency order, assert enable order is topologically correct.
4. Add a test that a cycle logs and falls back without crashing.
5. Add the missing-dep warning + a test.
6. Document in library system architecture docs.

Roughly half a day of work for someone familiar with the library system.

## Out of scope

- Reordering `disable_all_libraries` (would be the reverse topology — separate question, ask before adding).
- Making `dependencies` strictly enforced (refuse to enable B if A failed). Strict mode could be a future opt-in.
- Per-state dependencies (rather than per-library). If state-level dependency declarations were needed they'd add complexity without much benefit; the current per-library granularity is correct.

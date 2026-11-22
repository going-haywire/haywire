---
name: a-name-leaves-the-author-api-through-a-deprecation-window
description: A component API name is removed or changed incompatibly only after a minor release that deprecated it; the workbench API may change in any minor release; a deprecated name is served by a module __getattr__ that warns, and the library loader writes each notice to the error ledger
status: accepted
see-also: ADR-0084
level: framework
---

# A name leaves the Author API through a deprecation window

**Context.**

- [ADR 0084](0084-a-library-imports-the-framework-through-the-author-api.md) names the two modules a library imports from. A list of names is worth what is promised about it.
- A library author sees the studio, not the terminal: Python hides `DeprecationWarning` outside `__main__`, and shows a warning once per source location.
- Library modules are imported at two sites: the library's root module (`LibraryRegistry._load_module_and_metadata`) and each component module (`FolderScanMixin.module_scan_for_classes`), which runs again on every hot reload.

**Decision.**

- **Component API** (`haywire.api`): a name is removed or changed incompatibly only after at least one minor release in which it was deprecated, and never in a patch release. From 1.0 on, only in a major release.
- **Workbench API** (`haywire.api.workbench`): provisional. It may change in any minor release, listed in the release notes, never in a patch release. It stays provisional until a library outside this repository has built an editor on it.
- **Covered:** the name is importable, and its documented signatures, hooks and behaviour hold. **Not covered:** underscore members, undocumented attributes, anything outside the two modules.
- **A deprecated name leaves `__all__` and stays importable.** The module's `_DEPRECATED` table maps it to the object it still resolves to, its replacement and the release that removes it. The module `__getattr__` serves it and warns with `HaywireDeprecationWarning`, a `DeprecationWarning`.
- **The loader records the notice.** Both import sites run inside `recorded_deprecations`, which writes each notice as a `WARNING` to the error ledger with the module name and, where known, the library identity. A hot reload records it again.
- **The checked-in name list has a "deprecated" list per module**, so a deprecated name cannot vanish before its window ends.

**Considered.**

- *Recording through `warnings.catch_warnings(record=True)`.* It replaces process-wide filter state for the duration of an import, which is not safe while another thread imports, it swallows every other warning raised by the import, and it records the deprecation warnings of every third-party package the library imports. The notices are collected in a `ContextVar` instead, set by the loader and filled by `serve_deprecated`.
- *Relying on the warning alone.* Hidden by Python's default filters, shown once per location, and never seen in the studio.
- *No window: remove at the next minor and list it in the release notes.* A library pinned to `haywire-core>=x` breaks on install with nothing having told its author.
- *A deprecation window for the workbench API too.* It has no user outside this repository yet; a window would slow the changes that tier still needs.

**Consequences.**

- Deprecating a name is three edits: move it from `__all__` to `_DEPRECATED`, and from the name list to the deprecated list in `tests/api/names.py`.
- A name used through a module attribute at call time (`import haywire.api as api; api.Old` inside a worker) warns but is recorded only when it runs during the module's import.
- The ledger folds a repeated notice into its unread entry and counts it, so a library reloading often does not flood it.
- **One-time exception (2026-11-21):** the 0.6 naming release removes the renamed builtin names without a deprecation window. External libraries update before they run on 0.6. See D9 in [the component naming plan](https://github.com/going-haywire/haywire/blob/master/workbench/plans/2026-11-21-component-naming-scheme.md).

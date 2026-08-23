---
name: surface-id-stable-key
description: Surface-related state keys on the stable Surface.id string, not the class object, to survive hot-reload class identity churn
status: accepted
level: architectural
---

# Surface routing keys on the stable `Surface.id` string, not the class object

Panel-to-surface matching, the Properties editor's active-tab tracking, and the
surface registry all key on the `Surface.id` **string** rather than the
`Surface` class object. `PanelRegistry` compares `surface.id` when selecting
panels for a surface; `PropertiesEditor` stores the active tab as
`self._active_surface_id: str` and resolves it back to a class on each render by
id lookup; `_SURFACE_BY_ID` maps id → class and lets a re-declared class
supersede the old one under the same id on hot-reload.

## Why this shape

- **Hot-reload supersedes the class object, but the id is invariant.** When a
  library with `file_watcher=True` reloads, its `@panel` / `Surface` modules are
  re-imported and the decorators/`__init_subclass__` re-run, producing **new
  class objects** with the same declared `id`. `Surface.__init_subclass__`
  detects the same module + qualname and overwrites the `_SURFACE_BY_ID[id]`
  entry with the fresh class. Anything that held the *old* class object now
  holds a stale reference that will never be `is`-equal to the class the
  registry hands out post-reload. The string id is a value, so it survives the
  reload unchanged.
- **The editor holding the active tab can outlive a reload of the library that
  declares the surface.** `PropertiesEditor` lives in `haybale_studio`, while
  surfaces are declared by the libraries that own them. A class object pinned
  across that boundary goes stale; the id does not.
- **Active-tab state is transient and editor-local.** `_active_surface_id` lives
  only inside one `PropertiesEditor` instance and is not persisted to any slot
  snapshot or workspace state. There is no external consumer and no
  serialization boundary that a typed class reference would help; the only
  forces acting on the representation are reload-safety (favours the string) and
  IDE navigation (marginally favours the class).

Nesting keys the same way. A panel declares the surfaces it may host in
`hosts=`, and the registry resolves those edges by id, so a re-declared surface
re-enters the tree in place rather than orphaning what hangs off it. There is no
surface-to-surface parent to go stale — see ADR-0029 for the surface model
itself.

## Considered alternatives

- **Store `self._active_surface: type[Surface]` (hold the class object
  directly).** Rejected — triggers the reload hazard above directly: the active
  tab silently resets to the default surface on every hot-reload of the
  declaring library, since the held class never matches the superseded one the
  registry now hands out. The marginal IDE-navigation / refactor-rename upside
  does not justify reintroducing a stale-class-reference bug — the same failure
  class that `LibraryIdentity.dependencies` and the `_SURFACE_BY_ID` supersede
  logic exist to prevent.
- **`NewType("SurfaceId", str)` for compile-time protection.** Not adopted — the
  id flows only through a few private methods in a single file, all already
  typed `str`; the wrapper buys little over the current typing and adds ceremony
  at every call site and in the toolbar click closure.

## Consequences

- Resolving the active surface is an id → class lookup on each render, not a
  stored class reference. This is O(surfaces) per refresh, which is negligible
  and reload-safe.
- Any future cross-session persistence of the active tab should serialize the
  string id, not a class reference — the id is already the durable key.
- New surface-keyed state elsewhere should follow the same rule: key on
  `Surface.id`, resolve to a class via `surface_by_id` / registry lookup at
  point of use; do not cache `type[Surface]` across anything that can span a
  hot-reload.

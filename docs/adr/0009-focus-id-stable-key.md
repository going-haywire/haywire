---
status: accepted
---

# Focus routing keys on the stable `Focus.id` string, not the class object

Panel-to-focus matching, the Properties editor's active-tab tracking, and the
focus registry all key on the `Focus.id` **string** rather than the `Focus`
class object. `PanelRegistry` compares `focus.id` when selecting panels for a
focus; `PropertiesEditor` stores the active tab as `self._active_focus_id: str`
and resolves it back to a class on each render by id lookup; `_FOCUS_BY_ID`
maps id → class and lets a re-declared class supersede the old one under the
same id on hot-reload.

## Why this shape

- **Hot-reload supersedes the class object, but the id is invariant.** When a
  library with `file_watcher=True` reloads, its `@panel` / `Focus` modules are
  re-imported and the decorators/`__init_subclass__` re-run, producing **new
  class objects** with the same declared `id`. `Focus.__init_subclass__`
  detects the same module + qualname and overwrites the `_FOCUS_BY_ID[id]`
  entry with the fresh class (see `focus.py`). Anything that held the *old*
  class object now holds a stale reference that will never be `is`-equal to the
  class the registry hands out post-reload. The string id is a value, so it
  survives the reload unchanged.
- **The registry already commits to id-matching for focus.** `PanelRegistry`
  matches panels to a focus by `focus.id`, explicitly *"stable across
  hot-reload"*. This contrasts with `action_protocol`, which the registry
  matches by **class identity** — and that is correct there precisely because a
  panel and its action Protocol are declared in the same library scope and
  reload together, so their class objects stay mutually consistent. Focus is
  different: the editor that holds the active focus is in a *different* package
  (`haybale_studio`) from the libraries that *declare* focuses, so it can
  outlive a focus library's reload and must not pin a class object across it.
- **Active-tab state is transient and editor-local.** `_active_focus_id` lives
  only inside one `PropertiesEditor` instance and is not persisted to any slot
  snapshot or workspace state. There is no external consumer and no
  serialization boundary that a typed class reference would help; the only
  forces acting on the representation are reload-safety (favours the string) and
  IDE navigation (marginally favours the class).

## Considered alternatives

- **Store `self._active_focus: type[Focus]` (hold the class object directly).**
  Rejected — this is the reload hazard above made concrete: after a hot-reload
  of the focus-declaring library, the editor's held class no longer matches the
  superseded class from the registry, so `_active_focus` resolves to "no match"
  and the active tab silently resets to the default focus on every such reload.
  The marginal IDE-navigation / refactor-rename upside does not justify
  reintroducing a stale-class-reference bug — the same failure class that
  `LibraryIdentity.dependencies` and the `_FOCUS_BY_ID` supersede logic exist to
  prevent. (This was proposed as a "Phase 3" follow-up in the panel-system
  handoff doc and rejected on review against the code.)
- **`NewType("FocusId", str)` for compile-time protection.** Not adopted — the
  id flows only through three private methods in a single file, all already
  typed `str`; the wrapper buys little over the current typing and adds
  ceremony at every call site and in the toolbar click closure.

## Consequences

- Resolving the active focus is an id → class lookup on each render
  (`_compute_toolbar_focuses` + `focus.id` compare), not a stored class
  reference. This is O(focuses) per refresh, which is negligible and reload-safe.
- Any future cross-session persistence of the active tab should serialize the
  string id, not a class reference — the id is already the durable key.
- New focus-keyed state elsewhere should follow the same rule: key on
  `Focus.id`, resolve to a class via `focus_by_id` / registry lookup at point of
  use; do not cache `type[Focus]` across anything that can span a hot-reload.

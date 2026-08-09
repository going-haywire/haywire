# Handoff: `LibraryFileHandler` should not know about `.py`

**Status:** **DONE**, 2026-08-09. Design B landed in three commits: the
downstream guard hardened, `.py` deleted from the router, and the metadata
refresh converted to a `_HaybaleTomlWatcher` adapter on the root fallback.

Retained for the reasoning, not as a description of the code — everything below
in the present tense describes the state *before* the change. The corrections
inline are the load-bearing part: the premise that "the correctness is already
downstream" was false, and it dictated the commit order.

**Superseded by:** docs/superpowers/plans/2026-08-09-filewatcher-extension-filter-to-dispatcher.md

## What is there now

Stage 4 of the `haybale.toml` plan needed a library's own `haybale.toml` edit to
refresh its identity *without* going through the module-reload pipeline: a
metadata change is not a code change, so answering it with a debounced
re-import would be both heavyweight and wrong.

The first attempt put that knowledge in `LibraryFileHandler` — it tested for the
filename and mutated identities it found by scanning its own routing tables.
That was rejected: the handler is a router, and library metadata is not its
business.

The current shape moves the policy out, to whoever owns both the directory and
the state the file describes:

```python
# core/library/file_watcher.py:25
FileEventCallback = Callable[[str, FileEventType], bool]
```

`LibraryFileHandler.__init__` takes an optional `on_file_event`; `_claimed()`
(`:134`) offers every non-directory event to it before the `.py` routing, and
`True` means handled. `BaseLibrary` installs `self._on_watched_file`
(`base.py:61`), which claims exactly one file — its own `haybale.toml` — and
calls `_reload_metadata()` (`base.py:257`).

That is a genuine improvement: the identity search disappeared (a library has
`self.identity`, no lookup needed), the lock is gone from that path, and a
*nested* library's file is correctly declined rather than written into the
wrong identity.

## Why it is still not right

`.py` remains hardcoded in the router, in four places
(`file_watcher.py:158, 171, 184, 216-217`), plus the `_known_files` seed at
`:75` which does `rglob("*.py")`.

So the handler still asserts what kind of file matters. The callback is an
*escape hatch around* that assertion rather than a removal of it — a second
mechanism sitting beside the registry-dispatch mechanism that already exists.

### The router's filter is load-bearing today (correction)

An earlier revision of this note claimed the handler's `.py` test was "a cheap
pre-filter, not a correctness guarantee — the correctness is already
downstream." **That is wrong, and the sequencing of any fix depends on the
correction.** Downstream is *not* safe today:

1. **`_validate_python_file` raises rather than rejecting.** At
   `registry/folder_scan.py:194-206` the `try` wraps only the `open()`/`read()`
   for `OSError`. `ast.parse` sits **outside** it. Given a `.toml` or a `.png`,
   `ast.parse` raises, the exception propagates into `event_dispatcher`'s
   `except Exception` at `registry/base.py:437`, and that branch **manufactures a
   `CLASS_RELOAD_FAILED` lifecycle event** and pushes it to subscribers. A
   non-`.py` file reaching a registry surfaces as a fake reload failure in the
   error ledger, not a quiet rejection.

2. **`resolve_module_name` does not reliably yield an absent module.** It strips
   the suffix via `.stem` (`folder_scan.py:186`), so `foo/nodes.toml` resolves to
   `pkg.foo.nodes` — colliding with the real `nodes.py`, which *is* in
   `sys.modules`. That is a live mis-reload of the wrong module.

**Consequence:** step 2 below (the explicit guard) is load-bearing, not
cosmetic. It must land **before or with** step 1, never after. Doing step 1
first, on the old reasoning that downstream is already safe, opens exactly the
two failures above across every library.

## The two candidate designs

Both were sketched; the second is preferred.

### A — open the extension axis on folder mappings

Registries already register interest per folder. Widen that to per folder *and
extension*:

```python
def add_folder_mapping(self, folder_path, library_identity, registry,
                       debounce_delay=0.5, extensions=(".py",)):
```

`_get_matching_registries(path)` becomes `_get_matching_registries(path, suffix)`,
and the four `endswith` tests become "does any mapping for this path want this
suffix?".

*Costs:* `_known_files` must seed per registered extension or the
CREATE→MODIFIED downgrade misfires; and every call site of `add_folder_mapping`
/ `add_root_fallback` grows a parameter it mostly does not care about.

### B — drop the filter entirely; filter in `event_dispatcher` (preferred)

The question that settled it: *why filter for `.py` at all — what else would be
in a Python library?*

The `.py` assertion belongs to `BaseRegistry` — the consumer that actually only
handles Python modules — not to the router that merely offers files. But see the
correction above: downstream does **not** guard itself yet, so the guard must be
built before the filter is removed.

The change:

1. Harden the downstream guard first (a standalone bug fix): make
   `_validate_python_file` **return `False`** for a non-`.py` suffix and for a
   `SyntaxError`, rather than letting `ast.parse` throw.
2. Add the explicit assertion at the **top** of `BaseRegistry.event_dispatcher`:

   ```python
   if not event.file_path.endswith(".py"):
       return None  # not a Python module; nothing to reload
   ```

   **Placement is not free choice.** `event_dispatcher` calls
   `resolve_module_name` **before** `_validate_python_file` (`:389` vs `:402`),
   and skips validation entirely for `DELETED` (`:401`). A validator-only guard
   would let a `haybale.toml` DELETE sail into `_on_delete("pkg.haybale")`. The
   guard must sit above `resolve_module_name`.

   A `.py` file that fails to parse is a *different* case and keeps raising, so
   an author saving a broken module still gets its `CLASS_RELOAD_FAILED` in the
   ledger. Only non-Python files are rejected silently.
3. Only then delete `.py` from all four handler callbacks; seed `_known_files` on
   all files. The handler routes every non-directory event to whichever
   registries claim the folder.
4. Register the library's metadata reload as a normal `HotReloadRegistry` on the
   root fallback, via a small **adapter** owned by `BaseLibrary`:

   ```python
   class _HaybaleTomlWatcher(HotReloadRegistry):
       def event_dispatcher(self, event: FileChangeEvent) -> None:
           path = Path(event.file_path)
           if path.name != HAYBALE_TOML:
               return
           if path.parent != Path(self._library.identity.folder_path):
               return  # a nested library's file; its own library owns it
           self._library._reload_metadata()
   ```

5. Delete `FileEventCallback`, `_claimed()`, `_on_file_event`, and
   `BaseLibrary._on_watched_file`.

**Adapter, not inheritance.** Making `BaseLibrary` itself a `HotReloadRegistry`
was considered and rejected: a library is a plugin host, not a registry, and the
interface is one method — cheap to delegate, misleading to inherit.

**The root fallback is the correct home for the adapter (confirmed).**
`_get_matching_registries` gives folder mappings priority *and* exclusivity — if
any folder mapping matches, root fallbacks are never consulted
(`file_watcher.py:124-125`). That would starve a root-fallback adapter *if* a
library registered its own root as a component folder. None do: every
`register_components()` registers **subfolders** (`base_path / "nodes"`,
`base_path / "types"`, …). `haybale.toml` sits at the root, matches no folder
mapping, and reaches the fallback.

> **Invariant this introduces:** a library must never register its own root via
> `add_folder_to_registry`. Add the assertion that makes that explicit rather
> than tacit.

**No import cycle — skip the `HotReloadRegistry` extraction.** An earlier
revision hedged about moving `HotReloadRegistry` into `core/registry/hot_reload.py`.
There is no cycle: `library/base.py:9-12` already imports `BaseRegistry` and
`FileEventType` from `registry.base`, and nothing in `registry/base.py` imports
`library.base`. Subclass it in place — no module move, no compatibility
re-export.

## Consequences to weigh before starting

- **More events reach registries.** Every `.md`, `.json`, `.DS_Store` write
  wakes each registry to be rejected. Cheap per event, but it is a real increase
  in volume and each one starts a debounce timer. Libraries are small
  directories, so this is almost certainly fine — but measure rather than assume
  if a library ever watches something large. Note `barn/haybale-testing/`
  already contains a `.DS_Store`.
- **Debouncing starts applying to `haybale.toml`.** The callback path today is
  synchronous; going through `event_dispatcher` adds the 0.5s debounce. That is
  arguably *better* — an editor's write-burst collapses into one reload — but it
  is a behaviour change, and `tests/core/test_libraries/test_watcher_metadata_refresh.py`
  asserts synchronously today. Those tests will need to drive the debounce.
- **The CREATE→MODIFIED downgrade log** (`file_watcher.py:176`) will fire for
  non-Python files once `_known_files` covers them. Scope it or it gets noisy.

one posible way to mitigate the noise is to add a general list of filtered extensions to the `LibraryFileHandler` and log only those that are not in the list.

## Tests that will move

`tests/core/test_libraries/test_watcher_metadata_refresh.py` (11 tests) drives a
real `BaseLibrary` through its handler. The four asserting the *callback*
contract — `test_the_handler_routes_unclaimed_events_normally`,
`test_a_raising_callback_does_not_stop_the_watcher`,
`test_a_handler_without_a_callback_behaves_as_before`, and the
`_on_watched_file` claim tests — describe a mechanism design B deletes. The rest
(refresh happens, in place, no module reload, atomic-write paths, malformed file
keeps previous values, nested library declined) are behaviour that must survive
unchanged.

`tests/core/test_libraries/test_file_watcher.py` covers the `.py` routing and is
the regression net for step 1.

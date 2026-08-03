# Install blocks the event loop in enable_all_libraries()

Reported 2026-08-03: installing `haybale-visiongraph` (30+ seconds) made the
browser show a NiceGUI "connection lost" error mid-install.

Two separate causes were found. **One is fixed, this one is not.**

- Fixed: `_run_uv_streaming` read line-by-line, so uv's `\r`-updated download
  bar produced no output at all during a large download. Now splits on `\r`
  too, and the install panel has a spinner + elapsed counter that are
  independent of log output.
- **Not fixed (this document):** the heartbeat genuinely stops after the
  subprocess finishes.

## The blocking call

`LibraryManager.install()` (barn/haybale-marketplace/library_manager.py), in
the post-install sequence:

```python
await asyncio.to_thread(self.registry.scan_for_libraries)   # threaded
self.registry.enable_all_libraries()                        # NOT threaded  <-- blocks
self._invalidate_caches()                                   # NOT threaded
```

`enable_all_libraries()` imports and enables every library. For
haybale-visiongraph that pulls in depthai and opencv — seconds of synchronous
import work on the event loop, during which NiceGUI cannot answer its
heartbeat and the browser declares the connection lost.

`uninstall_streaming()` has the same shape and the same exposure.

Note this predates the stepped install flow; the flow only made it more
visible, because a step that streams live output implies liveness in a way the
old "this will take a while" progress modal did not.

## Why it was not simply threaded

`asyncio.to_thread(self.registry.enable_all_libraries)` is a one-line change,
and the line above it already does exactly that for `scan_for_libraries`. It
was held back because the enable path fans out much further than the scan
path does:

    enable_all_libraries()
      -> BaseLibrary.enable()
           -> register_components()      # library-authored
           -> _attach_to_registries()
      -> _fire_library_enabled(library)
           -> LibraryStateContainer.on_library_enabled()   (core/state/container.py:274)
                -> LibraryState.on_enable()                # library-authored

Two of those hops run **third-party code**. A grep over this repo found no
`on_enable` or `register_components` that touches NiceGUI, so threading looks
safe for the libraries we ship — but that is a snapshot of in-repo libraries,
not a guarantee about the ecosystem. A third-party `on_enable` that calls
`ui.notify()` would move from "works" to "crashes with an empty slot stack"
(see .insights/feedback_nicegui_async.md).

Also relevant, and in our favour: DI context is module-level globals, not
`ContextVar` (.insights/project_di_context.md), so a worker thread sees the
same injector. A `ContextVar`-based design would have made threading much
harder.

Worth knowing that at least one in-repo `on_enable` does real I/O:
`MarketplaceState.on_enable` calls `_auto_refresh_if_empty()`, which can make
network requests. So the enable path is *already* doing things that do not
belong on the event loop.

## Options

1. **Thread it, and document the contract**: state that `on_enable` and
   `register_components` must not call NiceGUI. Cheapest fix; makes an
   unwritten rule explicit, at the cost of possibly breaking an existing
   third-party library that violates a rule nobody had stated.
2. **Thread it, keep callbacks on the loop**: run the import-heavy
   `library.enable()` in a thread but marshal `_fire_library_enabled` back to
   the event loop. More faithful, more moving parts.
3. **Yield periodically**: `await asyncio.sleep(0)` between libraries in an
   async variant of `enable_all_libraries`. Keeps the heartbeat alive without
   moving anyone's code off the loop; does nothing for a single library whose
   import alone takes seconds (which is exactly the visiongraph case).

Option 1 is the likely answer, but it is an ecosystem-facing contract change,
so it wants an explicit decision rather than a quiet commit.

## Reproducing

Install or update `haybale-visiongraph` from the marketplace and watch the
browser console. The freeze lands *after* uv finishes — the log shows
"Scanning for libraries..." then stalls before "Enabling libraries...".

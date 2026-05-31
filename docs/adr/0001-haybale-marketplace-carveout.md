# Carve out the library manager into `haybale-marketplace`

The library install/uninstall/enable/disable orchestrator (`LibraryManager`) and its five editors (`library_browser_editor`, `library_overview_editor`, `library_component_editor`, `library_marketplace_dialog`, `component_source_editor`) move out of `haywire-studio` + `haybale-studio` into a new optional library `haybale-marketplace`. The carve-out closes a loop the marketstall spec (§3.1, §17) already anticipated: `haywire.core.marketstall` is the runtime, `haybale-marketplace` will be the consumer-facing plugin that drives it.

## Why optional, not bundled

The studio works without an installer. Editors self-register into slots via `EditorTypeRegistry`; if `haybale-marketplace` is absent, the left-slot library browser simply doesn't appear — no defensive code in `haybale-studio`. This is the architectural win the carve-out is buying: a derivative project can ship a Haywire build with no marketplace UI, or swap in a different installer, without touching the studio runtime. Workspace scaffolding (`haywire init`) installs it by default, so the default user experience is unchanged.

## Why composition, not inheritance, for `LibraryManager`

The new haybale publishes the manager via `LibraryManagerState(AppState)` as a thin holder (`state.manager.X`), not by making the manager inherit `AppState` directly. Two reasons:

1. `AppState.__init__` takes no arguments (the framework instantiates state classes via bare `cls()`), and `LibraryManager`'s current `__init__` takes `(registry, venv_path, project_dir)`. Folding the manager into the AppState would require either constructor-injection in the state container (out-of-scope framework change) or resolving everything in `on_enable()` (implicit dependencies, longer reach).
2. The ~600 LOC of uv-orchestration, DTO assembly, and dependency intelligence in `LibraryManager` is genuinely separate from the framework concerns `AppState` exists to handle (signal broadcasting, session-manager weakref, registry lifecycle). Smashing them together would be inheritance misuse.

Consumers reach the manager via `ctx.app_data[LibraryManagerState].manager.X` — one extra `.manager.` segment versus inheritance, in exchange for clean separation.

## Why persistence moves out of the manager

`apply_persisted_state` / `_persist_disabled_state` were on `LibraryManager` for historical reasons — it was the only object that held both `project_dir` and a registry reference. They are not, conceptually, manager concerns: "which libraries are currently disabled" is a property of the **registry**, not the installer. Putting them on the manager forces a mid-bootstrap mutation problem (the manager's `on_enable` fires *during* `enable_all_libraries`, but it wants to disable libraries — meaning it mutates the very phase whose end-state it cares about).

The carve-out moves the persistence concern onto the **`LibraryRegistry`** itself. The registry owns the contract end-to-end:

- `LibraryRegistry.apply_persisted_disabled_state()` is called once between `scan_for_libraries()` and `enable_all_libraries()`. It reads the user-disabled set from `HostStore` and populates `self._user_disabled`. `enable_all_libraries()` skips those ids.
- `LibraryRegistry.enable_library(id)` / `disable_library(id)` mutate `self._user_disabled` and write through to `HostStore` automatically. Every code path that toggles enable-state (the marketplace UI, the install/uninstall flow in `LibraryManager`) picks up persistence for free.

Persistence is via **`HostStore`** (`haywire.core.host.store`) — a tiny TOML-backed key/value store the host application constructs *before* the DI container and passes in as a singleton. The library registry takes it as a constructor argument; if the host supplies nothing, an in-memory store is used (writes don't hit disk). Data lives in `<workspace>/.haywire/host.toml` under `[libraries] disabled`.

### Why `HostStore` and not `FrameworkSettings`

An earlier design used a `LibraryEnableSettings(FrameworkSettings)` schema for this. That looked attractive ("one persistence mechanism, not two") but introduced a real architectural smell: the **`SettingsRegistry` configured the `LibraryRegistry`'s bootstrap (which libraries to skip), while libraries enabling later contributed schemas back to the same `SettingsRegistry`**. The same registry served two architecturally different roles — startup config vs. user/library preferences — and the bootstrap order made the cycle visible.

`HostStore` honors the boundary instead of hiding it:

- **`HostStore`** owns engine bootstrap config — what the engine reads *before it can read anything*, including which libraries to enable. No schema, no tiers, no reactivity. Generic sectioned key/value.
- **`SettingsRegistry`** keeps doing what it does for `LibrarySettings` and `FrameworkSettings`. User and library preferences.

Two mechanisms, two files (`host.toml` and `settings.toml`), each with a clear audience. The cycle goes away because the registry no longer depends on the settings system at all.

Optionality is the load-bearing property: hosts construct `HostStore` (file-backed for normal workspaces) or pass `None` (in-memory for tests, embedded uses, CI). The library registry never imposes a persistence policy — the host decides.

The marketplace UI is not a special case here. Its enable/disable buttons call `manager.registry.enable_library(id)` / `manager.registry.disable_library(id)` directly; the registry handles persistence. There is no AppState in between, no `LibraryEnableState` wrapper.

`MarketplaceState` (currently in `haybale-studio`, owner of `~/.haywire/db/haybale-marketplace/marketplace.toml` and `<project>/.haywire/marketplace.toml`) moves too, by the same logic: it's marketplace-concern state, not studio-concern state.

## Why `IProjectState.library_manager` goes away

Today, `haywire.core.session.protocols` has a `TYPE_CHECKING` reference to `haywire_studio.library_manager.LibraryManager`. That's a leak from core into a sibling package, and it hard-wires the manager into the framework contract. With the carve-out, the manager is plugin-contributed; it cannot stay in `IProjectState`. Editors that used `ctx.app.library_manager.X` migrate to `ctx.app_data[LibraryManagerState].manager.X` — the same pattern `HaystackState` and `MarketplaceState` already use.

## Why `haybale-graph-editor` doesn't depend on `haybale-marketplace`

Its single use of the manager (`ctx.app.library_manager.is_installed(...)` in `create_node_panel.py`) is vestigial. Git blame shows the conditional was originally guarding an `import` of `LibraryComponentEditor` inside the `if` body; the import was removed in a later refactor but the guard was left behind. The check is replaced with `if node_info.library is not None:` (or deleted entirely) — no cross-haybale dependency needed.

## Considered alternatives

- **Move only the editors, leave the manager in `haywire-studio`.** Smaller change, but defeats the goal: the manager would remain a hard-wired studio singleton accessible via `IProjectState`, and `haybale-marketplace` becomes a thin UI wrapper around a service it doesn't own. The optionality property (Q7) wouldn't be reachable.
- **Move the manager into `haywire-core` alongside `marketstall`.** Conceptually clean (the manager *is* the runtime arm of marketstall), but pulls `uv` subprocess invocation, `toml` writing, and venv detection into the engine. Core has stayed product-opinion-free; this would break that.
- **Make `LibraryManager` inherit `AppState` directly.** See "composition, not inheritance" above. Constructor-shape mismatch + responsibility conflation.
- **Keep persistence on the manager, time it differently with a "bootstrap complete" signal.** Preserves the architectural muddle ("manager owns persistence") that future readers would re-question. The whole point of recording this decision is to prevent that re-question.
- **Use `FrameworkSettings` (`LibraryEnableSettings`) for the disabled list.** Initially shipped, then reverted — see "Why HostStore and not FrameworkSettings" above. The single-mechanism appeal didn't survive the architectural smell: it would have required `LibraryRegistry` to read from `SettingsRegistry` at bootstrap, while libraries enabling later extended that same registry. Two distinct concerns sharing one mechanism produced a bidirectional dependency that the two-mechanism `HostStore` design cleanly avoids.

## Consequences

- `haywire-studio` is no longer the home of library install/uninstall UI. The `[project.scripts]` CLI (`haywire init`, `haywire share`) stays in `haywire-studio` for now — that decision is deferred.
- A small helper currently embedded in `library_manager.py` (`_set_decorator_list_field`, regex-rewriter for `@library(...)` decorators) moves to `haywire.core.library.decorator_io`. It is shared by `haywire share` and the marketplace Edit dialog, and neither belongs in the other's package.

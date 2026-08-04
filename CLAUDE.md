## Architecture

Haywire is a Blueprint-inspired visual programming system with a **dual-flow model**: control pins define execution order, data pins pass values.

This project uses Python with NiceGUI framework. The codebase has a haywire DI framework. Do not introduce patterns that have no existing equivalent: check in related code for existing architectural approaches before design.

When working on architecture or design patterns, do NOT assume singleton patterns, library ownership models, or registration paths. Ask for confirmation before implementing architectural decisions that affect class hierarchies or dependency injection.

## Skills & Commands

When user runs a slash command or skill, execute it immediately without asking clarifying questions. If the skill loads context, treat it as context — don't interpret it as a user request for configuration.

Before editing any file, read it first. Before modifying a function, grep for all callers. Research before you edit.

When reporting to me, be extremly concise and sacrifice grammar for the sake of concision.

### Package Layout

`.codemap/INDEX.md` provides an entry point to get a grasp on the layout of this repo.

## Documentation

When looking up how a system works (API, parameters, behaviour), check `docs/` first before reading source code. Layout:

- `docs/components/<area>/<area>-canon.md` — extension-point authoring guides (nodes, types, ports, adapters, settings, widgets, themes, editors, panels, states, libraries, haybale-package).
- `docs/architecture/<area>/<area>-arch.md` — framework internals (execution pipeline, library system, hot-reload, settings resolution, session/state, studio).
- `docs/reference/glossary.md` — canonical vocabulary, including the five distinct meanings of "library".
- `docs/reference/design-guide.md` — contains guidelines for UI design / UX rules and design tokens. Follow these when implementing new UI features or refactoring existing ones.

Run `uv run mkdocs serve` to preview the published site at `http://127.0.0.1:8000`.


## Testing

- Always run the full test suite (`pytest` or equivalent) after any refactor or multi-file change and confirm all tests pass before presenting work as complete.
- Use `force_immediate_validation()` only when you need the `ValidationResult` synchronously, or for graphs left on the default (timer) scheduler. See ADR 0002.

### Pre-edit baseline

Before any **substantial** change — multi-file refactors, signature changes, type-system edits, anything where post-edit failures would be hard to attribute — establish a baseline first:

```sh
# Lint + type-check the area about to be touched (faster than the
# full repo and surfaces only the relevant pre-existing noise).
uv run ruff check <path/to/file_or_dir>
uv run mypy <path/to/file_or_dir>
```

The code base has no errors - if this is not the case - initialze an error fix session interactively with the user. After your edit, re-run the same commands. Anything new is yours.

For trivial edits (a one-line fix, a rename inside one file, a docstring), this baseline step is unnecessary

### Commands

```sh
# Run the app
uv run haywire

# Generate deterministic library docs (README/OVERVIEW/QUICKREF/docs/*.md)
uv run haywire docs barn/haybale-mylib   # one library
uv run haywire docs --all                # every in-repo library, one load

# Tests
#
# Pick the SMALLEST tier that covers the change; run the full suite once at the
# end, not on every iteration.
uv run pytest tests/path/to/file.py       # single file — seconds; the default while iterating
uv run pytest tests/some_dir/             # one area
uv run pytest tests/ -k "edge"            # filtered by name
uv run pytest -m "not browser and not perf"  # pre-commit gate: ~2.5 min, 2985 tests
uv run pytest                             # everything incl. Playwright browser tests — slowest
uv run pytest -m integration              # integration only (full library system, slow)
uv run pytest -m unit                     # unit tests only (~1m40s, 1252 tests)
uv run pytest --cov                       # with coverage

# Running the long tiers without fighting the terminal
#
# `addopts` includes `-v`, so a full run emits thousands of lines and the tail
# is easily buried under the studio's post-run update banner. Redirect, then
# read the exit code — it is the actual pass/fail signal:
#
#   uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
#   grep -E "^FAILED|^ERROR" /tmp/t.log     # what broke
#   grep -E "passed|failed" /tmp/t.log | tail -1   # the summary line
#
# Use a timeout ≥ 600000 ms for the full suite. `--durations=25` shows where the
# time goes; anything over ~5s in the non-browser suite is worth a look — a 60s
# outlier is usually an accidental network call, not real work.

# Code quality
# CI's ruff job runs BOTH `ruff check` and `ruff format --check`. They catch
# disjoint problems, so run both locally or CI will reject what passed here.
uv run ruff check .                          # lint (line-length = 109)
uv run ruff format --check .                 # verify formatting — same as CI; fails on drift
uv run ruff format .                         # apply formatting in place to FIX drift, then re-commit
# type checking (haybale-visiongraph is a gitignored local-only symlink — excluded so this matches CI)
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

## Traps and gotchas

Things that aren't visible from the code itself — bugs we hit, framework quirks, "don't do X because Y" rules. Long-form versions live in [.insights/](.insights/); read the relevant file before debugging in that area.

### Framework gotchas (NiceGUI / Quasar / Vue 3)

- [feedback_nicegui_async.md](.insights/feedback_nicegui_async.md) — slot stack is per-asyncio-task; `asyncio.ensure_future()` makes `ui.notify()` crash. Three safe patterns.
- [feedback_nicegui_dialog_theming.md](.insights/feedback_nicegui_dialog_theming.md) — `.style()` color doesn't reach Quasar pseudo-elements; use `hui.dialog_card()` (carries `hw-panel`).
- [feedback_nicegui_autofocus.md](.insights/feedback_nicegui_autofocus.md) — autofocus in dynamic popups needs `ui.timer(0.1, ...) + run_javascript`.
- [feedback_nicegui_compact_panels.md](.insights/feedback_nicegui_compact_panels.md) — `compact-fields` utility class for dense field layouts.
- [feedback_nicegui_headless_tab_panels.md](.insights/feedback_nicegui_headless_tab_panels.md) — `ui.tab_panels` works without `ui.tabs`; keep-alive container pattern.
- [feedback_nicegui_nested_menu_flyouts.md](.insights/feedback_nicegui_nested_menu_flyouts.md) — nested `ui.menu` flyouts: 3.x drops closed-menu DOM, QMenu z-6000 < Popup z-7001, hover-open + sibling/cascade close must be wired (no close-timers).
- [project_popup_vue.md](.insights/project_popup_vue.md) — `__enter__` must return a `ui.column`; Vue 3 doesn't proxy `_`-prefixed `data()` properties.
- [feedback_nicegui_redraw_deletes_handler_slot.md](.insights/feedback_nicegui_redraw_deletes_handler_slot.md) — a row handler that mutates state then redraws its own container deletes its slot mid-flight; capture `ui.context.client` first, then `ui.notify()` under `with client:`.
- [project_nicegui_input_update_value_event.md](.insights/project_nicegui_input_update_value_event.md) — `ui.input` emits `update:value`, not `update:modelValue`; a widget binding on the wrong event silently drops all user edits in-browser. Other value elements (checkbox/switch/select/color) use `update:modelValue`.
- [feedback_nicegui_outbox_updatevalue_stomp.md](.insights/feedback_nicegui_outbox_updatevalue_stomp.md) — render-time `updateValue` messages flush after the websocket connects and stomp early user input (edit silently reverted server-side). Harness pages stamp `data-hw-synced` last; tests use `goto_ready`.
- [feedback_nicegui_lifespan_task_scope.md](.insights/feedback_nicegui_lifespan_task_scope.md) — `app.on_startup`/`on_shutdown` handlers run in different tasks; an anyio task-group context entered in one and exited in the other crashes shutdown with a cancel-scope error. Use the single-runner-task pattern (found via the MCP mount prototype).

### Test traps

- [feedback_barn_module_reload_test_trap.md](.insights/feedback_barn_module_reload_test_trap.md) — top-of-file imports of barn classes go stale after `importlib.reload`. Use `importlib.import_module` + `patch.object`.
- [project_registry_force_reload_bug.md](.insights/project_registry_force_reload_bug.md) — fixed in `7b7d86e`; symptom was `assert Foo is Foo` failing (same name, distinct objects). If it ever recurs, look for `force_reload=True` on initial registry scans.
- [project_slow_test_outliers.md](.insights/project_slow_test_outliers.md) — a multi-second test is almost always an accidental network call paid as a timeout, or serial `subprocess` spawns — not real work (`--durations=25` first). Also: `sys.modules.pop()` in a teardown deletes a pre-existing entry, causing `assert Foo is Foo` failures two files later — snapshot by prefix.
- [project_playwright_asyncio_order_trap.md](.insights/project_playwright_asyncio_order_trap.md) — the first Playwright test parks a running event loop in the main thread for the rest of the session; anyio tests after it fail. `tests/conftest.py` auto-marks `tests/ui/harness/` with `browser` and sorts browser tests last — Playwright tests elsewhere must carry `@pytest.mark.browser`. Ambient-DI leakage is contained by snapshot/restore in the `test_injector` fixtures; never call `create_test_injector()` directly in a test.

### Architecture traps

- [project_di_context.md](.insights/project_di_context.md) — DI context uses module-level globals, NOT `ContextVar`. ContextVar broke hot-reload (reload captured a different ContextVar instance than the rest of the app). Don't switch back without solving that.
- [project_settings_registry_construction_side_effects.md](.insights/project_settings_registry_construction_side_effects.md) — building a `SettingsRegistry()` is NOT inert: it repoints `FrameworkSettings._registry` and drains the global `_pending_global` queue. A throwaway registry silently steals framework-schema registration. Get it from DI; if a test must build one, snapshot/restore all three globals.
- [project_docs_gen_reentrancy.md](.insights/project_docs_gen_reentrancy.md) — `generate_docs()` builds a 2nd library system whose `initialize()` repoints the global injector + settings registry, and instantiates every node (hardware grabs!). Never call it in-process from the studio — shell out to `haywire docs --all`.
- [project_git_url_publishing_traps.md](.insights/project_git_url_publishing_traps.md) — haybales install via `git+URL` **clone**, so: gitignored files inside `barn/` are absent for consumers (unanchored `build/`/`dist/`/`env/` match at every depth), LFS assets arrive as pointer text, and `install_spec`/doc URLs are tag-pinned only when built through `SharePipeline` — a standalone call with no `tag` still floats to the current branch/default-HEAD.
- [project_stale_version_diagnosis.md](.insights/project_stale_version_diagnosis.md) — "package shows the old version": site-packages vs pyproject vs uv.lock disagree; a permissive specifier does NOT unstick a dist the lock already froze, and tracebacks from an updated-in-place studio cite code that no longer exists.
- [project_graph_canvas_connection.md](.insights/project_graph_canvas_connection.md) — `pin.flow_type.value` (`'data'`) vs `str(pin.flow_type)` (`'FlowType.DATA'`); `lastMousePos` workaround for resume-without-coords.
- [project_minimap.md](.insights/project_minimap.md) — minimap must be sibling of `ZoomPanContainer`, not child. Why `offsetLeft`/`getBoundingClientRect` don't work for node scanning.
- [project_library_dependencies_use_package_names.md](.insights/project_library_dependencies_use_package_names.md) — `@library(dependencies=[...])` takes Python package names (e.g. `"haybale_studio"`), NOT the library `id` from the same decorator. Mismatches silently break hot-reload scope tracking.
- [feedback_css_containment_node_floor.md](.insights/feedback_css_containment_node_floor.md) — a node's size floor is CSS max-content, so widget content floors its node; percentages evaporate during intrinsic sizing. Measure the floor in manual mode (auto reads `max-w-sm` 384px). `contain: size` fixes the floor but kills aspect-driven growth — prefer `contain: inline-size`.
- [project_settings_bags_include_props.md](.insights/project_settings_bags_include_props.md) — `_settings_bags` includes `props` (13 framework fields), so generic bag-walks need an explicit filter; a validator-rejected settings write is dropped silently (`min`/`max` are UI-only and NOT enforced), so writes must be verified by reading back.
- [project_haybale_studio_haywire_studio_layering.md](internals/handoff/project_haybale_studio_haywire_studio_layering.md) — handoff: `NetworkSettingsPanel` in haybale-studio imports from haywire_studio (app package), the one place a barn library reaches "up" into the app; undeclared dep (DEP003), direction unresolved.
- [project_stepper_flows.md](.insights/project_stepper_flows.md) — multi-step flows use `haywire.ui.components.stepper`; the plan/apply split must exist in the pipeline first (only the last step may write), and click handlers must RETURN the coroutine, never schedule it.

### Design rules

- [project_ui_design_system.md](.insights/project_ui_design_system.md) — anti-patterns with reasons: no hardcoded colors, no `box-shadow` on chrome, no `truncate` on QBtn, no `ui.card()` inside `ui.dialog()`.

When you discover a new trap that isn't obvious from the code, add a file to `.insights/` and a one-line entry above. Keep this list under ~20 entries — if it gets longer, demote less-load-bearing ones to a subdir `CLAUDE.md`.

## Sandcastle

The repo has an autonomous agent loop (Docker sandbox, ticket queue, review branches) — setup, usage, and model variants are documented in [.sandcastle/README.md](.sandcastle/README.md).

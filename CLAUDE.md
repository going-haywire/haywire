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

- `docs/reference/doc-authoring.md` — how to write a page in this docs site: front matter, nav wiring, and linking to live source.
- `docs/reference/glossary.md` — canonical vocabulary, including the five distinct meanings of "library".
- `docs/reference/design-guide.md` — contains guidelines for UI design / UX rules and design tokens. Follow these when implementing new UI features or refactoring existing ones.

Run `uv run mkdocs serve` to preview the published site at `http://127.0.0.1:8000`.

### Design rules

UI/UX visual rules, tokens, and anti-patterns are canonical in `docs/reference/design-guide.md` — see the Documentation section above. Do not create a second design-rules doc under `.insights/`.

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
# "Run a ruff check" / "ruff check" as a spoken instruction means BOTH commands
# below, not just the first. CI's ruff job runs BOTH `ruff check` and
# `ruff format --check` — they catch disjoint problems (lint vs formatting), so
# running only `ruff check` and calling it done is what causes CI-only failures.
uv run ruff check .                          # lint (line-length = 109)
uv run ruff format --check .                 # verify formatting — same as CI; fails on drift
uv run ruff format .                         # apply formatting in place to FIX drift, then re-commit
# type checking (haybale-visiongraph is a gitignored local-only symlink — excluded so this matches CI)
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

## Traps and gotchas

Things that aren't visible from the code itself — bugs we hit, framework quirks, "don't do X because Y" rules. Long-form versions live in [.insights/](.insights/); read the relevant file before debugging in that area.

### Framework gotchas (NiceGUI / Quasar / Vue 3)

- [feedback_nicegui_async.md](.insights/feedback_nicegui_async.md) — slot stack is per-asyncio-task; `asyncio.ensure_future()` makes `ui.notify()` crash (return the coroutine instead). Also: a handler that redraws its own container deletes its slot mid-flight — capture `ui.context.client` first, `ui.notify()` under `with client:`; and a `ui.timer` created during a draw can outlive a redrawn slot — re-parent it to a stable element.
- [feedback_nicegui_dialog_theming.md](.insights/feedback_nicegui_dialog_theming.md) — `.style()` color doesn't reach Quasar pseudo-elements; use `hui.dialog_card()` (carries `hw-panel`).
- [feedback_nicegui_compact_panels.md](.insights/feedback_nicegui_compact_panels.md) — `compact-fields` utility class for dense field layouts.
- [feedback_nicegui_headless_tab_panels.md](.insights/feedback_nicegui_headless_tab_panels.md) — `ui.tab_panels` works without `ui.tabs`; keep-alive container pattern.
- [feedback_nicegui_nested_menu_flyouts.md](.insights/feedback_nicegui_nested_menu_flyouts.md) — nested `ui.menu` flyouts: 3.x drops closed-menu DOM, QMenu z-6000 < Popup z-7001, hover-open + sibling/cascade close must be wired (no close-timers). Vue 3 doesn't proxy `_`-prefixed `data()` properties (also applies to `Popup`'s own SFC).
- [project_nicegui_input_update_value_event.md](.insights/project_nicegui_input_update_value_event.md) — `ui.input` emits `update:value`, not `update:modelValue`; a widget binding on the wrong event silently drops all user edits in-browser. Other value elements (checkbox/switch/select/color) use `update:modelValue`.
- [feedback_nicegui_outbox_updatevalue_stomp.md](.insights/feedback_nicegui_outbox_updatevalue_stomp.md) — render-time `updateValue` messages flush after the websocket connects and stomp early user input (edit silently reverted server-side). Harness pages stamp `data-hw-synced` last; tests use `goto_ready`. Also: autofocus into a dynamically-shown popup silently no-ops — needs `ui.timer(0.1, ...) + run_javascript`.
- [feedback_nicegui_lifespan_task_scope.md](.insights/feedback_nicegui_lifespan_task_scope.md) — `app.on_startup`/`on_shutdown` handlers run in different tasks; an anyio task-group context entered in one and exited in the other crashes shutdown with a cancel-scope error. Use the single-runner-task pattern (found via the MCP mount prototype).
- [feedback_clipboard_secure_context.md](.insights/feedback_clipboard_secure_context.md) — secure-context APIs are absent on a LAN-exposed studio over http (localhost is secure, a LAN IP isn't — so it always works where you test it). Nothing shipped is broken by this today: clipboard is **fixed** (execCommand fallback) and camera/mic never applied (capture is server-side Python). Don't cite either as a symptom of plain HTTP — it bites only a future front-end `mediaDevices`/geolocation feature.

### Test traps

- [feedback_barn_module_reload_test_trap.md](.insights/feedback_barn_module_reload_test_trap.md) — top-of-file imports of barn classes go stale after `importlib.reload`. Use `importlib.import_module` + `patch.object`.
- [project_slow_test_outliers.md](.insights/project_slow_test_outliers.md) — a multi-second test is almost always an accidental network call paid as a timeout, or serial `subprocess` spawns — not real work (`--durations=25` first). Also: `sys.modules.pop()` in a teardown deletes a pre-existing entry, causing `assert Foo is Foo` failures two files later — snapshot by prefix. Same signature's historical case (fixed): `BaseRegistry` force-reload on initial scan, fixed in `7b7d86e`.
- [project_playwright_asyncio_order_trap.md](.insights/project_playwright_asyncio_order_trap.md) — the first Playwright test parks a running event loop in the main thread for the rest of the session; anyio tests after it fail. `tests/conftest.py` auto-marks `tests/ui/harness/` with `browser` and sorts browser tests last — Playwright tests elsewhere must carry `@pytest.mark.browser`. Ambient-DI leakage is contained by snapshot/restore in the `test_injector` fixtures; never call `create_test_injector()` directly in a test.
- [feedback_nicegui_user_simulation_find.md](.insights/feedback_nicegui_user_simulation_find.md) — `user.find("Text", kind=ui.button)` silently ignores `kind` and clicks the lowest-id match (often a label), so the handler never fires; use `find(kind=..., content=...)`. Also: `ui.context.client` raises in the test body (use `user._client`).
- [project_docs_test_reverts_barn_testing.md](.insights/project_docs_test_reverts_barn_testing.md) — `tests/studio/test_docs/test_generate.py`'s teardown runs `git checkout -- barn/haybale-testing`, silently discarding ANY uncommitted edit there (and deleting untracked files). Commit work under that dir before running the suite; a green run is not proof it survived (`sys.modules` masks the damage until the next run).

### Architecture traps

- [project_di_context.md](.insights/project_di_context.md) — DI context uses module-level globals, NOT `ContextVar`. ContextVar broke hot-reload (reload captured a different ContextVar instance than the rest of the app). Don't switch back without solving that.
- [project_settings_registry_construction_side_effects.md](.insights/project_settings_registry_construction_side_effects.md) — building a `SettingsRegistry()` is NOT inert: it repoints `FrameworkSettings._registry` and drains the global `_pending_global` queue. A throwaway registry silently steals framework-schema registration. Get it from DI; if a test must build one, snapshot/restore all three globals.
- [project_docs_gen_reentrancy.md](.insights/project_docs_gen_reentrancy.md) — `generate_docs()` builds a 2nd library system whose `initialize()` repoints the global injector + settings registry, and instantiates every node (hardware grabs!). Never call it in-process from the studio — shell out to `haywire docs --all`.
- [project_git_url_publishing_traps.md](.insights/project_git_url_publishing_traps.md) — haybales install via `git+URL` **clone**, so: gitignored files inside `barn/` are absent for consumers (unanchored `build/`/`dist/`/`env/` match at every depth), LFS assets arrive as pointer text, and `install_spec`/doc URLs are tag-pinned only when built through `SharePipeline` — a standalone call with no `tag` still floats to the current branch/default-HEAD.
- [project_stale_version_diagnosis.md](.insights/project_stale_version_diagnosis.md) — "package shows the old version": site-packages vs pyproject vs uv.lock disagree; a permissive specifier does NOT unstick a dist the lock already froze, and tracebacks from an updated-in-place studio cite code that no longer exists.
- Canvas pin DOM attributes: use `pin.flow_type.value` (e.g. `'data'`), never `str(pin.flow_type)` (`'FlowType.DATA'`) — see `node_skin.py`. Relatedly, [project_layout_direction_pin_contract.md](.insights/project_layout_direction_pin_contract.md) — a pin's CSS side and its `data-pin-dir-x/y` vector must both come from `LayoutDirection`; a mismatch is silent (right edge, wrong curves). Skin-authoring side is in `docs/components/skins/skin-canon.md`.
- [project_library_dependencies_use_package_names.md](.insights/project_library_dependencies_use_package_names.md) — `@library(dependencies=[...])` takes Python package names (e.g. `"haybale_studio"`), NOT the library `id` from the same decorator. Mismatches silently break hot-reload scope tracking.
- [feedback_css_containment_node_floor.md](.insights/feedback_css_containment_node_floor.md) — a node's size floor is CSS max-content, so widget content floors its node; percentages evaporate during intrinsic sizing. Measure the floor in manual mode (auto reads `max-w-sm` 384px). `contain: size` fixes the floor but kills aspect-driven growth — prefer `contain: inline-size`.
- [project_settings_bags_include_props.md](.insights/project_settings_bags_include_props.md) — `_settings_bags` includes `props` (13 framework fields), so generic bag-walks need an explicit filter; a validator-rejected settings write is dropped silently (`min`/`max` are UI-only and NOT enforced), so writes must be verified by reading back.
- [project_app_library_dependency_direction.md](.insights/project_app_library_dependency_direction.md) — barn libraries may depend on `haywire-studio`; the app must NEVER depend on a barn library (cycle). Only a library can register components, so app-owned state needing a panel/tool imports "up". Declare in pyproject only, never `linked_libraries`; baseline presence comes from the project scaffold.
- [project_stepper_flows.md](.insights/project_stepper_flows.md) — multi-step flows use `haywire.ui.components.stepper`; the plan/apply split must exist in the pipeline first (only the last step may write), and click handlers must RETURN the coroutine, never schedule it.
- [project_surface_popup_emptiness_contract.md](.insights/project_surface_popup_emptiness_contract.md) — a hosting panel polling true only means it drew its own layout, not that anything landed inside it; context-menu emptiness is decided by rendering the whole tree and counting leaves (`counting_leaves()`), not by the root panel list. Symptom of getting this wrong: an edge-drag that never resumes, arbitrarily far from the cause.

When you discover a new trap that isn't obvious from the code, add a file to `.insights/` and a one-line entry above. Keep this list under ~20 entries — if it gets longer, demote less-load-bearing ones to a subdir `CLAUDE.md`.

## Sandcastle

The repo has an autonomous agent loop (Docker sandbox, ticket queue, review branches) — setup, usage, and model variants are documented in [.sandcastle/README.md](.sandcastle/README.md).

# Module: Tests

> pytest suite organised by area: core (engine subsystems), ui, graph_editor, studio, libraries, barn, marketplace, marketstall, models, audio, image, share, farmhand, security, auth and integration. Aims for full coverage of `haywire-core`; uses markers to separate fast tests from slow integration runs.

**Path:** `tests/`
**Language:** Python 3.10+ (pytest)
**Owner:** All teams (each owns tests near their module)
**Tree hash:** `db337c6bfd89c189b239a5975f3ce71fd48a55ed`
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

The test suite covers the framework and every bundled library. Tests are grouped by the module they exercise. `tests/README.md` is the authority for test tiers, parallelism and known traps; this manifest only maps the layout. Breaking the suite means no change can be verified locally. CI runs the full suite on every push.

## 2. Folder Architecture

```
tests/
├── conftest.py                  ← root shared fixtures (DI reset, library reload helpers)
├── barn/                        ← bundled-library tests (builtin, haybale-core behavior)
├── core/                        ← haywire-core engine tests, one dir per subsystem:
│   ├── test_access/ test_assembly/ test_authoring/ test_catalog/ test_debug/ test_di/
│   ├── test_docs/ test_edge/ test_errors/ test_execution/ test_farmhand/ test_graph/
│   ├── test_libraries/ test_library/ test_macro/ test_node/ test_registry/ test_session/
│   ├── test_settings/ (single-cell + promotion characterization suites, own conftest.py)
│   ├── test_signals/ test_skin/ test_state/ test_types/ test_undo/ test_validation/ test_volumes/
│   ├── graph/, node/, settings/, signals/, types/   ← sibling dirs; see ⚠️ note in Rules
├── ui/                          ← haywire-core-ui tests:
│   ├── components/ errors/ extends/ graph_canvas/ harness/ keymap/ menu/ panel/ panels/
│   ├── properties_editor/ skin/ surface/ widget/
│   └── test_canvas_handlers/ test_file_browser_menu/
├── graph_editor/                ← haybale-graph-editor tests
├── studio/                      ← haywire-studio and haybale-studio tests
├── libraries/                   ← library-system tests (loads fixtures, collisions, reload)
├── haystack/                    ← haybale-haystack tests
├── marketplace/, marketstall/   ← haybale-marketplace and engine marketstall tests
├── models/, audio/, image/      ← haybale-models, haybale-audio, haybale-image tests
├── share/, share_flow/, share_pipeline/ ← haybale-share and publish pipeline tests
├── execution/                   ← execution VM and scheduling tests
├── farmhand/                    ← Farmhand MCP tests
├── security/, auth/             ← security document, roster, login gate tests
├── rename/, update/, scripts/   ← rename CLI, update checks, scripts
└── integration/                 ← full-stack flows, marked integration
```

## 3. Always-load vs On-demand

### Always-load

- `conftest.py` (root) — DI reset and library reload helpers.
- `tests/README.md` — tiers, parallelism and traps. Read before running tests.
- A representative test for the area you change. Match its setup, especially `force_immediate_validation()` and import order.
- For settings or promotion work: `tests/core/test_settings/test_single_cell.py` and `tests/core/node/test_promotion_single_cell.py`, the canonical characterization suites for the ADR 0011–0017 model.

### On-demand

- `tests/integration/` — full-stack flows, marked `integration`.
- `tests/ui/test_canvas_handlers/` — canvas drag and connect handlers. Heavy on event simulation.
- `tests/barn/` — when changing bundled library adapters, widgets or types.

## 4. Rules & Boundaries

- Run the relevant tests after any refactor or multi-file change. The full suite is CI's job per push; run it locally only when asked.
- In test files, `import haywire.core.graph.editor` **before** any other haywire module (circular import).
- Call `force_immediate_validation()` after node setup and before asserting.
- Do not top-import barn classes. They go stale across `importlib.reload`. Use `importlib.import_module` and `patch.object` (see `.insights/feedback_barn_module_reload_test_trap.md`).
- Tests never read repo `graphs/` files; use `tests/` or `haybale-testing` fixtures.
- ⚠️ TODO: `tests/core/` holds both legacy `test_X/` dirs and newer unprefixed `X/` dirs for the same areas (for example `test_settings/` and `settings/`, `test_node/` and `node/`). Confirm the long-term convention before adding a test; check both.
- Markers are declared in `pyproject.toml` (`[tool.pytest.ini_options]`). `addopts` deselects `perf`; `--strict-markers` is on.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Test tiers, parallelism, traps | `tests/README.md` | Authority for how to run |
| Shared fixtures | `tests/conftest.py` | DI reset, reload helpers |
| Settings characterization | `tests/core/test_settings/` | Single-cell model (ADR 0013) |
| Promotion characterization | `tests/core/node/test_promotion_*.py` | ADR 0014 |
| Pytest config | `pyproject.toml` | Markers and addopts |

---

## Dependencies

### Depends on

- Every mapped module: [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md), [haywire-studio](haywire-studio.md), and all `haybale-*` libraries.
- [haybale-libs-other](haybale-libs-other.md) — the test fixture libraries (`haybale-testing`, `haybale-TEST_A`).

### Depended on by

- None. CI and local runs consume it.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Root fixtures | `tests/conftest.py` | Shared setup |
| Test guide | `tests/README.md` | Tiers and traps |
| Settings suite | `tests/core/test_settings/conftest.py` | Settings-suite fixtures |

# NiceGUI 2.22.2 → 3.12.1 Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the entire haywire monorepo (haywire-core, haywire-studio, and all 7 barn packages) from NiceGUI 2.22.2 to 3.12.1 so that all tests pass, mypy is clean, the app launches, and the graph canvas renders correctly.

**Architecture:** Work in a git worktree to keep master clean. Fix the two breaking API changes in haywire-core first (the `register_library` / `.libraries` pattern and the `background_tasks` import), then sweep the barn packages for the same patterns. Finish by bumping version constraints in all pyproject.toml files and verifying the full suite.

**Tech Stack:** Python 3.12, NiceGUI 3.12.1, uv, pytest, mypy, ruff

---

## Breaking changes discovered (reference)

| # | What changed | Old (2.x) | New (3.x) |
|---|---|---|---|
| 1 | JS library attached to element | `self.libraries.append(register_library(...))` at init | `dependencies=[path]` in class declaration; `exposed_libraries` ClassVar |
| 2 | `background_tasks` import | `from nicegui import background_tasks` | `from nicegui import background_tasks` — **still works** (module exists, just not re-exported from `__init__`; direct module import is fine) |
| 3 | `nicegui.element.Element` import path | `from nicegui.element import Element` | **unchanged** — still valid in 3.x |
| 4 | `nicegui.timer.Timer` import path | `from nicegui.timer import Timer` | **unchanged** — still valid in 3.x |
| 5 | `from nicegui import context` | existed | **unchanged** — still in `__init__` |
| 6 | `ui.run()` params | `show`, `reload`, `port`, `title` | **unchanged** |

**The only actual breaking change in this codebase is #1:** `self.libraries` (instance attribute) no longer exists — it is now `cls.exposed_libraries` (ClassVar). The fix is to move JS library registration from instance `__init__` to the class declaration via `dependencies=[...]`.

---

## Files to modify

| File | Change |
|------|--------|
| `packages/haywire-core/src/haywire/ui/components/graph/canvas.py` | Replace `self.libraries.append(register_library(...))` with `dependencies=[library_path]` in class declaration |
| All `pyproject.toml` files that declare `"nicegui"` (11 files) | Pin to `"nicegui>=3.12.1"` |
| `uv.lock` | Regenerated automatically by `uv lock` |

---

## Task 1: Spike — bump nicegui in the venv and run the test suite cold

This task establishes the actual break surface before touching any code.

**Files:** none modified

- [ ] **Step 1: Create a git worktree for the migration**

```bash
git worktree add ../haywire-nicegui3 -b feat/nicegui3-migration
cd ../haywire-nicegui3
```

- [ ] **Step 2: Bump nicegui to 3.12.1 in the worktree**

Edit `packages/haywire-core/pyproject.toml` — change the nicegui dependency line:

```toml
# Before
"nicegui",

# After
"nicegui>=3.12.1",
```

- [ ] **Step 3: Update the lockfile and install**

```bash
uv lock
uv sync
```

Expected: resolves nicegui 3.12.1 into the lock.

- [ ] **Step 4: Run mypy on haywire-core to surface type errors**

```bash
uv run mypy packages/haywire-core/src/
```

Note every new error — these are yours to fix. Pre-existing errors were zero per CLAUDE.md.

- [ ] **Step 5: Run the full test suite cold**

```bash
uv run pytest -x -q 2>&1 | head -60
```

Note every failure. Expected: failures related to `self.libraries` on `GraphCanvasVue`.

- [ ] **Step 6: Commit the lock-only change as a checkpoint**

```bash
git add uv.lock packages/haywire-core/pyproject.toml
git commit -m "chore: bump nicegui constraint to >=3.12.1 (migration spike)"
```

---

## Task 2: Fix `GraphCanvasVue` — remove runtime `self.libraries.append`

The root breaking change: `Element.libraries` (instance attribute) was replaced by `Element.exposed_libraries` (ClassVar). Libraries must now be declared at class definition time via the `dependencies=[...]` keyword in `__init_subclass__`.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.py`

**Background:** In NiceGUI 3.x, `__init_subclass__` accepts a `dependencies: list[str | Path]` keyword. Each path is registered as a `Library` and appended to `cls.exposed_libraries`. At class definition time, the path must be known — so the module-level `library_path` variable (already computed at import time) is the right thing to pass.

- [ ] **Step 1: Read the current canvas.py**

Open `packages/haywire-core/src/haywire/ui/components/graph/canvas.py` and confirm the current state matches:

```python
from nicegui.dependencies import register_library
# ...
library_path = script_dir / "generated" / "graph_events.js"
if library_path.exists():
    try:
        my_library = register_library(library_path, max_time=library_path.stat().st_mtime)
    except Exception as e:
        print(f"❌ Failed to register library: {e}")
else:
    print(f"❌ Library not found at: {library_path}")
# ...
class GraphCanvasVue(ui.element, component="canvas.vue"):
    def __init__(self, ...):
        super().__init__()
        self.libraries.append(my_library)   # <-- this line breaks in 3.x
```

- [ ] **Step 2: Apply the fix**

Replace the entire preamble and class declaration in `packages/haywire-core/src/haywire/ui/components/graph/canvas.py`.

Remove these lines entirely:
```python
from nicegui.dependencies import register_library

# Register the auto-generated library
script_dir = Path(__file__).parent
library_path = script_dir / "generated" / "graph_events.js"

if library_path.exists():
    try:
        my_library = register_library(library_path, max_time=library_path.stat().st_mtime)
    except Exception as e:
        print(f"❌ Failed to register library: {e}")
else:
    print(f"❌ Library not found at: {library_path}")
```

Change the class declaration from:
```python
class GraphCanvasVue(ui.element, component="canvas.vue"):
```

To:
```python
_GRAPH_EVENTS_JS = Path(__file__).parent / "generated" / "graph_events.js"

class GraphCanvasVue(ui.element, component="canvas.vue", dependencies=[_GRAPH_EVENTS_JS]):
```

Remove from `__init__`:
```python
        self.libraries.append(my_library)
```

The final class declaration block should look like:

```python
_GRAPH_EVENTS_JS = Path(__file__).parent / "generated" / "graph_events.js"


class GraphCanvasVue(ui.element, component="canvas.vue", dependencies=[_GRAPH_EVENTS_JS]):
    """Vue-based graph canvas component with ONLY unified event handling."""

    def __init__(
        self,
        on_canvas_event: Optional[Callable[[BaseGraphEvent], None]] = None,
        zoom_container=None,
        canvas_width: int = 8000,
        canvas_height: int = 8000,
    ):
        super().__init__()

        self._on_canvas_event = on_canvas_event
        # ... rest unchanged
```

- [ ] **Step 3: Verify mypy is clean on canvas.py**

```bash
uv run mypy packages/haywire-core/src/haywire/ui/components/graph/canvas.py
```

Expected: `Success: no issues found in 1 source file`

- [ ] **Step 4: Run the test suite**

```bash
uv run pytest -x -q
```

Expected: all tests pass (canvas.py has no unit tests; the fix is verified at runtime).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/canvas.py
git commit -m "fix: migrate GraphCanvasVue.libraries to dependencies= for NiceGUI 3.x"
```

---

## Task 3: Bump nicegui constraint in all remaining pyproject.toml files

The `uv.lock` already resolves 3.12.1 after Task 1. Now every package's declared constraint must be updated to `>=3.12.1` so published packages declare the right floor.

**Files to modify (all 10 remaining pyproject.toml files):**
- `packages/haywire-studio/pyproject.toml`
- `barn/haybale-core/pyproject.toml`
- `barn/haybale-studio/pyproject.toml`
- `barn/haybale-example/pyproject.toml`
- `barn/haybale-visiongraph/pyproject.toml`
- `barn/haybale-graph-editor/pyproject.toml`
- `barn/haybale-haystack/pyproject.toml`
- `barn/haybale-marketplace/pyproject.toml`
- `barn/haybale-testing/pyproject.toml`

(haywire-core was already done in Task 1.)

- [ ] **Step 1: Update each file**

In every file listed above, find the line:
```toml
"nicegui",
```
or
```toml
"nicegui", 
```
and replace with:
```toml
"nicegui>=3.12.1",
```

- [ ] **Step 2: Re-lock to confirm no conflicts**

```bash
uv lock
```

Expected: lock resolves cleanly, nicegui stays at 3.12.1.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Run mypy on the full scope**

```bash
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-visiongraph/haybale_visiongraph/
```

Expected: no new errors introduced by this migration.

- [ ] **Step 5: Commit**

```bash
git add barn/*/pyproject.toml packages/haywire-studio/pyproject.toml uv.lock
git commit -m "chore: pin nicegui>=3.12.1 across all packages"
```

---

## Task 4: Lint, format, and full quality gate

- [ ] **Step 1: Run ruff lint**

```bash
uv run ruff check .
```

Expected: zero errors. If any appear, fix them before continuing.

- [ ] **Step 2: Run ruff format check**

```bash
uv run ruff format --check .
```

If format differences are found, apply them:
```bash
uv run ruff format .
git add -u
git commit -m "style: ruff format after nicegui3 migration"
```

- [ ] **Step 3: Run the full test suite one final time**

```bash
uv run pytest -q
```

Expected: all tests pass, zero failures, zero errors.

- [ ] **Step 4: Commit if any fixes were needed**

If steps 1-3 produced no changes, skip. Otherwise:
```bash
git add -u
git commit -m "fix: lint/format cleanup after nicegui3 migration"
```

---

## Task 5: Manual smoke test — launch app and verify graph canvas

This task cannot be automated. The graph canvas uses a custom Vue component + JS library loaded via NiceGUI's dependency system; no test exercises it.

- [ ] **Step 1: Launch the app**

```bash
uv run haywire
```

Expected: app starts, browser opens on `http://localhost:8082`, no Python tracebacks in the terminal.

- [ ] **Step 2: Verify the graph canvas renders**

In the browser:
1. Open or create a graph document.
2. Confirm the canvas area is visible (not blank/empty).
3. Add a node — confirm it appears on the canvas.
4. Connect two nodes — confirm the connection line renders.
5. Pan and zoom — confirm the canvas responds.

If anything is blank or throws a JS console error, check the browser devtools console for errors related to `graph_events.js` or `canvas.vue`. The most likely cause would be the `dependencies=` path not resolving to the `.js` file.

- [ ] **Step 3: Stop the app and confirm clean shutdown**

Press `Ctrl+C` in the terminal. Expected: clean shutdown, no tracebacks.

---

## Task 6: Merge to master

- [ ] **Step 1: Final pre-merge check**

```bash
uv run pytest -q && uv run ruff check . && uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-visiongraph/haybale_visiongraph/
```

All three must exit 0.

- [ ] **Step 2: Switch back to master and merge**

```bash
cd /path/to/haywire-repo   # the original worktree
git merge feat/nicegui3-migration --no-ff -m "feat: migrate to NiceGUI 3.12.1"
```

- [ ] **Step 3: Remove the worktree**

```bash
git worktree remove ../haywire-nicegui3
git branch -d feat/nicegui3-migration
```

---

## Self-review checklist

**Spec coverage:**
- ✅ Full migration (all packages) — Tasks 1, 3
- ✅ `register_library` / `.libraries` breaking change — Task 2
- ✅ `class Foo(ui.element, component=...)` pattern — Task 2 (`dependencies=[...]` is the fix; the `component=` keyword is unchanged and still works)
- ✅ `nicegui.element.Element` import — not broken in 3.x, no change needed
- ✅ `nicegui.timer.Timer` import — not broken in 3.x, no change needed
- ✅ `background_tasks` import — not broken in 3.x, no change needed
- ✅ `ui.run()` params — not broken in 3.x, no change needed
- ✅ Tests green — Tasks 1, 2, 3, 4
- ✅ mypy clean — Tasks 2, 3, 4
- ✅ App launches + canvas manually verified — Task 5
- ✅ Merge — Task 6

**Placeholder scan:** No TBDs, no "implement later", all code blocks are complete.

**Type consistency:** No new types introduced; the only API change is `dependencies=[_GRAPH_EVENTS_JS]` in the class declaration keyword, which takes `list[str | Path]` — `Path` matches.

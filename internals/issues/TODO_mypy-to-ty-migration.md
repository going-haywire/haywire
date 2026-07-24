# Retire mypy in favour of ty

**Goal:** make `ty` (Astral's type checker) the sole type-check gate and remove mypy.

**Why not yet:** `ty` is pre-1.0 (pinned `ty==0.0.63`) and not officially released. It runs
in CI as a **non-blocking** second opinion (`ty.yml`, `continue-on-error: true`) while mypy
stays the gate. Don't flip the gate until `ty` reaches 1.0 / feature parity.

**Suppression rule:** add `# ty: ignore` *only* where the code is correct and ty is wrong
(stub gaps, narrowing ty can't follow). Where ty points at a genuinely loose type, fix the
type. Never suppress a real defect or to lower a count. **We do not add `# ty: ignore` lines
while ty is pre-1.0** — a diagnostic whose only remedy is a suppression is left flagged and
recorded below as a re-check, so we re-evaluate it against a newer ty rather than silence it.

---

## Step 1 — drive `ty check` to zero

Run: `uv run ty check packages/ barn/`. A 2026-07-24 pass (ty 0.0.44, then bumped to 0.0.63)
took the count **28 → 9** by fixing every diagnostic that had an honest fix — **no `# ty: ignore`
added**. mypy stays clean throughout (410 files). Two of the fixes were latent bugs ty surfaced:

- `IProjectState` was missing `skin_factory` (protocol gap; the app defined it) — added it.
- `introspect/graph.py` called `graph.list_edge_wrappers` without `()` — edge count was always
  `"?"`. Fixed.

The rest were real type improvements: honest `Optional`/narrowing on `graph_editor._project_state`;
`type[BasePanel]` throughout `selection_toolbar`; narrowed-closure locals in `node_menu_builder`;
`getattr(handler, "__name__", …)` in `graph_canvas_manager`; `type[IType]` bounds in
`settings/registry` (surfaced a loose caller in `di/test_config`); deleting a dead
`self.container = None` in `ui_node` so its type is honestly non-Optional; an `AppState`-bound
TypeVar + explicit None-assert on `FarmhandContext.state()` (replacing a `cast` that hid both an
unbounded type and a swallowed `None`); and a **`FlyoutMenu(ui.menu)` typed subclass** in
`ui/elements/flyout.py` that retired the `_child_flyouts` monkey-patch, tightened
`FlyoutSiblings → List[FlyoutMenu]` (which caught a stale `List[ui.menu]` in `node_menu_builder`),
and modernized the `@contextmanager` return type (`Iterator → Generator`).

### Re-check list — the remaining 9 (no honest fix under current ty; re-evaluate on upgrade)

Each is either a ty pre-1.0 gap (code is correct, mypy agrees) or a deliberate framework-boundary
pattern already `# type: ignore`'d for mypy. **Do not `# ty: ignore` these while ty is pre-1.0** —
re-run against a newer ty first; a version bump has already cleared items (0.0.63 dropped the two
`farmhand/host.py` str→AnyUrl diagnostics 0.0.44 flagged). Fix honestly whatever survives; several
were checked to have *no* honest fix (an explicit annotation was rejected too — see `rename.py`).

- `ui/widget/factory.py:134` (+ `ui/widget/interface.py`) — `widget_cls(port)`; ty won't match
  `DataPort` to the `WidgetModel` Protocol though mypy does and the docstring documents the intent.
- `core/graph/base.py:139` ×2 — `GraphProperties(registry=…, graph=…)`; ty can't resolve the
  `__init__` inherited through the settings-descriptor metaclass. Params genuinely exist.
- `ui/app/shell.py:44` — `pygments.formatters.HtmlFormatter` stub gap (imports fine at runtime).
- `barn/haybale-marketplace/.../library_manager.py:203` — `importlib.metadata.FastPath` — a
  deliberate CPython-internal cache-clear workaround, `try/except AttributeError`-guarded.
- `ui/utils.py:31` — `_handle_delete` method-assign (already `# type: ignore[method-assign]`).
- `barn/haybale-studio/.../farmhands/errors.py:82` — `ledger.delete(seq)` seq narrowing
  (already `# type: ignore[arg-type]` with reason).
- `barn/builtin/types/vectors.py:32` — `_value` on `Self` (already `# type: ignore[attr-defined]`).
- `haywire_studio/rename.py:282` — subscript-assign on a `dict` narrowed from `object`; ty rejects
  it *and* an explicit `dict[str, Any]` annotation (invariance + `Unknown`). mypy narrows natively.

**Done when:** `uv run ty check packages/ barn/` reports 0 diagnostics — every entry above either
cleared by a ty upgrade or fixed honestly (never suppressed while pre-1.0).

## Step 2 — flip the gate

In `.github/workflows/ty.yml`: set `continue-on-error: false`.

## Step 3 — remove mypy (only after Steps 1–2 hold)

Delete every mypy touch-point:

1. `pyproject.toml` — `[tool.mypy]` block (also `python_version`, `mypy_path`, overrides)
2. `packages/haywire-studio/pyproject.toml` — `[tool.mypy]` block
3. `.github/workflows/mypy.yml` — delete the workflow
4. `.github/workflows/tests.yml` — the "Run mypy" step (currently `uv run mypy src/`, a stale
   path — verify/remove, don't preserve)
5. `README.md` — the mypy badge (line ~6) and the `uv run mypy .` command (line ~284, also stale)
6. `CLAUDE.md` — the two `uv run mypy …` commands (baseline snippet + the full type-check command)
7. `.claude/skills/verify/SKILL.md` — the mypy invocation in the quality suite

Replace each removed mypy invocation with its `ty` equivalent, or drop it if `ty.yml` covers it.

**Done when:** no `mypy` reference remains (`grep -rn mypy` clean outside this doc) and `ty` is the gate.

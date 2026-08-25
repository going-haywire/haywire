# Node theme cascade — implementation plan

Replaces the four per-node appearance props (`6d4c3ee0`) with a CSS-variable
cascade. Settled by inquisition on 2026-08-25; thirteen decisions, recorded in
ADR-0030 (written in Stage 6).

**The one sentence:** node styling travels as a CSS-var cascade, and nothing
reads a theme in Python.

```
:root            WorkbenchTheme                 (all tokens)
:root            global NodeTheme               (Tier 1, clear-then-set)
.graph-canvas    graph's node_theme             (only if ≠ global)
.ui-node-slot    node's node_theme              (only if ≠ graph)
.ui-node-slot    color_override                 (--hw-node-bg, composed last)
```

A skin emits `background: var(--hw-node-bg)` once and never branches. The
browser re-resolves every `var()` when a slot's declarations change — that is
what removes `card_style()` rather than reimplementing it.

## Baseline

Established clean on the working tree at `6042b719` + uncommitted work:

```sh
uv run ruff check .                       # All checks passed!
uv run mypy <the CLAUDE.md file list>     # Success: no issues found in 1186 source files
```

One pre-existing `ruff format` drift in
`packages/haywire-core/src/haywire/core/debug/debug_settings.py`, unrelated and
deliberately left alone. Anything new after an edit belongs to that edit.

## Do not touch

Three things in the working tree are unrelated to node colouring and must
survive untouched:

- `core/di/config.py` — the `workspace_settings_path` split. Tests were writing
  into the developer's real `<repo>/.haywire/settings.json`. Documented in
  `.insights/project_tests_wrote_workspace_settings.md`.
- `core/settings/persistence.py` — the `_flatten` namespace-vs-entry fix.
  `ui.node.default.skin.studio_skin` was truncated at `ui.node`, silently
  dropping a subtree.
- `graphs/oakNwebCam.haywire` — an unrelated stale promoted-key removal.

## Scope

Core props, the theme base classes, two barn libraries, a Vue-adjacent style
path, plus docs/ADR/insights. Smaller than the surface-model change, but it
deletes more than it adds: `card_style()` (68 lines), `test_card_style.py`
(221), the rename migration, three props, `get_color()`, and seven inert theme
fields.

Easy to miss:

- `packages/haywire-core/src/haywire/barn/builtin/skins/reroute_skin.py:53` —
  `background-color: var(--hw-node-bg)` silently drops a gradient-valued token.
  Must become `background:`. This is the whole reason a theme can carry a
  gradient at all.
- `packages/haywire-core/src/haywire/_baked_docs/` — generated. Edit `docs/`,
  then re-bake via `scripts/bake_docs.py`. Never hand-edit.
- `.insights/project_docs_test_reverts_barn_testing.md` — `tests/studio/test_docs/`
  teardown runs `git checkout -- barn/haybale-testing`. This change edits
  `haybale-testing/themes/node.py`. **Commit before running the full suite.**
- `_apply_size()` writes with `style(replace=…)`, deliberately authoritative. A
  second writer using `add=` would be wiped on the next size change — hence one
  merged `_apply_slot_style()`.

## Order

Stages 1–2 are independent of 3–4 and can land separately. Stage 5 depends on
everything before it.

### Stage 1 — Token map and theme base

1. Hoist `_CSS_TOKEN_MAP` and `to_css_vars()` from `WorkbenchTheme` to
   `BaseTheme` (`ui/themes/workbench.py`). `NodeTheme` inherits both — one map,
   so a node theme cannot name a token the workbench does not have.
2. Rename in the map's `# Node chrome` block:
   - `node_border` → `node_border_color` (`--hw-node-border-color`)
   - `node_header_text` → `node_header_text_color`
3. Add: `node_border_width`, `node_border_radius`, `node_text_color`.
4. Delete `NodeTheme.get_color()` (`ui/themes/node_theme.py`). `to_css_vars()`
   is the only way to read a theme.

**Tier 1** (card surface, per-node overridable): `node_bg`,
`node_border_color`, `node_border_width`, `node_border_radius`,
`node_header_bg`, `node_header_text_color`, `node_text_color`.

**Tier 2** (canvas chrome): `node_selected`, `node_active`, `node_shadow` —
consumed on `[data-node-id]` by `canvas.vue`. Reachable from `:root` and
`.graph-canvas`, **not** from `.ui-node-slot`. A node-tier theme silently
cannot restyle the selection ring; a graph-tier one can. Document the
asymmetry.

Lengths carry their unit in the value (`"3px"`), because `var()` is textual
substitution — `border: 3 solid red` is invalid and fails silently.
Precedent: `muted_opacity`, `compact_field_h`.

### Stage 2 — Theme values and skins

1. `barn/haybale-studio/haybale_studio/themes/workbench.py` — both themes gain
   the four new tokens, **seeded from today's hardcoded literals** so nothing
   changes visually on upgrade:
   `node_border_color = "#333333"`, `node_border_width = "3px"`,
   `node_border_radius = "16px"`. The stale `#2e2e48` is discarded; it has never
   painted anything.
2. Same for `barn/haybale-testing/haybale_testing/themes/workbench.py`.
3. `themes/node.py` in both libraries — delete the seven inert fields
   (`port_inlet`, `port_outlet`, `port_exec_inlet`, `port_exec_outlet`,
   `error_bg`, `error_border`, `muted_opacity`); rename the rest onto Tier-1
   names. These were never in `_CSS_TOKEN_MAP`, so "remove from CSS" is a no-op:
   they never reached CSS.
4. `default_skin.py` — drop the `card_style()` call; emit
   `background: var(--hw-node-bg); border: var(--hw-node-border-width) solid
   var(--hw-node-border-color); border-radius: var(--hw-node-border-radius);`
5. `example_skin.py` — its gradient moves from the injected `<style>` rule to
   `--hw-node-bg` on its own card, so it stays overridable. A rule setting
   `background:` directly beats the cascade entirely.
6. `reroute_skin.py:53` — `background-color` → `background`.
7. Delete `BaseSkin.card_style()` (`ui/skin/base.py`).

### Stage 3 — Props

1. `core/node/properties.py`:
   - Delete `body_fill`, `border_color`, `border_thickness`, `border_roundness`.
   - Delete `to_dict`, `from_dict`, `_RENAMED_FIELDS`, `_migrate_value` — with
     `color_override` restored under its original name, nothing was ever
     renamed, so no migration exists to run.
   - Restore `color_override = setting[COLOR](None, …)`, exactly pre-`6d4c3ee0`.
     A `None` default means "unset = inherit" falls out of emptiness, with no
     `is_locally_set` probing.
   - Add `node_theme = graph(src=GraphProperties.node_theme, …)`.
   - `REDRAW_FIELDS`: `color_override` and `node_theme` are **absent** — both
     ride the style-write path, not the redraw path.
2. `core/graph/properties.py` — `node_theme = shadow(src=NodeThemeSettings…)`,
   mirroring how `default_skin` and `layout_direction` already do it.
3. `NodeThemeSettings.theme` — `STRING` → registry-resolved `CHOICES`, matching
   `WorkbenchThemeSettings`.

### Stage 4 — The write points

1. `ui/app/shell.py` — global node theme, **clear-then-set**: `removeProperty`
   every Tier-1 var, then set the active theme's. Without the clear, switching
   to a partial theme leaves stale values from the previous one. Both paths —
   `_build_initial_theme_css()` and the live `setProperty` — must agree.
2. `graph_canvas` — graph-tier vars on `.graph-canvas`, **only when the graph's
   resolved `node_theme` differs from global**. Follow the shell's precedent for
   writing into a Vue-owned element.
3. `ui_node.py` — rename `_apply_size()` → `_apply_slot_style()`, composing in
   one `replace=` string:
   - size declarations (unchanged)
   - node's theme vars, **only if ≠ the graph's**
   - `color_override` as `--hw-node-bg`, **composed last so it wins**
   Extend `_subscribe_size_fields()` to `color_override` and `node_theme`.

Divergence is decided by **value comparison against the parent tier**, not
`is_locally_set`. Identical values produce identical CSS, so writing them is
waste however they arose; and a wrong comparison yields a redundant write, never
a wrong colour.

Why this matters at scale: a naive design has every node writing a full var set
on every render — 200 identical declaration strings on a 200-node graph, all
shadowing a `:root` value that was already correct. See
`.insights/project_large_graph_perf.md`.

### Stage 5 — FILL moves to haybale-example

`FILL` and `FillWidget` have no production consumer under this design. They move
to the example library rather than shipping as registered-but-inert core
components — the exact pattern this whole change exists to remove.

1. Move `types/fill.py` → `barn/haybale-example/haybale_example/types/fill.py`;
   `widgets/fill_widget.py` → the example library's `widgets/`. Folder-scan
   registration means no registration code to write.
2. Drop the core `widget_keys.FILL_WIDGET` entry and the two `__init__.py`
   exports. The widget's key becomes `haybale-example:widget:FillWidget`;
   the type references it directly, same library.
3. **Trim the props-era accommodations**: the `value=` branch in `FILL.__init__`
   (which exists only because `Settings._cell_for` seeds cells as
   `{"value": seed}`) and `from_css_color()` (documented as the migration path
   from `body_color`). Both are dead with no `FILL` settings field.
4. Add a demo node with a `FILL` config port, so the type is exercised in a real
   card rather than only in unit tests. `BaseType.to_dict`/`from_dict` handles
   the port round-trip — no new machinery.
5. Move `tests/core/types/test_fill.py` → `tests/barn/`, minus the tests
   covering removed paths.

### Stage 6 — Docs

1. `docs/components/themes/theme-canon.md` — the `NodeTheme` token table, the
   `get_color()` contract line, and line 20's claim that node theme values are
   "read by the canvas-side node renderer" (false today, **true** after this
   change). Add the tier model and the per-tier reach asymmetry.
2. `docs/components/nodes/node-canon.md:112` — `REDRAW_FIELDS` back to
   `color_override`, plus a note that it is *not* in that set because it rides
   the style-write path.
3. ADR-0030 — records why node styling is a CSS cascade and not Python-read
   theme values; why `NodeTheme` shares the workbench token map; why
   `get_color()` is gone; and the context that most needs recording: `NodeTheme`
   was registered, selectable, and documented as live while being entirely
   inert.
4. `.insights/` — one file for the three silent-failure modes:
   `background-color` drops a gradient var; a field absent from
   `_CSS_TOKEN_MAP` is silently dropped by `to_css_vars()`; `.ui-node-slot` vars
   cannot reach `[data-node-id]`.
5. Re-bake: `uv run python scripts/bake_docs.py`.

## Tests

- Delete `tests/ui/skin/test_card_style.py` with `card_style()`.
- Rewrite `tests/ui/harness/test_appearance_props.py` for one colour prop.
- `tests/ui/test_node_theme.py` — delete the `get_color` and inert-token tests;
  rewrite the rest onto `to_css_vars()`.
- `tests/ui/test_theme_registry.py:112` — `header_bg` → a Tier-1 name.
- New: three-tier resolution (global → graph → node), the divergence-comparison
  rule, and clear-then-set on a partial theme.
- Keep `is_visual_only()` and its haystack guard (`6042b719`) with their 114
  lines of tests. Eight producers raise those reasons and none are
  colour-specific: a pure repaint marking the graph unsaved is a real defect
  independent of what surfaced it.

Gate: `uv run pytest -m "not browser and not perf"`, then the full suite.

## Deliberately not doing

Per-node border/thickness/radius props; port and error colours as CSS vars; a JS
bridge so `.ui-node-slot` can reach `[data-node-id]`; `FILL` in
`NodeProperties`.

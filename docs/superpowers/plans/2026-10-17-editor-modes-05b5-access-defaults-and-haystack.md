# Editor modes, slice 5b-5: access defaults and the haystack — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Editors and panels default to `access=edit`, so a component that forgets to declare fails closed. The read-only editors declare `view` explicitly, and every haystack action needs the tier its effect calls for: `view` selects, `operate` also starts and stops, `edit` does the rest.

**Architecture:**
- **Defaults:** `EditorIdentity.access` and `PanelIdentity.access`, and the two decorators' fallbacks, become `AccessTier.EDIT`. The existing gates (`Slot._editor_accessible`, `panel_accessible` in `host_rendering.py`) already read `required_access`, so nothing else changes in the gating machinery.
- **Review once:** each shipped editor and panel is classified in one test, as `tests/farmhand/test_tool_tiers.py` does for tools. Unclassified or misdeclared components fail it.
- **Haystack:** each handler in `HaystackEditor` checks the principal's real tier and refuses with a notification. The control is hidden below that tier.

**Tech Stack:** Python 3.12, NiceGUI, pytest (`uv run pytest`), ruff, mypy.

**Spec:** [2026-10-16-edit-route.md](2026-10-16-edit-route.md): section "Access defaults and the haystack editor"; sequence item 5 ("5b-5, access defaults and the haystack"); decisions Q11, Q12, Q18; the 5b-5 items under "Docs corrections" and "Glossary (changed)". Decisions are listed below.

## Global Constraints

- **Branch:** work on `feat/editor-modes-slice5b5` in worktree `.worktrees/editor-modes-slice5b5`, cut from `feat/editor-modes-slice1` (HEAD `20b7d4ce`). It merges into `feat/editor-modes-slice1` after the live check; nothing goes to master. The main checkout has the user's uncommitted edits (`.claude/settings.json`, `docs/components/nodes/node-canon.md`); never touch them.
- **Default** (spec): "Editors and panels default to `access=edit`, instead of `view`. An editor that forgets to declare fails closed. Read-only editors declare `view` explicitly."
- **Haystack tiers** (spec Q12): `view`: select an entry to look at. `operate`: also Start and Stop execution. `edit`: everything else (New Graph, Load Graph, entry Rename and Remove, the haystack's Load, Rename and Save, and the run settings). Save and Save-as already need it. "Each handler checks the real tier, and the control is hidden below it."
- **Real tier, not level mode:** haystack actions use `SessionContext.can_access(...)`, never a level's route.
- **Not in this slice:** the `developer` tier; per-graph permissions; `required_access`'s VIEW fallbacks for a missing identity or an invalid tier (the decorators already reject a bad tier at definition time); Ctrl+S; the undo-history panel; the deferred 5b-4 minors.
- **Docs rules:** follow `.claude/rules/python-docs.md`. ADR, glossary, canon and guide edits land in Task 3, with the code.
- **Pre-edit baseline** (CLAUDE.md), before Task 1: `uv run ruff check packages/haywire-core/src barn tests/core tests/studio tests/haystack tests/farmhand` and the CLAUDE.md mypy command. It must be clean; if not, stop and ask.
- **Tests:** smallest tier while iterating. Commit before any full-suite run (`tests/studio/test_docs/test_generate.py` reverts uncommitted edits under `barn/haybale-testing`). Use `-n 4`.
- **Commit trailer:** end every commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Decisions (this plan's, against the spec)

1. **Editors that declare `view`:** `GraphEditor`, `HaystackEditor`, `ComponentDocsEditor`, `ErrorsEditor`, `FileViewerEditor`, `LazyFileBrowserEditor`, `LogEditor`, `ShortcutsEditor` (and `ActivityEditor`, already `view`). The graph and haystack editors gate their own actions (level mode, Decision 4), so a `view` principal can open them.
2. **Editors left at the `edit` default:** `PropertiesEditor` (every tab writes app or workspace settings, or polls `can_edit_graph`, so below `edit` it would be empty), `CodeEditor`, `ComponentSourceEditor`, `LibraryBrowserEditor` and `LibraryOverviewEditor` (refresh, sources, install), and `ShareEditor`. `RosterEditor` stays `admin`.
3. **Panels:** every panel is left at the `edit` default except the ones a principal below `edit` reaches: the four account-menu panels already declared (`DeveloperModePanel`, `LogoutPanel`, `OpenActivityPanel` at `view`; `OpenRosterPanel`, `RotateSecretPanel` at `admin`) and `OpenInFileViewerMenuPanel` (file browser menu), which declares `view`. The graph editor's menus and toolbars open only in level mode `edit`, and the Properties panels live in an `edit` editor, so the default changes nothing for them. `GraphRunSettingsPanel` (the run settings) takes the default, which is the spec's `edit`.
4. **Haystack controls below their tier are not drawn**, Save included (it draws disabled today; the spec says hidden). Below `edit`: the header's Save icon and its overflow menu (Save As…, Load…, Rename…), the add bar (New Graph, Load Graph…), and each entry's Save icon and overflow menu (Save, Save as…, Rename…, Remove / Release from memory) are not drawn. The unsaved dot stays. Below `operate`: the Start/Stop control is not drawn; the row's execution border still shows a running graph. A macro entry keeps its kind icon at every tier.
5. **Each handler refuses with a notification**, like Save does: `"<Action> needs edit access"` / `"Starting and stopping needs operate access"`, `type="warning"`, `position="top-right"`. Handlers: `_on_entry_rename`, `_on_entry_delete`, `_on_new`, `_on_open_graph`, `_on_load_haystack`, `_on_rename_haystack` need `edit`; `_on_start_execution`, `_on_stop_execution` need `operate`; `_on_select` needs nothing beyond `view`.
6. **Farmhand `start_graph` and `stop_graph` drop to `operate`,** matching Q12, so an agent at `operate` can run a graph as a person can. `create_graph`, `open_graph`, `save_graph`, `rename_graph`, `close_graph` stay `edit`.
7. **`ErrorsEditor` triage and `LogEditor`'s Clear stay open at `view`.** They change shared UI state (the error ledger's seen flags, the log buffer), not a document; the spec lists both editors as read-only candidates.

## Review Focus

1. **A `view` principal whose workspace layout has the Properties editor open.** The tab is not drawn and the layout loads without error; an `edit` principal on the same workspace still gets it. Test: Task 1, `test_a_view_principal_is_not_shown_an_edit_editor`.
2. **An `operate` principal on a haystack entry that is running.** The Stop control is drawn and works; the entry's overflow menu is not drawn. Test: Task 2, `test_operate_draws_start_stop_and_no_entry_menu`.
3. **A stale control clicked after a demotion** (rendered at `edit`, tier now `view`). The handler refuses and nothing changes. Test: Task 2, `test_each_edit_handler_refuses_below_edit`.
4. **A new editor or panel added later without `access=`.** It is hidden from a `view` principal, and the classification test names it. Test: Task 1, `test_every_editor_and_panel_is_classified`.
5. **A `view` principal opening the file browser.** It lists files and offers "Open in File Viewer" only. Test: Task 1, `test_the_file_menu_offers_only_the_viewer_below_edit`.

---

### Task 1: The `edit` default and one classification of every editor and panel

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/identity.py:81-91` (docstring + default), `packages/haywire-core/src/haywire/ui/editor/decorator.py:48,95`, `packages/haywire-core/src/haywire/ui/panel/identity.py:60-71`, `packages/haywire-core/src/haywire/ui/panel/decorator.py:78,119`
- Modify (add `access=AccessTier.VIEW`): the `@editor(...)` of the eight editors in Decision 1 (`barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py`, `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py`, `barn/haybale-studio/haybale_studio/editors/{component_docs_editor,errors_editor,file_viewer,file_browser,log_editor,shortcuts_editor}.py`) and `OpenInFileViewerMenuPanel` (grep `class OpenInFileViewerMenuPanel` under `barn/haybale-studio`)
- Test: `tests/core/test_access/test_identity_access.py` (`test_panel_identity_defaults_to_view` :28, `test_editor_identity_defaults_to_view` :33), new `tests/studio/test_component_access_classification.py`

**Interfaces:**
- Produces: `EditorIdentity.access` and `PanelIdentity.access` default `AccessTier.EDIT`; `@editor()`/`@panel()` without `access=` give `EDIT`. `required_access` is unchanged.

- [ ] **Step 1: Write the failing tests**
  - `test_identity_access.py`: rename the two default tests to `test_panel_identity_defaults_to_edit` / `test_editor_identity_defaults_to_edit` and assert `AccessTier.EDIT`; add `test_editor_decorator_without_access_gives_edit` (a test-local `@editor(...)` class without `access=` → `class_identity.access is AccessTier.EDIT`).
  - `test_component_access_classification.py` (integration, `library_system`; registries from `library_system.injector.get(EditorTypeRegistry)` / `get(PanelRegistry)`, iterating every registered class):
    - module tables `VIEW_EDITORS` (Decision 1, nine names incl. `ActivityEditor`), `ADMIN_EDITORS = {"RosterEditor"}`, `VIEW_PANELS = {"DeveloperModePanel", "LogoutPanel", "OpenActivityPanel", "OpenInFileViewerMenuPanel"}`, `ADMIN_PANELS = {"OpenRosterPanel", "RotateSecretPanel", "SecurityPanel", "CloneToLibraryMenuPanel", "NewNodeToolbarPanel"}`; every other editor and panel is `EDIT`.
    - `test_every_editor_and_panel_is_classified`: for each registered class, `required_access(cls)` equals the table's tier (by class name); the failure message lists every mismatch.
    - `test_the_tables_name_only_registered_components`: each name in the tables is registered (catches a rename).
  - `test_a_view_principal_is_not_shown_an_edit_editor` (unit, in the same file): with `set_access_resolver(lambda _n: AccessTier.VIEW)` (restore in a fixture, as `tests/studio/test_haystack_editor_save_gate.py` does), `Slot._editor_accessible(PropertiesEditor)` is `False` and `(GraphEditor)` is `True`; at `EDIT` both `True`. Build the `Slot` the way the existing slot tests do (grep `_editor_accessible` under `tests/`); if none exist, call `SessionContext.can_access(required_access(cls))`, the exact expression the slot evaluates.
  - `test_the_file_menu_offers_only_the_viewer_below_edit`: `required_access` of the three `FileMenu` panels is `VIEW` for `OpenInFileViewerMenuPanel` and `EDIT` for `OpenInCodeEditorMenuPanel` and `OpenInHaystackMenuPanel`.
- [ ] **Step 2: Run** both files — FAIL (defaults still `VIEW`; the classification lists every undeclared component).
- [ ] **Step 3: Implement** the defaults (docstrings: "Defaults to 'edit', so a component that does not declare is hidden below edit") and the nine explicit declarations. Fix any test that relied on the old default (`grep -rn "defaults_to_view\|access is AccessTier.VIEW" tests/`; `tests/graph_editor/test_stage_parity.py`, `tests/graph_editor/test_graph_editor_views.py`, `tests/ui/test_activity_editor.py`).
- [ ] **Step 4: Run** `uv run pytest tests/core/test_access tests/studio tests/graph_editor tests/ui -m "not browser" -n 4` — PASS.
- [ ] **Step 5: Commit** `feat(access): editors and panels default to edit; read-only editors declare view`

---

### Task 2: Haystack actions by tier

**Files:**
- Modify: `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py` (`_render_header` :148, `_render_add_bar` :184, `_render_list` :202 (add bar call), `_render_entry` :234, and the handlers in Decision 5)
- Modify: `barn/haybale-haystack/haybale_haystack/farmhands/graph_tools.py` (`start_graph` :234, `stop_graph` :256: `access=AccessTier.OPERATE`)
- Test: `tests/studio/test_haystack_editor_save_gate.py` → `git mv` to `tests/studio/test_haystack_editor_tiers.py` (keep its tests; replace `test_haystack_save_controls_draw_disabled_below_edit`), `tests/farmhand/test_tool_tiers.py` (move both names from `EDIT_TOOLS` to `OPERATE_TOOLS`)

**Interfaces:**
- Consumes: nothing from Task 1 beyond `HaystackEditor` declaring `view`.
- Produces: no new public names.

- [ ] **Step 1: Write the failing tests** in `test_haystack_editor_tiers.py`, reusing `_setup` / `_haystack_header_setup` and rendering through a headless `Client` as the existing draw test does:
  - `test_each_edit_handler_refuses_below_edit` (parametrized `VIEW`, `OPERATE`): calling `_on_entry_rename`, `_on_entry_delete`, `_on_new`, `_on_open_graph`, `_on_load_haystack`, `_on_rename_haystack` changes nothing on the mocked haystack (`create_new`, `remove_entry`, `rename_graph`, `load_haystack`, `rename_haystack` not called; no dialog or modal opened) and calls `ui.notify` once each.
  - `test_start_and_stop_refused_in_view`: at `VIEW`, `_on_start_execution` and `_on_stop_execution` call neither `entry.start_execution` nor `entry.stop_execution`; at `OPERATE` both are called.
  - `test_haystack_controls_are_hidden_below_edit` (replaces the draw-disabled test; parametrized `(VIEW, False)`, `(OPERATE, False)`, `(EDIT, True)`): header drawn → the `save` icon button and the `more_vert` button exist iff edit; list drawn with one unsaved, not executing entry → the add bar's `add` button, the entry's `save` icon and its `more_vert` button exist iff edit; the unsaved dot (`bg-amber-400`) exists at every tier.
  - `test_operate_draws_start_stop_and_no_entry_menu`: at `OPERATE` with an executing entry, the Stop icon action (`hui.icon.execution_stop`) exists and the entry's `more_vert` does not; at `VIEW` no Start/Stop icon action exists.
  - `test_tool_tiers.py`: the existing classification asserts the new buckets.
- [ ] **Step 2: Run** `uv run pytest tests/studio/test_haystack_editor_tiers.py tests/farmhand/test_tool_tiers.py` — FAIL.
- [ ] **Step 3: Implement** Decisions 4–6. Read the tier once per draw (`can_edit = context.can_edit()`, `can_operate = context.can_access(AccessTier.OPERATE)`); the handler checks read it again at click time.
- [ ] **Step 4: Run** `uv run pytest tests/studio tests/haystack tests/farmhand -n 4` — PASS.
- [ ] **Step 5: Commit** `feat(haystack): each action needs its tier; controls below it are not drawn`

---

### Task 3: Docs, glossary, ADRs, full gates

**Files:**
- Modify: `docs/components/panels/panel-canon.md:129` (`access` default `AccessTier.EDIT`, with the read-only rule: "declare `view` for a panel a principal below `edit` must reach")
- Modify: `docs/components/editors/editor-canon.md` (identity table near :52: an `access` row, default `edit`, same rule; checklist line near :280)
- Modify: `docs/reference/glossary.md` (:374 **Access-Gated Surface**: the default is `edit`; :376 **Operate (tier)**: add "Start and Stop in the haystack")
- Modify: `docs/guides/security.md` (:486 `view`: "can open the graph, haystack, docs, errors, log, shortcuts, activity and file editors, pan and zoom on the document level and select a haystack entry" — no Properties editor; :487 `operate`: adds Start and Stop; :494-499 delete the known-gaps box, keeping its last sentence ("These are UI roles against accidents…") as a plain paragraph; the "apart from the known gaps" sentence near :539 per the spec)
- Modify: `docs/adr/0051-operate-tier-and-the-canvas-lock.md` (:20 `view`'s description drops "reads the Properties editor's Execution tab"; Consequences :41 drops the haystack known-gaps bullet and says the haystack follows Q12)
- Modify: `docs/adr/0027-studio-authentication.md` (the access default, where it states `view` as the identity default; grep `default` in that file)
- Modify: `docs/superpowers/plans/2026-10-16-edit-route.md` (sequence item 5: mark built, one line per Decision 2, 4, 6, 7)

- [ ] **Step 1: Edit** the docs above, present tense, no history.
- [ ] **Step 2: Run** `uv run mkdocs build --strict` — PASS.
- [ ] **Step 3: Commit** `docs: editors and panels default to edit; haystack tiers; security guide loses its known gaps`
- [ ] **Step 4: Full gates.** `uv run ruff check packages barn tests`, `uv run ruff format --check packages barn tests`, the CLAUDE.md mypy command, `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`, `uv run pytest -m browser -n 4`. All green.
- [ ] **Step 5: Hand off for the live check** (studio started from the worktree; principals made with `haywire user add <name> --tier view|operate|edit`):
  1. `view`: the graph, haystack, docs, errors, log, shortcuts, activity and file editors appear; Properties, code, component source, library browser, library overview and share do not. The haystack shows entries without Save, menus, the + bar or Start/Stop; selecting an entry opens it.
  2. `operate`: as `view`, plus Start/Stop on each graph entry; starting and stopping works.
  3. `edit`: everything as before, Save icons and menus included.
  4. File browser at `view`: the file menu offers only Open in File Viewer.
  5. Farmhand at `operate`: `haystack_start_graph` and `haystack_stop_graph` work; `haystack_open_graph` is refused.

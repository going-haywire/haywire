# Editor modes 6a: the default skins move to the graph editor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the default-skin family (NodeSkin, Stacked, Split, Error), `NodeSkinSettings` and `NodeSkinSettingsPanel` from haybale-studio to haybale-graph-editor, with no change in behaviour.

**Architecture:** A pure file move between two barn libraries. The registry finds the default and error skins by flag (`_is_default`, `_is_error`), not by key, so it needs no change. Only the registry keys' library prefix changes, from `haybale-studio:` to `haybale-graph-editor:`. The settings namespace `ui.node.skin` is unchanged, so stored values survive. graph-editor gains a `settings/` folder scan and no new package dependency.

**Tech Stack:** Python 3.12, NiceGUI, haywire registries (`SkinRegistry`, `SettingsRegistry`, `PanelRegistry`), pytest.

**Spec:** the slice-6 inquisition of 2026-10-19 (decisions below), recorded into [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md) by Task 3.

## Background: the slice-6 decisions this plan starts

Slice 6 (Inset) is split into three plans: **6a** (this one), **6b** groundwork and **6c** Inset. The ones that matter here:

- **Q11 B.** The NodeSkin family moves to haybale-graph-editor, the only library that draws node cards: it is the only `SkinFactory` user. **graph-editor never depends on haybale-studio.** InsetSkin (6c) will subclass NodeSkin there.
- **Q16 A.** graph-editor may import `haywire.barn.builtin` (types, surfaces) like every other library. The forbidden direction is builtin referencing anything outside core.
- **Q12 A / Q12b A.** No alias and no migration. A stored `haybale-studio:skin:*` key renders the error card ("Failed to use skin …"), which is the framework's normal signal for a missing skin. Re-picking the skin fixes it. No tracked graph, the repo's `.haywire/settings.json` and `~/.haywire/` hold no such key.
- **ADR:** one ADR, "The default skins live in the graph editor" (Task 3).

## Global Constraints

- Behaviour is unchanged: no rendering, layout or settings difference. Every existing skin test passes with only its imports changed.
- `barn/haybale-graph-editor/pyproject.toml` `dependencies` stays exactly `["haywire-core>=0.2.4", "nicegui>=3.12.1"]`. No `haybale_studio` import anywhere under `barn/haybale-graph-editor/`.
- `NodeSkinSettings` keeps `@settings(namespace="ui.node.skin", label="Node Skin")`, its 8 fields, and their defaults, ranges and labels.
- `NodeSkinSettingsPanel` keeps `surface=CanvasSettings` (builtin), `label="Skin"`, its description, `icon=hui.icon.skin`, `order=20` and `default_open=False`.
- `NodeSkinDefaultPanel` **stays** in studio, because it renders the core `NodeDefaultSkinSettings`, not the moved bag.
- New keys: `haybale-graph-editor:skin:StackedNodeSkin`, `…:SplitNodeSkin`, `…:ErrorNodeSkin`, and `haybale-graph-editor:panel:NodeSkinSettingsPanel`.
- Use `git mv` for every moved file so history follows.
- **Trap:** `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing` in teardown. Commit the `display_node.py` edit before any run that includes `tests/studio/`.

## Review Focus

1. **Stored skin geometry after the move.** A user's `ui.node.skin.pin_gutter` set before the move must still apply. Pinned by `test_node_skin_settings_keep_their_namespace` (Task 1).
2. **Registration order on load and on hot reload.** The skins import `NodeSkinSettings`. If the `settings/` folder were scanned after `skins/`, a force-reload would replace the settings class the skins already hold (the trap described in studio's `__init__.py` comment). Pinned by `test_graph_editor_scans_settings_before_skins` (Task 1).
3. **A stale `haybale-studio:skin:*` key.** It must render the error card, never crash or render blank. Pinned by `test_an_old_studio_skin_key_renders_the_error_card` (Task 1).
4. **graph-editor's independence.** No import of haybale_studio may come in now or later. Pinned by `test_graph_editor_never_imports_haybale_studio` (Task 1).
5. **The Skin panel stays where users find it.** Same surface, label and order. Pinned by `test_skin_settings_panel_lives_in_graph_editor` (Task 1).

---

### Task 0: Baseline

- [ ] **Step 1: Lint and type-check the two libraries**

Run:
```sh
uv run ruff check barn/haybale-studio barn/haybale-graph-editor tests/ui/skin tests/graph_editor
uv run mypy barn/haybale-studio/haybale_studio/ barn/haybale-graph-editor/haybale_graph_editor/
```
Expected: clean. If not, stop and open an error-fix session with the user (CLAUDE.md).

- [ ] **Step 2: Run the skin and graph-editor tests**

Run: `uv run pytest tests/ui/skin tests/graph_editor tests/ui/graph_canvas -m "not browser" -n 4 -q > /tmp/6a-base.log 2>&1; echo "exit=$?"`
Expected: `exit=0`. Keep the pass count for Task 2.

---

### Task 1: Tests that pin the new home

**Files:**
- Create: `tests/graph_editor/test_default_skins_home.py`

**Interfaces:**
- Consumes: fixtures `library_system`, `nicegui_slot_context` (tests/conftest.py). `library_system.injector.get(SkinFactory)`, `.get(PanelRegistry)`. `SkinRegistry.has(key)` / `.list_names()`, `get_default_skin_registry_key()`, `get_error_skin_registry_key()`.
- Produces: the module paths Task 2 must create, `haybale_graph_editor.skins.{node_skin,stacked_skin,split_skin,error_skin}`, `haybale_graph_editor.settings.node_skin_settings`, and `haybale_graph_editor.panels.properties.setting.skin`.

- [ ] **Step 1: Write the failing tests**

```python
GE = "haybale-graph-editor"

def test_default_and_error_skins_live_in_graph_editor(library_system):
    registry = library_system.injector.get(SkinFactory)._skin_registry
    assert registry.get_default_skin_registry_key() == f"{GE}:skin:StackedNodeSkin"
    assert registry.get_error_skin_registry_key() == f"{GE}:skin:ErrorNodeSkin"
    assert registry.has(f"{GE}:skin:SplitNodeSkin")
    assert not [k for k in registry.list_names() if k.startswith("haybale-studio:skin:")]

def test_node_skin_settings_keep_their_namespace():
    from haybale_graph_editor.settings.node_skin_settings import NodeSkinSettings
    assert NodeSkinSettings._namespace == "ui.node.skin"
    assert NodeSkinSettings._settings_descriptors()["pin_gutter"]._setting_key == "ui.node.skin.pin_gutter"

def test_skin_settings_panel_lives_in_graph_editor(library_system):
    from haywire.barn.builtin.surfaces import CanvasSettings
    panels = library_system.injector.get(PanelRegistry)
    assert panels.has(f"{GE}:panel:NodeSkinSettingsPanel")
    assert not panels.has("haybale-studio:panel:NodeSkinSettingsPanel")
    cls = panels.get(f"{GE}:panel:NodeSkinSettingsPanel")
    # Assert surface is CanvasSettings, label == "Skin", order == 20 through the
    # panel's class identity (read the attribute names off @panel in haywire/ui/panel/decorator.py).

def test_graph_editor_never_imports_haybale_studio():
    root = Path(__file__).resolve().parents[2] / "barn/haybale-graph-editor"
    offenders = [p for p in (root / "haybale_graph_editor").rglob("*.py")
                 if re.search(r"\bhaybale_studio\b", p.read_text())]
    assert offenders == []
    assert "haybale-studio" not in (root / "pyproject.toml").read_text()

def test_graph_editor_scans_settings_before_skins(monkeypatch):
    # Record folder names passed to Library.add_folder_to_registry during
    # haybale_graph_editor.Library.register_components (instance via __new__, method patched);
    # assert order.index("settings") < order.index("skins") and < order.index("panels").

def test_an_old_studio_skin_key_renders_the_error_card(library_system, nicegui_slot_context, monkeypatch):
    # Build a DisplayNode wrapper as tests/ui/skin/test_stage_render.py::_wrapper does.
    # Spy on type(error_skin).render (error_skin = factory.get_skin_instance(error key)),
    # calling through to the original. Then:
    card = factory.render("haybale-studio:skin:StackedNodeSkin", wrapper, on_stage=False)
    assert card is not None
    assert spy_calls == 1
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run pytest tests/graph_editor/test_default_skins_home.py -v`
Expected: the key, namespace, panel and order tests FAIL (keys still `haybale-studio:…`, modules missing). `test_graph_editor_never_imports_haybale_studio` and `test_an_old_studio_skin_key_renders_the_error_card` PASS already. They pin behaviour that has to survive the move.

- [ ] **Step 3: Commit the tests**

```bash
git add tests/graph_editor/test_default_skins_home.py
git commit -m "test(graph-editor): pin the default skins' new home"
```

---

### Task 2: Move the skins, the settings bag and the Skin panel

**Files (all `git mv`; paths relative to `barn/`):**
- `haybale-studio/haybale_studio/skins/{node_skin,stacked_skin,split_skin,error_skin}.py` → `haybale-graph-editor/haybale_graph_editor/skins/`
- `haybale-studio/haybale_studio/settings/node_skin_settings.py` → `haybale-graph-editor/haybale_graph_editor/settings/node_skin_settings.py`
- Create: `haybale-graph-editor/haybale_graph_editor/settings/__init__.py` (empty, like studio's)
- Create: `haybale-graph-editor/haybale_graph_editor/panels/properties/setting/skin.py`, holding `NodeSkinSettingsPanel` cut from `haybale-studio/haybale_studio/panels/properties/setting/canvas.py`
- Modify: `haybale-studio/haybale_studio/panels/properties/setting/canvas.py` (remove the class, its import and its module-docstring line), `haybale-studio/haybale_studio/panels/__init__.py` (drop the import and the `__all__` entry)
- Modify: `haybale-graph-editor/haybale_graph_editor/__init__.py` (scan `settings/` with `SettingsRegistry` **first**, before `state`, so any module importing the bag sees the registered class)
- Modify: `haybale-graph-editor/haybale_graph_editor/skins/__init__.py` docstring → "The default node skins: Stacked (default), Split, Error, and their NodeSkin base."
- Modify: `node_skin_settings.py` line 1 header comment → `# haybale_graph_editor/settings/node_skin_settings.py`
- Modify: `haybale-testing/haybale_testing/nodes/testbed/display_node.py:18` key → `"haybale-graph-editor:skin:SplitNodeSkin"`
- Tests, imports and paths only (`haybale_studio.skins` → `haybale_graph_editor.skins`, `haybale_studio.settings.node_skin_settings` → `haybale_graph_editor.settings.node_skin_settings`, `barn/haybale-studio/haybale_studio/skins` → `barn/haybale-graph-editor/haybale_graph_editor/skins`, `haybale-studio:skin:` → `haybale-graph-editor:skin:`):
  `tests/graph_editor/test_fold_toggle_route.py:138`, `tests/graph_editor/test_warning_badge.py:17-18,76-78`, `tests/graph_editor/test_ui_node_stage_skin.py:73-74`, `tests/ui/graph_canvas/test_node_size_apply.py:196`, `tests/ui/skin/test_node_skin_is_collapsed.py:42,86,109,177,187`, `tests/ui/skin/test_detail_render.py:185`, `tests/ui/skin/test_node_skin_settings.py:21,28`, `tests/ui/skin/test_skins_write_nothing.py:13,30`, `tests/ui/skin/test_stage_render.py:67,360`, `tests/ui/skin/test_port_row_depth_indent.py` (all `haybale_studio` lines), `tests/ui/harness/routes.py:342,353-355,434`

**Interfaces:**
- Consumes: Task 1's test module paths.
- Produces: `haybale_graph_editor.skins.node_skin.NodeSkin` (6c subclasses it), `haybale_graph_editor.settings.node_skin_settings.NodeSkinSettings`.

- [ ] **Step 1: `git mv` the six files and create the new ones listed above**

`node_skin.py`'s relative import `from ..settings.node_skin_settings import NodeSkinSettings` stays valid as is.

- [ ] **Step 2: Update the test imports, paths and keys listed above**

Afterwards, `grep -rn "haybale_studio\.skins\|haybale_studio\.settings\.node_skin\|haybale-studio:skin\|haybale_studio/skins" tests barn packages --include=*.py` must print nothing.

- [ ] **Step 3: Run Task 1's tests**

Run: `uv run pytest tests/graph_editor/test_default_skins_home.py -v`
Expected: all PASS.

- [ ] **Step 4: Run the Task 0 tier and compare**

Run: `uv run pytest tests/ui/skin tests/graph_editor tests/ui/graph_canvas -m "not browser" -n 4 -q > /tmp/6a-move.log 2>&1; echo "exit=$?"`
Expected: `exit=0`, with the Task 0 count + 6.

- [ ] **Step 5: Lint and type-check**

Run the Task 0 Step 1 commands plus `uv run ruff format --check barn/haybale-studio barn/haybale-graph-editor tests`.
Expected: clean.

- [ ] **Step 6: Commit** (before any run that includes `tests/studio/`; see Global Constraints)

```bash
git add -A barn/haybale-studio barn/haybale-graph-editor barn/haybale-testing/haybale_testing/nodes/testbed/display_node.py tests
git commit -m "refactor(skins): the default skins, their settings and Skin panel move to haybale-graph-editor"
```

---

### Task 3: ADR, docs and the slice-6 spec

**Files:**
- Create: `docs/adr/0057-the-default-skins-live-in-the-graph-editor.md`
- Modify: `docs/components/skins/skin-canon.md`: in "Stage view: the stage skin…" (`:405`) or a new short section "Where the default skins live", one paragraph: Stacked, Split and Error, their `NodeSkin` base and `NodeSkinSettings` ship in haybale-graph-editor (`haybale_graph_editor.skins.node_skin.NodeSkin`); a third-party skin that subclasses NodeSkin depends on haybale-graph-editor.
- Modify: `.codemap/modules/haybale-studio.md:15` (drop "and the studio's default theme/skin set" → "and the studio's default themes") and `.codemap/modules/haybale-graph-editor.md` (add the skins, the settings bag and the Skin panel)
- Modify: [2026-10-12-editor-modes.md](2026-10-12-editor-modes.md): rewrite the **Inset (bpatcher)** section and Sequence item 6 from the Background above and the full ruling list below. Add placement value overrides, auto-fit, Inset edges and the shared edge-drawing JS module to **Not in scope**.
- Modify: [2026-10-16-edit-route.md](2026-10-16-edit-route.md) `:164-168`: an Inset widget follows the host level's mode; in `edit` it records an ordinary value step (no overrides).
- Regenerate: library docs for both libraries

**The slice-6 rulings for the spec rewrite (from the 2026-10-19 inquisition):**
- An Inset is a Graph-node card (Group or placement) whose body shows the interior's **stage**, in every level mode. Widgets write through an interior route `Editor(definition, …, host history)` at the **host route's mode**. Placement values stay runtime state (ADR 0038 unchanged).
- InsetSkin is a NodeSkin subclass in graph-editor, tagged `special` + `graph-node`, listed by a core `_graph_node_skin_choices()` for Graph-nodes' patch and stage skin lists. It can be set per view.
- Patch face: the title, then the body as the card body, with bare pin columns or strips on the layout's edges plus root ghost pins. Layout direction and collapse are honoured. No folds, detail, labels, widgets or config ports. Stage face: the body only.
- Body: an InsetView of plain `UINode`s, each drawn with its stage skin and absolutely positioned at `stage_x/y`. The interior cards' containers carry no `data-node-id`. Clipped. Fixed 240 × 160 floor. Placeholder "Nothing on stage — Enter to arrange".
- `GraphNode._on_definition_validated` redraws the card on any interior `requires_redraw()` or `NODE_STAGE_CHANGED`, unconditionally. A value write never redraws.
- One CSS rule: inside `[data-hw-inset]` only `[data-hw-operable]` subtrees take pointer input, and pins are hidden. Box select skips Inset contents.
- Sub-plans: 6a this plan. 6b groundwork (interior redraw, `graph-node` tag and choices, `SkinFactory._unregister_node` per card if the all-cards bug is confirmed). 6c Inset.

- [ ] **Step 1: Write ADR 0057**

Front matter like ADR 0056 (`name`, `description`, `status: accepted`, `see-also: ADR-0056`, `level: library`). Sections:
- **Context:** only graph-editor draws node cards. The Inset needs NodeSkin in graph-editor, and graph-editor must not depend on haybale-studio.
- **Decision:** the family, the bag (namespace unchanged) and the Skin panel move. The keys' prefix changes. There is no alias: a stored old key renders the error card. graph-editor imports builtin types and surfaces like any library. Builtin references nothing outside core. `NodeSkinDefaultPanel` stays in studio.
- **Considered:** NodeSkin into core (core grows by about 860 lines of layout code plus a library settings bag); graph-editor depending on studio (breaks its independence); an alias table (permanent special case for a one-off move).
- **Consequences:** graph-editor draws cards without studio installed. Third-party NodeSkin subclasses import from haybale_graph_editor. Stored `haybale-studio:skin:*` keys show error cards until re-picked.

- [ ] **Step 2: Edit the skin canon, codemap, editor-modes spec and edit-route plan as listed**

- [ ] **Step 3: Regenerate the library docs**

Run: `uv run haywire docs barn/haybale-studio && uv run haywire docs barn/haybale-graph-editor && uv run haywire docs barn/haybale-testing`
Expected: `barn/haybale-studio/haybale_studio/docs/haybale-studio.{skin.StackedNodeSkin,skin.SplitNodeSkin,skin.ErrorNodeSkin,setting.NodeSkinSettings,panel.NodeSkinSettingsPanel}.md` are gone and graph-editor has the five matching `haybale-graph-editor.*` pages. If the generator leaves the old studio pages, `git rm` them. OVERVIEW/QUICKREF are updated for both libraries.

- [ ] **Step 4: Check the docs build**

Run: `uv run mkdocs build --strict 2>&1 | tail -5`
Expected: no new warnings for the ADR or the edited pages.

- [ ] **Step 5: Commit**

```bash
git add docs .codemap barn/haybale-studio barn/haybale-graph-editor barn/haybale-testing
git commit -m "docs: ADR 0057 — the default skins live in the graph editor; slice-6 spec"
```

---

### Task 4: Full verification and live check

- [ ] **Step 1: Quality gates**

Run: `uv run ruff check . && uv run ruff format --check .` and the full mypy command from CLAUDE.md.
Expected: clean. A known pre-existing failure on tracked `.scratch/draw-perf/*.py` should be reported, not fixed here.

- [ ] **Step 2: Non-browser suite**

Run: `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/6a-full.log 2>&1; echo "exit=$?"; grep -E "^FAILED|^ERROR" /tmp/6a-full.log`
Expected: `exit=0`. The one known fixture failure from the user's modified `graphs/any_and_nonde.haywire` may appear. Report it, don't fix it.

- [ ] **Step 3: Browser suite**

Run: `uv run pytest -m browser -n 4 -q > /tmp/6a-browser.log 2>&1; echo "exit=$?"`
Expected: `exit=0`.

- [ ] **Step 4: Live check (user)**

1. `uv run haywire`, then open a graph. Cards look exactly as before in both patch and stage view.
2. Properties → a node → Skin lists Stacked and Split as before. Picking Split redraws the card as Split.
3. Canvas settings → **Skin** panel is present under the same heading. Changing Pin Gutter moves the pins live, and the value persists across a restart.
4. Hot-reload: touch `barn/haybale-graph-editor/haybale_graph_editor/skins/stacked_skin.py` (add and remove a blank line). The cards redraw without errors.
5. App settings → **Default Skins** panel (studio) still lists the skins under their new keys.

# Editor modes, slice 5d-3b: widget-node style bag — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A widget node's stage face can be styled per node: the label's typography, the card's background and border, the label's position, and its maximum width. This follows the `AnnotationNode` pattern: a settings bag on the node, which the skin reads. The label/control split becomes one rule shared with the properties panel: the label takes half the row, capped at a maximum width.

**Architecture:**
- **The bag:** `WidgetNode` gains a node settings bag, accessor `style`, inherited by all seven widget nodes. Every field is `Promotable.NONE`.
- **Redraw:** `post_init` subscribes each field to `wrapper.redraw()`, as `AnnotationNode` does.
- **The skin:** `WidgetNodeSkin` reads `node.style`. A node without a `style` bag (a third-party node using the skin) draws today's face. The patch skins ignore the bag.
- **Shared fonts:** the annotation's font choices and CSS font stacks move to one headless module, `haywire.core.skin.fonts`, which both skins import (Q4 a).
- **One split rule:** `.sf-label` becomes `width: min(50%, var(--hw-max-label-width, 9rem))`, replacing the two-step container query in `app/shell.py`. The skin sets `--hw-max-label-width` only when the node sets a maximum.

**Tech Stack:** Python 3.12, NiceGUI 3 / Quasar, pytest, Playwright browser tier.

**Spec:** The user's rulings of 2026-10-19 on top of [5d-3](2026-10-18-editor-modes-05d3-widget-nodes.md):
- **Q1 (c), the fields:**
  - label typography (font, size, bold, italic, colour, alignment in its part of the row);
  - the card (background colour, border on/off);
  - layout (label position left/above/hidden, the label's share of the width).
- **Q2 (a):** not promotable.
- **Q3 (b):** accessor `style`.
- **Q4 (a):** one shared font list.
- **Max label width** (user, 2026-10-19): the label is 50/50 with the control until the row is twice the maximum, and never grows beyond it. Empty means 9rem. The properties panel adopts the same rule (option a), which replaces its 50/50-then-9rem-from-320px step.

## Global Constraints

- **Branch:** continue directly on `feat/editor-modes-slice1` (tip `b3f2afcc`). This joins slice 5d-3's squash after the user's live check: tag the tip `editor-modes-slice5d3-full`, then `git reset --soft 74bba92c` and make one commit.
- **The user's uncommitted files** (`.claude/settings.local.json`, `docs/components/nodes/node-canon.md`, `graphs/any_and_nonde.haywire`, `.scratch/docs-story/`): stage explicit paths only. While `any_and_nonde.haywire` is modified, `test_prehydration` fails; report it, don't restore it.
- **Saved files:** an untouched graph saves byte-identical. A widget node at its defaults writes no `style` values.
- **No nicegui on the headless path:** `haywire.core.skin.fonts` is a leaf module with no imports.
- **Not in scope:** promoting style fields; live restyle without a redraw; a style bag for the patch card.

## Decisions

1. **`haywire.core.skin.fonts`** (new, `packages/haywire-core/src/haywire/core/skin/fonts.py`):
   - `FONTS = ("sans", "serif", "mono", "handwriting")` and `FONT_STACKS: dict[str, str]`, moved verbatim from `annotation.py`'s `FONTS` and `annotation_skin.py`'s `_FONT_STACKS`.
   - Both annotation modules import them from here. `annotation.py` keeps the name `FONTS` re-exported, so existing imports work.
2. **The `style` bag** on `WidgetNode`, `class style(NodeSettings)`. Every field is `promotable=Promotable.NONE`. Labels, categories, orders and defaults:

   | Field | Type | Default | Label | Category / order | Notes |
   |---|---|---|---|---|---|
   | `label_position` | `CHOICES` | `"left"` | Label Position | layout / 1 | options `LABEL_POSITIONS = ("left", "above", "hidden")` |
   | `max_label_width` | `OPTIONAL[INT]` | `None` | Max Label Width | layout / 2 | px, `min=40, max=600`; description "The widest the label gets when it is on the left: it takes half the row up to this width. None is 9rem, as in the properties panel" |
   | `label_align` | `CHOICES` | `"left"` | Label Alignment | layout / 3 | options `H_ALIGNS` (`left`, `center`, `right`) |
   | `font` | `CHOICES` | `"sans"` | Font | font / 10 | options `list(FONTS)` |
   | `font_size` | `INT` | `14` | Text Size | font / 11 | `min=6, max=72` |
   | `bold` | `BOOL` | `False` | Bold | font / 12 | |
   | `italic` | `BOOL` | `False` | Italic | font / 13 | |
   | `label_color` | `COLOR` | `""` | Label Color | colors / 20 | empty uses the theme's text colour |
   | `background` | `COLOR` | `""` | Background | colors / 21 | empty draws none |
   | `border` | `BOOL` | `False` | Border | colors / 22 | the theme's node border |

   - `LABEL_POSITIONS` and `H_ALIGNS` live in `haybale_core/nodes/widgets/base.py`. `H_ALIGNS` is imported from `annotation.py`.
   - `post_init` adds `self.style._subscribe_field(name, self._redraw_card)` for every style field. `_redraw_card(value, old)` calls `self.wrapper.redraw()` when the wrapper is set.
3. **What the skin draws** (`WidgetNodeSkin.render`, reading `getattr(node, "style", None)`; `None` means all defaults):
   - **Card:**
     - `background: <background>`, or `transparent` when it is empty.
     - With `border`: `border: var(--hw-node-border-width) solid var(--hw-node-border-color); border-radius: var(--hw-node-border-radius)`. Otherwise no border.
   - **Label style** (`_label_style(style) -> str`, a module function): `font-family: FONT_STACKS[font]`, `font-size: <font_size>px`, `font-weight` 700 when bold (else 400), `font-style` italic when italic (else normal), and `text-align: <label_align>`. It also sets `color: <label_color>` when that is set.
   - **`label_position`:**
     - **left:** today's row, with `sf-label` / `sf-widget`. With `max_label_width = n` set, the row gets `style="--hw-max-label-width: <n>px"`; the shared rule (Decision 4) does the rest.
     - **above:** a column. The label is full width on top and the control full width below, with no `sf-*` classes.
     - **hidden:** no label element; the control takes the full width.
   - `data-widget-node-label` stays on the label; the face row gains `data-widget-node-face="<label_position>"`.
   - The card drops `container-type` / `container-name` (nothing queries it now) and keeps its `min-width: 180px` floor and `compact-fields`.
4. **The shared split rule** in `packages/haywire-core/src/haywire/ui/app/shell.py` (`STATIC_CSS`), replacing the `.sf-label` / `.sf-widget` lines and the `@container settings-panel` block:
   ```css
   .sf-label  { width: min(50%, var(--hw-max-label-width, 9rem)); flex: none; }
   .sf-widget { flex: 1 1 0; min-width: 0; }
   ```
   - The comment above it says: the label takes half the row up to `--hw-max-label-width` (default 9rem), and the control takes the rest. So the row is 50/50 until it is twice the maximum wide.
   - `render_utils._COLUMN_STYLE` keeps its container declaration (no layout depends on it now; removing it is not part of this slice).

## Review Focus

1. **The default face is unchanged.** A widget node at its defaults draws exactly today's face: the same classes and no inline label width. Test: Task 2 `test_default_style_draws_todays_face`.
2. **A third-party node without a `style` bag**, drawn by `WidgetNodeSkin`, does not raise and draws today's face. Test: Task 2 `test_a_node_without_a_style_bag_draws_the_default_face`.
3. **An untouched graph saves no style values.** Test: Task 1 `test_a_default_widget_node_saves_no_style_values`.
4. **Undo of a style change** restores the old face (the change is a settings write through the route). Test: Task 1 `test_a_style_change_redraws_and_undoes`.
5. **Max label width with the label above or hidden** is ignored; nothing breaks. Test: Task 2 `test_max_label_width_applies_only_on_the_left`.

---

### Task 1: Shared fonts and the `style` bag

**Files:**
- Create: `packages/haywire-core/src/haywire/core/skin/fonts.py` (Decision 1)
- Modify:
  - `packages/haywire-core/src/haywire/barn/builtin/nodes/annotation.py` (import `FONTS` from `core.skin.fonts`)
  - `packages/haywire-core/src/haywire/barn/builtin/skins/annotation_skin.py` (use `FONT_STACKS`; delete `_FONT_STACKS`)
  - `barn/haybale-core/haybale_core/nodes/widgets/base.py` (Decision 2)
- Test: `tests/barn/test_widget_nodes.py` (append), `tests/core/test_skin/test_fonts.py` (new, unit)

**Interfaces:**
- Produces: `haywire.core.skin.fonts.FONTS`, `FONT_STACKS`; `WidgetNode.style` with the Decision 2 fields; `LABEL_POSITIONS`.

- [ ] **Step 1: Write the failing tests:**
  - `test_every_font_has_a_stack`: `set(FONT_STACKS) == set(FONTS)`, and `annotation.FONTS is fonts.FONTS`.
  - `test_every_widget_node_has_the_style_bag` (parametrized over the seven classes): the bag has the Decision 2 fields with their defaults, and every descriptor has `_promotable is Promotable.NONE`.
  - `test_a_default_widget_node_saves_no_style_values`: a fresh Float Slider's `_to_dict()["settings"]["style"]["values"] == {}`.
  - `test_a_style_change_redraws_and_undoes`: through an `EditRoute` in EDIT, `set_setting(node.style, "bold", True, minimum=LevelMode.EDIT)` calls the patched `wrapper.redraw` once, and `editor.undo()` restores `bold is False`.
- [ ] **Step 2:** Run `uv run pytest tests/core/test_skin/test_fonts.py tests/barn/test_widget_nodes.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement Decisions 1 and 2.
- [ ] **Step 4:** Run the tests again, plus `tests/ui/skin/ tests/barn/ -q` and `uv run pytest -m browser -n 4 tests/ui/harness/test_annotation_node.py -q`. Expected: PASS.
- [ ] **Step 5:** Commit `feat(haybale-core): the widget-node style bag; fonts shared with annotations`.

### Task 2: The skin draws the style

**Files:**
- Modify:
  - `barn/haybale-core/haybale_core/skins/widget_node_skin.py` (Decision 3)
  - `packages/haywire-core/src/haywire/ui/app/shell.py` (Decision 4)
  - `tests/ui/harness/routes.py`: `/graph-widget-nodes` gains three on-stage Float Sliders, each with its node-id label:
    - `styled`, manual 400×120, with `label_position = "above"`, `bold = True` and `background = "#203040"`;
    - `capped`, manual 400×60, with `max_label_width = 80`;
    - `capped_narrow`, manual 140×60, with `max_label_width = 80`.
- Test: `tests/ui/skin/test_widget_node_skin.py` (append), `tests/ui/harness/test_widget_nodes.py` (append and update), `tests/ui/test_shell_split_rule.py` (new, unit)

**Interfaces:**
- Consumes: `WidgetNode.style`, `FONT_STACKS`, `LABEL_POSITIONS` (Task 1).

- [ ] **Step 1: Write the failing tests:**
  - `test_default_style_draws_todays_face`: the label carries `sf-label`, the control `sf-widget`, the label has no inline `width`, and the card's style has `background: transparent` and no `border:`.
  - `test_a_node_without_a_style_bag_draws_the_default_face`: render a Float Slider with `style` replaced by `None` on the instance (`object.__setattr__(node, "style", None)`). The face matches the default and nothing raises.
  - `test_label_typography_reaches_the_label`: with font `mono`, size 20, bold, italic, colour `#ff0000` and align `right`, the label's style contains `font-family: ui-monospace`, `font-size: 20px`, `font-weight: 700`, `font-style: italic`, `color: #ff0000` and `text-align: right`.
  - `test_background_and_border_reach_the_card`: `background = "#203040"` and `border = True` give a card style containing `background: #203040` and `border: var(--hw-node-border-width)`.
  - `test_label_above_stacks_label_over_control` and `test_label_hidden_draws_no_label`: `data-widget-node-face` is `above` or `hidden`; with hidden, no `data-widget-node-label` element exists.
  - `test_max_label_width_applies_only_on_the_left`: `max_label_width = 80` puts `--hw-max-label-width: 80px` on the left-label row. With `above` or `hidden`, no element carries it, and nothing raises.
  - `test_the_split_rule_caps_half_the_row` (unit, `tests/ui/test_shell_split_rule.py`): `STATIC_CSS` contains `width: min(50%, var(--hw-max-label-width, 9rem))` and no `@container settings-panel`.
  - Browser:
    - `test_a_label_above_sits_over_its_control`: on the `styled` card, the label box's bottom is at or above the slider box's top, and both are wider than 300px.
    - `test_a_max_label_width_caps_the_label`: on `capped` the label is 80px wide (±2) and the control takes the rest. On `capped_narrow` (row narrower than 2 × 80) label and control are equal (±4).
    - The existing `test_a_wide_card_gives_the_control_the_extra_width` (400px → 9rem label) and `test_a_narrow_card_splits_label_and_control_evenly` (260px → 50/50) keep passing under the new rule.
- [ ] **Step 2:** Run `uv run pytest tests/ui/skin/test_widget_node_skin.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement Decision 3.
- [ ] **Step 4:** Run the tests again, plus `uv run pytest -m browser -n 4 tests/ui/harness/test_widget_nodes.py tests/ui/harness/test_graph_views.py tests/ui/harness/test_widgets.py tests/ui/harness/test_promote_flyout.py tests/ui/harness/test_external_sync.py -q` (the last three exercise the properties panel's rows). Expected: PASS.
- [ ] **Step 5:** Commit `feat(haybale-core): the widget-node skin draws its style bag; one label/control split rule`.

### Task 3: Docs and gates

**Files:**
- Modify:
  - `docs/reference/glossary.md`: the **Widget-node skin** row adds "styled per node by the widget node's `style` bag (label typography, card background and border, label position, maximum label width)".
  - `docs/reference/design-guide.md`: where it describes settings-row layout (search `sf-label` / `9rem`), state the rule: the label takes half the row up to `--hw-max-label-width` (9rem), and the control takes the rest.
  - `docs/components/skins/skin-canon.md`: in the widget-node paragraph, one sentence on the `style` bag: the node owns it, the skin reads it, and a node without one draws the default face.
  - `docs/superpowers/plans/2026-10-12-editor-modes.md`: the 5d-3 line also links this plan.

- [ ] **Step 1:** Make the doc edits.
- [ ] **Step 2:** Run the gates:
  - `uv run ruff check . --extend-exclude .scratch/draw-perf -q` and `uv run ruff format --check .` (only `.scratch/draw-perf` may drift)
  - the full mypy command from CLAUDE.md
  - `uv run pytest -m "not browser and not perf" -n 4 -q` (only the known `test_prehydration` fixture failure is allowed)
  - `uv run pytest -m browser -n 4 -q`
  - `uv run haywire docs --all`, then commit the regenerated library docs.

  Expected: all exit 0, apart from the one noted fixture.
- [ ] **Step 3:** Commit `docs: widget-node style bag — glossary, skin canon, spec`.

### Live check (user, studio started from the main checkout)

1. Add a Float Slider to the stage. With no style set it looks as before.
2. In its properties, under *style*: set Font to Mono, Text Size to 20, Bold and a red Label Color. The stage label changes, and the patch card does not.
3. Set Background to a dark blue and turn on Border: the stage card fills and gets the theme's node border.
4. Set Label Position to *Above*, then *Hidden*: the label moves over the slider, then disappears, and the slider takes the full width.
5. Back to *Left*, set Max Label Width to 80: on a wide card the label stops at 80px; shrink the card below 160px and label and control share it evenly. Clear it: the label caps at 9rem again.
6. The properties panel's rows follow the same rule: narrow the panel and label and control share it evenly, widen it and the label stops at 9rem without a jump.
7. Undo steps back through each change. Save, close and reopen: the style is as left.

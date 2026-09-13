# Fold Depth Indentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make port-row indentation a property of the row's *content column* so a nested port's pin stays anchored to the card border at any depth.

**Architecture:** A port row is already a two-column CSS grid — `{PIN_GUTTER}px 1fr`, pin in column 1, label+widget in column 2. Today `StackedNodeSkin._render_group` indents the *whole row* with `pl-2 ml-1`, which falsifies the assumption behind the pin's negative offset (`card_padding + pin_gutter // 2 + pin_protrusion`) and insets the pin from the card border once per nesting level. This plan moves indentation onto the content column and passes an explicit `depth` down the render path. The pin column's geometry is never touched, so the existing offset formula stays correct with no change to `render_pin`.

**Tech Stack:** Python 3.12, NiceGUI 3.13, pytest.

## Global Constraints

- Line length 109 (`ruff`). CI runs BOTH `ruff check .` and `ruff format --check .`.
- Type checking via `mypy` over the package list in `CLAUDE.md`.
- Do NOT change `packages/haywire-core/src/haywire/ui/skin/pin_render.py`. The offset formula is correct; this plan makes its precondition true again.
- Indentation must apply to the content column ONLY — the column holding both the label and the widget.
- `tests/ui/skin/` tests are unit tests (`pytestmark = pytest.mark.unit`).

## Pre-Flight Baseline

Before Task 1, establish the baseline required by `CLAUDE.md`:

```sh
uv run ruff check barn/haybale-studio/haybale_studio/skins/
uv run mypy barn/haybale-studio/haybale_studio/skins/
uv run pytest tests/ui/skin/ -q
```

All three must be clean. If not, stop and raise it with the user.

## File Structure

| File | Responsibility |
|---|---|
| `barn/haybale-studio/haybale_studio/settings/node_skin_settings.py` | Owns the user-tunable geometry bag. Gains `fold_indent`. |
| `barn/haybale-studio/haybale_studio/skins/node_skin.py` | Owns `render_port`, `_render_port_horizontal`, `_render_config`. Gains a `FOLD_INDENT` accessor and a `depth` parameter that feeds the content column's inset. |
| `barn/haybale-studio/haybale_studio/skins/stacked_skin.py` | Owns `_render_port_hierarchy` / `_render_group`. Stops indenting whole rows; passes `depth` down instead. |
| `tests/ui/skin/test_port_row_depth_indent.py` | New. Proves the pin column's geometry is depth-invariant and the content column's inset grows with depth. |

---

### Task 1: Content-column indentation in `_render_port_horizontal`

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/skins/node_skin.py:367-393` (`render_port`), `:395-468` (`_render_port_horizontal`)
- Test: `tests/ui/skin/test_port_row_depth_indent.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `NodeSkinSettings.fold_indent` — `setting[INT]`, default `12`, `category="layout"`.
  - `NodeSkin.FOLD_INDENT` — an `@property` over it, matching its six siblings.
  - `NodeSkin._content_inset(self, depth: int) -> int` — an **instance** method.
  - `NodeSkin.render_port(self, port, wrapper, widget_classes="", layout=None, depth=0)`
  - `NodeSkin._render_port_horizontal(self, port, wrapper, *, side, layout, widget_classes="", depth=0)`
  - Task 3 relies on both `depth` keyword names exactly as spelled.

⚠️ **Every geometry value on `NodeSkin` is an `@property`, not a class constant**
(`node_skin.py:57-82`): `PIN_GUTTER`, `CONTENT_GAP`, `PIN_PROTRUSION`,
`PIN_ROW_HEIGHT`, `PIN_COLUMN_WIDTH` and the `CARD_*` pair. Each reads
`self._ui_settings`, a live `NodeSkinSettings` bag the user edits in the settings
panel. So:

- `_content_inset` and `_config_indent` MUST be instance methods reading
  `self.CONTENT_GAP` / `self.PIN_GUTTER` / `self.FOLD_INDENT`. As
  `@staticmethod`s referencing `NodeSkin.CONTENT_GAP` they would get the
  property *descriptor* and raise `TypeError` on the arithmetic — broken at
  runtime, not only in the tests.
- The fold indent joins them as a **setting**, not a hardcoded constant: it is
  node geometry like the rest, and a user who wants flat cards sets it to `0`.
- Tests construct a skin with `StackedNodeSkin.__new__(StackedNodeSkin)`, the
  pattern `tests/ui/skin/test_node_skin_is_collapsed.py:40-46` already uses —
  it bypasses `__init__`, which needs a widget factory and builds a settings bag.
  A test touching a geometry property must set `_ui_settings` itself.

ℹ️ **`content_gap` defaults to `-15`**, not a positive number — it deliberately
overlaps into the empty half of the pin gutter. So `_content_inset(0)` is
negative, and depth adds to a negative base. That is correct; do not "fix" it.

ℹ️ Two things wire themselves and need no extra work. The settings panel calls
`render_schema(ctx, NodeSkinSettings, registry)`, so a new field renders
automatically. And `test_node_skin_settings.py` enforces that every declared
field is read somewhere under the skins directory by grepping for
`self._ui_settings.<name>` — the `FOLD_INDENT` property body satisfies it.

- [x] **Step 1: Write the failing test**

Create `tests/ui/skin/test_port_row_depth_indent.py`:

```python
"""Depth indents a port row's CONTENT column, never its pin column.

The load-bearing property: a pin is placed by a negative offset computed from
`card_padding`, which assumes its row begins at the card edge. Indenting the
whole row falsifies that and insets the pin from the border once per nesting
level, silently. Indentation therefore belongs on the content column, whose
geometry no pin offset reads.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def skin():
    """A skin with stubbed geometry settings.

    Built with ``__new__`` — the pattern in ``test_node_skin_is_collapsed.py`` —
    because ``__init__`` needs a widget factory and constructs a real
    ``NodeSkinSettings``. The geometry accessors are ``@property`` reads off
    ``_ui_settings``, so stubbing that bag is what makes them answer.
    """
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    instance = StackedNodeSkin.__new__(StackedNodeSkin)
    instance._ui_settings = SimpleNamespace(
        card_padding=16,
        pin_gutter=20,
        pin_protrusion=0,
        # The real default is negative — it overlaps into the empty half of the
        # gutter — so the stub uses it rather than a tidier positive number.
        content_gap=-15,
        pin_row_height=24,
        pin_column_width=24,
        card_padding_block=8,
        fold_indent=12,
    )
    return instance


def test_fold_indent_is_a_declared_setting() -> None:
    """Node geometry is user-tunable; the fold indent is geometry like the rest."""
    from haybale_studio.settings.node_skin_settings import NodeSkinSettings

    assert "fold_indent" in NodeSkinSettings._settings_descriptors()


def test_geometry_accessors_are_properties() -> None:
    """Guards the trap this plan was corrected for: these are NOT class constants.

    Reading them off the class yields the descriptor, and arithmetic on that
    raises TypeError.
    """
    from haybale_studio.skins.node_skin import NodeSkin

    assert isinstance(NodeSkin.CONTENT_GAP, property)
    assert isinstance(NodeSkin.PIN_GUTTER, property)
    assert isinstance(NodeSkin.FOLD_INDENT, property)


def test_content_inset_grows_with_depth(skin) -> None:
    """The content column's inset is CONTENT_GAP + depth * FOLD_INDENT."""
    gap = skin.CONTENT_GAP
    step = skin.FOLD_INDENT

    assert skin._content_inset(0) == gap
    assert skin._content_inset(1) == gap + step
    assert skin._content_inset(3) == gap + 3 * step


def test_content_inset_follows_the_live_settings(skin) -> None:
    """Both values are user-editable, so the inset must re-read them, not cache."""
    skin._ui_settings.content_gap = 9
    skin._ui_settings.fold_indent = 20
    assert skin._content_inset(1) == 29


def test_a_zero_fold_indent_flattens_the_card(skin) -> None:
    """0 is a legitimate choice, which is half the reason this is a setting."""
    skin._ui_settings.fold_indent = 0
    assert skin._content_inset(0) == skin._content_inset(4)


def test_negative_depth_is_clamped(skin) -> None:
    assert skin._content_inset(-1) == skin.CONTENT_GAP
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/skin/test_port_row_depth_indent.py -v`
Expected: FAIL. Most tests fail with `AttributeError` — `'StackedNodeSkin' object
has no attribute '_content_inset'`, and `NodeSkin.FOLD_INDENT` missing;
`test_fold_indent_is_a_declared_setting` fails with `AssertionError`.

- [x] **Step 3: Declare the setting**

In `barn/haybale-studio/haybale_studio/settings/node_skin_settings.py`, add to
the "Pin geometry" block, beside `content_gap`:

```python
    fold_indent = setting[INT](
        12,
        label="Fold Indent",
        description="How far a folded port's label and widget step right per "
        "nesting level (px). 0 renders a flat card. Pins never indent",
        category="layout",
        min=0,
        max=40,
    )
```

- [x] **Step 4: Add the accessor and the inset helper**

In `barn/haybale-studio/haybale_studio/skins/node_skin.py`, add the property
beside its six siblings (after `CONTENT_GAP`, around line 73):

```python
    @property
    def FOLD_INDENT(self) -> int:  # noqa: N802
        return self._ui_settings.fold_indent
```

Then add the helper as an **instance method** — every value it reads is a
`@property` over live settings, so all of them come off `self`:

```python
    def _content_inset(self, depth: int) -> int:
        """Return the content column's left inset, in px, for a row at ``depth``.

        Applied to the content column only. A pin's offset is computed from
        ``card_padding`` and assumes its row starts at the card edge, so
        indenting the pin column would move the pin off the card border once
        per nesting level.
        """
        return self.CONTENT_GAP + max(0, depth) * self.FOLD_INDENT
```

- [x] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/ui/skin/test_port_row_depth_indent.py -v`
Expected: PASS (6 tests)

- [x] **Step 6: Thread `depth` through the two render methods**

In `render_port`, change the signature and forward the value:

```python
    def render_port(
        self,
        port: DataPort,
        wrapper: NodeWrapper,
        widget_classes: str = "",
        layout: LayoutDirection | None = None,
        depth: int = 0,
    ):
        """Render a port according to its port type.

        Horizontal layouts only for inlets/outlets — vertically they belong in
        :meth:`render_pin_strip`, which has no room for the label/widget column
        this builds. Config ports are pinless and render the same either way.

        ``layout`` resolves from the wrapper when omitted; pass it when
        rendering many ports so the chain resolves once per card.

        Args:
            depth: Fold nesting level, insetting the content column. The pin
                column is never inset — see ``FOLD_INDENT``.
        """
        layout = self.layout_of(wrapper) if layout is None else layout
        if port.is_config():
            self._render_config(
                port,
                wrapper,
                widget_classes="widget-container zoom-pan-lod2",
                depth=depth,
            )
        elif port.is_inlet() or port.is_outlet():
            self._render_port_horizontal(
                port,
                wrapper,
                side=layout.side_for(port),
                layout=layout,
                widget_classes="widget-container zoom-pan-lod2",
                depth=depth,
            )
```

In `_render_port_horizontal`, add `depth: int = 0` as the last keyword-only
parameter and replace the `content_margins` computation. The existing line is:

```python
        content_margins = (
            f"margin-left: {gap}px; margin-right: {g}px;"
            if pin_first
            else f"margin-left: {g}px; margin-right: {gap}px;"
        )
```

Replace it with:

```python
        # Depth insets the CONTENT side only. The pin side keeps the raw gutter,
        # so the pin column's geometry — and with it the offset render_pin
        # computes from card_padding — is unchanged at any depth.
        inset = self._content_inset(depth)
        content_margins = (
            f"margin-left: {inset}px; margin-right: {g}px;"
            if pin_first
            else f"margin-left: {g}px; margin-right: {inset}px;"
        )
```

Add to that method's docstring, after the existing `side` paragraph:

```
        ``depth`` insets the content column by one ``FOLD_INDENT`` per fold
        nesting level. The pin column is never inset.
```

- [x] **Step 7: Add the depth-invariance test**

Append to `tests/ui/skin/test_port_row_depth_indent.py`:

```python
def test_pin_cell_style_is_depth_invariant() -> None:
    """The pin column's grid placement must not vary with depth."""
    import inspect

    from haybale_studio.skins.node_skin import NodeSkin

    source = inspect.getsource(NodeSkin._render_port_horizontal)

    # Two pin renders (pin_first and its mirror). Neither cell_style may carry
    # the depth inset — that is the whole invariant this plan establishes.
    pin_cells = [
        line for line in source.splitlines() if "grid-column: {pin_column}" in line
    ]
    assert len(pin_cells) == 2, f"expected two pin cell placements, got {len(pin_cells)}"

    # The inset reaches the CONTENT margins only.
    assert "inset" in source, "the content column must use the depth inset"
    inset_lines = [line for line in source.splitlines() if "inset" in line]
    assert not any("pin_column" in line for line in inset_lines), (
        "the pin column must never be offset by depth"
    )


def test_render_port_accepts_depth() -> None:
    import inspect

    from haybale_studio.skins.node_skin import NodeSkin

    assert "depth" in inspect.signature(NodeSkin.render_port).parameters
    assert "depth" in inspect.signature(NodeSkin._render_port_horizontal).parameters
```

- [x] **Step 8: Run the tests**

Run: `uv run pytest tests/ui/skin/test_port_row_depth_indent.py -v`
Expected: PASS (8 tests)

- [x] **Step 9: Verify no regression in existing pin geometry**

Run: `uv run pytest tests/ui/skin/ -q`
Expected: all pass. `test_pin_render_layout.py` must be untouched and green — it
asserts the offset formula this plan deliberately does not change.

- [x] **Step 10: Commit**

```bash
git add barn/haybale-studio/haybale_studio/skins/node_skin.py tests/ui/skin/test_port_row_depth_indent.py
git commit -m "feat(skin): inset a port row's content column by fold depth

A pin is placed by a negative offset computed from card_padding, which
assumes its row begins at the card edge. Indenting the whole row insets
the pin from the border once per level. Indentation moves to the content
column, whose geometry no pin offset reads.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Depth in `_render_config`

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/skins/node_skin.py:522-537`
- Test: `tests/ui/skin/test_port_row_depth_indent.py`

**Interfaces:**
- Consumes: `NodeSkin._content_inset` and `NodeSkin.FOLD_INDENT` from Task 1.
- Produces:
  - `NodeSkin._config_indent(self, depth: int) -> int` — an **instance** method, for the same reason as `_content_inset`: `PIN_GUTTER` and `CONTENT_GAP` are `@property` reads off live settings.
  - `NodeSkin._render_config(self, port, wrapper, widget_classes="", depth=0)` — Task 3 calls it via `render_port` only.

A config port renders no pin, so it can inset wholesale with no conflict. It
already computes a symmetric `indent`; depth adds to the left side only.

- [x] **Step 1: Write the failing test**

Append to `tests/ui/skin/test_port_row_depth_indent.py`:

```python
def test_render_config_accepts_depth() -> None:
    import inspect

    from haybale_studio.skins.node_skin import NodeSkin

    assert "depth" in inspect.signature(NodeSkin._render_config).parameters


def test_config_indent_grows_with_depth(skin) -> None:
    """A config row is pinless, so depth adds to its existing symmetric indent."""
    base = max(0, skin.PIN_GUTTER + skin.CONTENT_GAP)
    step = skin.FOLD_INDENT

    assert skin._config_indent(0) == base
    assert skin._config_indent(2) == base + 2 * step


def test_config_indent_follows_the_live_settings(skin) -> None:
    """Both PIN_GUTTER and CONTENT_GAP are user-editable; neither may be cached."""
    skin._ui_settings.pin_gutter = 30
    skin._ui_settings.content_gap = 6
    assert skin._config_indent(0) == 36
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/skin/test_port_row_depth_indent.py::test_config_indent_grows_with_depth -v`
Expected: FAIL with `AttributeError: 'StackedNodeSkin' object has no attribute '_config_indent'`

- [x] **Step 3: Add the helper and thread `depth`**

Add beside `_content_inset` in `node_skin.py`, as an **instance** method:

```python
    def _config_indent(self, depth: int) -> int:
        """Return a config row's left indent, in px, for a row at ``depth``.

        A config port renders no pin, so the whole row may inset.
        """
        base = self.PIN_GUTTER + self.CONTENT_GAP
        return max(0, base) + max(0, depth) * self.FOLD_INDENT
```

Change `_render_config`'s signature and body. The existing head is:

```python
    def _render_config(
        self,
        port,
        wrapper: NodeWrapper,
        widget_classes: str = "",
    ):
        """Render a config port — no pin, indented symmetrically to align with inlet/outlet labels."""
        indent = max(0, self.PIN_GUTTER + self.CONTENT_GAP)
        with (
            ui.element("div")
            .classes("compact-fields")
            .style(
                f"display: flex; flex-direction: column; width: 100%; "
                f"padding-left: {indent}px; padding-right: {indent}px;"
            )
        ) as config_row:
```

Replace with:

```python
    def _render_config(
        self,
        port,
        wrapper: NodeWrapper,
        widget_classes: str = "",
        depth: int = 0,
    ):
        """Render a config port — no pin, indented symmetrically to align with inlet/outlet labels.

        Args:
            depth: Fold nesting level, added to the left indent.
        """
        right_indent = max(0, self.PIN_GUTTER + self.CONTENT_GAP)
        left_indent = self._config_indent(depth)
        with (
            ui.element("div")
            .classes("compact-fields")
            .style(
                f"display: flex; flex-direction: column; width: 100%; "
                f"padding-left: {left_indent}px; padding-right: {right_indent}px;"
            )
        ) as config_row:
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/skin/test_port_row_depth_indent.py -v`
Expected: PASS (11 tests)

- [x] **Step 5: Commit**

```bash
git add barn/haybale-studio/haybale_studio/skins/node_skin.py tests/ui/skin/test_port_row_depth_indent.py
git commit -m "feat(skin): inset a config row by fold depth

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Stop indenting whole rows in `StackedNodeSkin`

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/skins/stacked_skin.py:224-324` (`_render_port_hierarchy`, `_render_group`)
- Test: `tests/ui/skin/test_port_row_depth_indent.py`

**Interfaces:**
- Consumes: `render_port(..., depth=)` from Task 1.
- Produces: `StackedNodeSkin._render_group(self, group_port, all_ports, wrapper, port_type, layout=None, depth=0)`.

This is the change that fixes the existing bug: `_render_group` currently wraps
its children in `ui.column().classes("w-full pl-2 ml-1 gap-1")`, insetting the
pin column along with everything else.

- [x] **Step 1: Write the failing test**

Append to `tests/ui/skin/test_port_row_depth_indent.py`:

```python
def test_group_container_does_not_indent_the_row() -> None:
    """The group container must not carry row-level padding/margin classes.

    `pl-2 ml-1` there insets the pin column too, moving a nested pin off the
    card border once per level.
    """
    import inspect

    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    source = inspect.getsource(StackedNodeSkin._render_group)
    assert "pl-2" not in source
    assert "ml-1" not in source


def test_render_group_threads_depth() -> None:
    import inspect

    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    assert "depth" in inspect.signature(StackedNodeSkin._render_group).parameters
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/skin/test_port_row_depth_indent.py::test_group_container_does_not_indent_the_row -v`
Expected: FAIL — `assert "pl-2" not in source`

- [x] **Step 3: Remove row indentation and thread `depth`**

In `stacked_skin.py`, change `_render_port_hierarchy` (line 224 — there is no
`_render_ports`) to pass a depth of 0 at top level.
The existing call is:

```python
            # Render based on port type
            if port.is_group:
                self._render_group(port, ports, wrapper, port_type, layout)
            else:
                self.render_port(
                    port,
                    wrapper,
                    widget_classes="widget-container zoom-pan-lod2",
                    layout=layout,
                )
```

Replace with:

```python
            # Render based on port type
            if port.is_group:
                self._render_group(port, ports, wrapper, port_type, layout, depth=0)
            else:
                self.render_port(
                    port,
                    wrapper,
                    widget_classes="widget-container zoom-pan-lod2",
                    layout=layout,
                    depth=0,
                )
```

Change `_render_group`'s signature to take `depth`:

```python
    def _render_group(
        self,
        group_port: DataPort,
        all_ports: List[DataPort],
        wrapper: NodeWrapper,
        port_type: PortType,
        layout: LayoutDirection | None = None,
        depth: int = 0,
    ):
```

Add to its docstring, replacing the "Indentation for visual hierarchy" bullet:

```
        - Children indented via their own content column, never the container
```

The same docstring's toggle paragraph (`stacked_skin.py:283-284`) says a group
"renders as its (still-indented) children" — still true, but the indentation now
lives on each row's content column. Change that parenthetical to
"(still-indented, via each row's content column)".

And add to its `Args:` block:

```
            depth: This group's own nesting level. Children render at
                ``depth + 1``.
```

Replace the container line. The existing line is:

```python
        with ui.column().classes("w-full pl-2 ml-1 gap-1"):
```

Replace with:

```python
        # No padding/margin here: a container inset moves the pin column too,
        # taking a nested pin off the card border. Depth reaches the row's
        # CONTENT column instead, via render_port(depth=...).
        with ui.column().classes("w-full gap-1"):
```

Then replace the child loop so depth increments:

```python
                for child_port in sorted(children, key=lambda p: p.order):
                    # Recursively handle nested groups
                    if child_port.is_group:
                        self._render_group(
                            child_port, all_ports, wrapper, port_type, layout, depth=depth + 1
                        )
                    else:
                        self.render_port(
                            child_port,
                            wrapper,
                            widget_classes="widget-container zoom-pan-lod2",
                            layout=layout,
                            depth=depth + 1,
                        )
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/skin/test_port_row_depth_indent.py -v`
Expected: PASS (13 tests)

- [x] **Step 5: Run the full skin suite**

Run: `uv run pytest tests/ui/skin/ -q`
Expected: all pass.

- [x] **Step 6: Lint, format and type-check**

```sh
uv run ruff check barn/haybale-studio/haybale_studio/skins/ tests/ui/skin/
uv run ruff format --check barn/haybale-studio/haybale_studio/skins/ tests/ui/skin/
uv run mypy barn/haybale-studio/haybale_studio/skins/
```

Expected: clean. If `ruff format --check` reports drift, run
`uv run ruff format barn/haybale-studio/haybale_studio/skins/ tests/ui/skin/` and re-commit.

- [x] **Step 7: Commit**

```bash
git add barn/haybale-studio/haybale_studio/skins/stacked_skin.py tests/ui/skin/test_port_row_depth_indent.py
git commit -m "fix(skin): a nested port's pin no longer insets from the card border

_render_group indented the whole row with pl-2/ml-1, including the pin
column, while render_pin offsets from card_padding — so a grouped pin sat
~12px inside the border, once per level. Depth now reaches the content
column only.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Browser verification and insight note

**Files:**
- Create: `.insights/project_pin_offset_vs_row_indent.md`
- Modify: `CLAUDE.md` — add one line to the "Architecture traps" list (heading is exactly `### Architecture traps`, CLAUDE.md:138)

**Interfaces:**
- Consumes: the behaviour from Tasks 1-3.
- Produces: nothing code-facing.

- [x] **Step 1: Verify in the real app**

```sh
uv run haywire
```

Drop the `Group And Sections` node (menu: `testing/rendering`). Confirm:
1. The group's child port pin sits on the card border, flush with ungrouped pins above/below it.
2. The child's label and widget are indented relative to ungrouped rows.
3. Dragging an edge to the nested pin connects normally.

- [x] **Step 2: Write the insight file**

Create `.insights/project_pin_offset_vs_row_indent.md`:

```markdown
# A port row's indentation must not touch its pin column

A pin is placed by `render_pin` with a negative CSS offset:

    offset_px = card_padding + pin_gutter // 2 + pin_protrusion

`card_padding` is the padding on the axis the pin crosses — the skin picks it
(`node_skin.py:576`: `CARD_V_PADDING if layout.is_vertical else CARD_H_PADDING`).

That arithmetic assumes **the pin's row begins at the card edge**. Any
indentation applied to the row as a whole falsifies it, and the pin ends up
inset from the card border by exactly the indent — silently, because the edge
layer reads pin positions with `getBoundingClientRect()` and simply follows the
pin wherever it landed. Edges keep meeting their pins; the pins are just in the
wrong place.

`StackedNodeSkin._render_group` used to do this with `pl-2 ml-1`, so every grouped
port's pin sat ~12px inside the border, and nesting compounded it per level.

**The rule:** a port row is a two-column grid (`{PIN_GUTTER}px 1fr`). Depth
insets the CONTENT column — which holds both the label and the widget — and
never the pin column. `NodeSkin._content_inset(depth)` is the one place that
computes it; `_config_indent(depth)` is its pinless counterpart.

Symptom of getting it wrong: pins drift inward from the card border the deeper a
port is nested, while edges still connect correctly. `render_pin` is not the bug
— its precondition was broken upstream.
```

- [x] **Step 3: Add the CLAUDE.md entry**

In `CLAUDE.md`, under "### Architecture traps", add:

```markdown
- [project_pin_offset_vs_row_indent.md](.insights/project_pin_offset_vs_row_indent.md) — a pin's negative offset assumes its row starts at the card edge, so indenting a whole row insets the pin from the border (silently — edges follow via `getBoundingClientRect`). Depth insets the row's CONTENT column only.
```

- [x] **Step 4: Commit**

```bash
git add .insights/project_pin_offset_vs_row_indent.md CLAUDE.md
git commit -m "docs: record the pin-offset vs row-indent trap

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Done When

- [x] `uv run pytest tests/ui/skin/ -q` passes.
- [x] `uv run pytest -m "not browser and not perf" -q` passes (exit 0).
- [x] `uv run ruff check .` and `uv run ruff format --check .` clean.
- [x] `uv run mypy` over the `CLAUDE.md` package list clean.
- [x] A grouped port's pin is visually flush with an ungrouped port's pin in the running app.

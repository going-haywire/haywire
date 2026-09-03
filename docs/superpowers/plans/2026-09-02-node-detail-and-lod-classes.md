# Node Detail and LOD Classes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `NodeDetail` from a Python construction gate into a 5-rank, CSS-driven visibility ladder (`PINS < PINS_ALL < WIDGETS < LABELS < FULL`), stop suppressing hidden widgets' server→view traffic while they're CSS-hidden, and retire the LOD system's `display:none` zoom-crossing rules while keeping its `data-lod-level` attribute as a dormant hook.

**Architecture:** Mirrors the existing `locked` pattern end-to-end: `UINode` stamps a resolved value onto the node's `[data-node-id]` container as a `data-node-props-detail` attribute; `canvas.vue` reacts with descendant-combinator `display:none` rules keyed off that attribute; skins add one `.hw-detail-*` class per element instead of consulting `NodeVisibility.label`/`.widget`/`.diagnostics` as booleans that gate construction. `NodeVisibility` keeps its existing shape but its three boolean properties become "which classes to add" rather than "build or don't build." A first manual gate measurement (Task 1) decides whether Tasks 2 onward proceed at all — this plan assumes the gate comes back fast per the design session; if it comes back slow, stop after Task 1 and follow the "Fallback: gate is slow" section instead.

**Tech Stack:** Python (NiceGUI backend), Vue 2 SFCs (`canvas.vue`, `pan.vue`), pytest.

## Global Constraints

- No back-compat shim for old saved-graph `detail` values (`"compact"`/`"standard"`) — breaking change, confirmed by design session. `NodeDetail.coerce()`'s existing blind degrade-to-`FULL` for any unrecognized string stays untouched, no remap table.
- `Node collapse` (`props.collapsed`) is NOT touched by this plan — stays a boolean, two-tier (graph < node), construction-gated axis exactly as ADR 0032 defined it. Only `NodeDetail` changes shape.
- Scope boundary unchanged (ADR 0032 decision 9): Ports panel, properties editor, node inspector, Farmhand tools ignore both axes — nothing in this plan touches them.
- `ruff check .`, `ruff format --check .`, and `mypy` on the touched core paths must be clean before any task is considered done, per this repo's CLAUDE.md.
- Run the narrowest relevant pytest tier while iterating (`uv run pytest tests/path/to/file.py`); run `uv run pytest -m "not browser and not perf"` once at the end.

---

## Task 1: Gate measurement — decide whether this plan proceeds

**Files:** none (manual measurement only).

**Interfaces:**
- Consumes: `perf/detail-via-css` branch (already exists, has the working probe CSS rule), `debug_overlay.vue`'s `record`/`sweep` tooling (already landed on `perf/flatten-3d-merge`).
- Produces: a go/no-go decision gating every later task in this plan.

- [ ] **Step 1: Check out the probe branch and start the studio**

```bash
git worktree add /tmp/gate-check perf/detail-via-css
cd /tmp/gate-check
uv run haywire
```

- [ ] **Step 2: Open the 200-node reference graph at FULL detail, LOD off**

Load `graphs/10x200nodes.haywire`. Confirm every node is at `NodeDetail.FULL` (the default) and collapse is off. Disable LOD via the debug overlay's toggle if it defaults on.

- [ ] **Step 3: Click-select a single node and observe latency**

Use the debug overlay's `record 5s` to capture a window that starts just before the click. Click one node once. Note the frame-time / stall behavior during the selection (this is Axis-B: NiceGUI's whole-tree `renderRecursively` walk, not a per-frame pan cost — Decision A's earlier pan matrix does not cover this).

- [ ] **Step 4: Record the verdict**

- **Fast** (selection feels immediate, no visible multi-second freeze) → proceed to Task 2.
- **Slow** (visible multi-second lag/freeze on selection) → **stop here.** Do not proceed past this task. Instead:
  1. Revert nothing (no code has changed yet).
  2. Delete the four probe branches per the housekeeping step in Task 10 (still applicable — they're superseded either way).
  3. Update `internals/handoff/node-detail-and-lod-classes.md` to record "Decision A: construction gating confirmed necessary, ADR 0032 stands unchanged. Gate measurement on <date> showed selection latency regresses under a CSS-filtered FULL graph." Session ends; do not run further tasks in this plan.

- [ ] **Step 5: Clean up the worktree**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
git worktree remove /tmp/gate-check
```

---

## Task 2: `NodeDetail` enum — 5 ranks, new names, no migration shim

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/enums.py:170-239`
- Test: `tests/core/test_node/test_node_detail_collapse_tiers.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `NodeDetail` StrEnum with members `PINS = "pins"`, `PINS_ALL = "pins_all"`, `WIDGETS = "widgets"`, `LABELS = "labels"`, `FULL = "full"`, ranked in that order (`PINS` lowest, `FULL` highest). `.rank`, `.label`, `.includes()`, `.coerce()` keep their existing signatures. `coerce()` behavior is UNCHANGED (any unrecognized string, including the old `"compact"`/`"standard"`, degrades to `FULL`).

- [ ] **Step 1: Write the failing tests**

Replace the enum-shape assertions in `tests/core/test_node/test_node_detail_collapse_tiers.py` (the `COMPACT`/`STANDARD`/`FULL` constants at the top and `TestNodeDetailEnum`) with the 5-rank version:

```python
# Replace lines 18-20:
PINS = NodeDetail.PINS.value
PINS_ALL = NodeDetail.PINS_ALL.value
WIDGETS = NodeDetail.WIDGETS.value
LABELS = NodeDetail.LABELS.value
FULL = NodeDetail.FULL.value
```

```python
@pytest.mark.unit
class TestNodeDetailEnum:
    def test_ranks_are_cumulative_and_ordered(self):
        assert (
            NodeDetail.PINS.rank
            < NodeDetail.PINS_ALL.rank
            < NodeDetail.WIDGETS.rank
            < NodeDetail.LABELS.rank
            < NodeDetail.FULL.rank
        )

    def test_includes_is_reflexive_and_directional(self):
        assert NodeDetail.WIDGETS.includes(NodeDetail.WIDGETS)
        assert NodeDetail.FULL.includes(NodeDetail.PINS)
        assert not NodeDetail.PINS.includes(NodeDetail.WIDGETS)

    def test_wire_value_is_the_string(self):
        """StrEnum, not IntEnum: saved graphs hold names, so adding a rank
        later renumbers nothing. See ADR 0032."""
        assert NodeDetail.FULL == "full"
        assert isinstance(NodeDetail.FULL, str)

    @pytest.mark.parametrize("bad", ["sideways", "", None, 7, object()])
    def test_coerce_degrades_upward_to_full(self, bad):
        """Degrading UP is deliberate: a card drawing too much costs
        performance, one drawing too little looks broken."""
        assert NodeDetail.coerce(bad) is NodeDetail.FULL

    @pytest.mark.parametrize("old_value", ["compact", "standard"])
    def test_pre_5rank_saved_values_degrade_to_full(self, old_value):
        """Breaking change, no migration shim (design session, 2026-09-02):
        an old 3-rank graph's detail value is simply unrecognised now."""
        assert NodeDetail.coerce(old_value) is NodeDetail.FULL

    def test_coerce_passes_through_members_and_valid_strings(self):
        assert NodeDetail.coerce(NodeDetail.PINS) is NodeDetail.PINS
        assert NodeDetail.coerce("widgets") is NodeDetail.WIDGETS

    def test_every_member_has_a_label(self):
        """The label feeds the CHOICES widget — a missing one is a KeyError in
        a settings panel, not at import."""
        assert all(d.label for d in NodeDetail)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/core/test_node/test_node_detail_collapse_tiers.py::TestNodeDetailEnum -v
```
Expected: FAIL — `AttributeError: PINS` (member doesn't exist yet).

- [ ] **Step 3: Rewrite the enum**

In `packages/haywire-core/src/haywire/core/types/enums.py`, replace lines 170-239:

```python
class NodeDetail(StrEnum):
    """
    How much of an uncollapsed node card is drawn. See ADR 0032, superseded
    in part (2026-09) by the CSS-filter redesign — see the "Superseded"
    section at the end of that ADR.

    Cumulative: each rank draws everything the rank below it draws, plus its
    own. Resolved per node through the framework < graph < node chain
    (``node.props.detail``), so one graph may legitimately mix densities.

    - PINS: linked ports only — the same visual floor Node collapse folds
      down to, but drawn on a full-chrome (unfolded) card
    - PINS_ALL: + unlinked ports
    - WIDGETS: + inline port widgets
    - LABELS: + port labels
    - FULL: + inline diagnostics detail

    Labels sit *above* widgets deliberately: pin and config-row tooltips
    already carry identification, and a label is one element per port against
    a widget's whole subtree — so cheap-first makes each step of the ladder
    buy something.

    A **CSS filter**, not a construction gate: every element at every rank is
    BUILT. What differs per rank is a ``.hw-detail-*`` class added to each
    element (see ``haywire.ui.skin.visibility.NodeVisibility``), matched by a
    ``display: none`` rule keyed off the ``data-node-props-detail`` attribute
    ``UINode`` stamps on the node's container. This is deliberately the same
    mechanism the zoom-driven LOD system (ADR 0006) uses for its own classes
    — the two remain conceptually separate (LOD decides what is painted of
    what exists at THIS frame; NodeDetail decides what a rank includes) even
    though they now share a technique. Because nothing is omitted from
    construction, ``detail`` is NOT in ``NodeProperties.REDRAW_FIELDS`` — a
    rank change is a class-attribute flip, not a card rebuild.

    A ``StrEnum`` with an explicit :attr:`rank`, exactly like ``AccessTier``
    and for the same reason: the wire values stay strings, so adding a rank
    later renumbers nothing in saved graphs. A density scale is precisely the
    kind that grows a member.

    **Breaking change (2026-09):** the old 3-member enum's wire values
    (``"compact"``, ``"standard"``) are gone. No migration shim — an old
    saved graph's value is simply unrecognised now and :meth:`coerce`
    degrades it to ``FULL`` like any other unrecognised string, per this
    repo's pre-external-install-base state at the time of the change.
    """

    PINS = "pins"
    PINS_ALL = "pins_all"
    WIDGETS = "widgets"
    LABELS = "labels"
    FULL = "full"

    @property
    def label(self) -> str:
        """Human-readable name for settings widgets."""
        return _NODE_DETAIL_LABELS[self]

    @property
    def rank(self) -> int:
        """Position in the cumulative order — higher draws more."""
        return _NODE_DETAIL_RANKS[self]

    def includes(self, other: "NodeDetail") -> bool:
        """True when drawing at this rank also draws everything *other* does."""
        return self.rank >= other.rank

    @classmethod
    def coerce(cls, value: object) -> "NodeDetail":
        """Resolve a stored value, falling back to FULL rather than raising.

        Settings store the enum's ``str`` value (CHOICES is a STRING subtype),
        and this runs on the render path — an unrecognised or stale string must
        degrade to the most legible card, never take one down. Degrading
        *upward* is deliberate: a node that draws too much is a performance
        cost, one that draws too little looks broken. Unchanged by the 2026-09
        rank-count change: old ``"compact"``/``"standard"`` values are simply
        unrecognised strings now and take this same path.
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(value)
            except ValueError:
                return cls.FULL
        return cls.FULL


_NODE_DETAIL_LABELS: dict[NodeDetail, str] = {
    NodeDetail.PINS: "Pins — linked ports only",
    NodeDetail.PINS_ALL: "All Pins — every port",
    NodeDetail.WIDGETS: "Widgets — pins and inline widgets",
    NodeDetail.LABELS: "Labels — widgets and port labels",
    NodeDetail.FULL: "Full — labels and diagnostics detail",
}

_NODE_DETAIL_RANKS: dict[NodeDetail, int] = {
    NodeDetail.PINS: 0,
    NodeDetail.PINS_ALL: 1,
    NodeDetail.WIDGETS: 2,
    NodeDetail.LABELS: 3,
    NodeDetail.FULL: 4,
}
```

Note: check whether `_NODE_DETAIL_RANKS` already exists elsewhere in the file (the original only showed `_NODE_DETAIL_LABELS` in the excerpt read during design) — if a `_NODE_DETAIL_RANKS` dict already exists nearby, update its values in place instead of duplicating it.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/core/test_node/test_node_detail_collapse_tiers.py::TestNodeDetailEnum -v
```
Expected: PASS.

- [ ] **Step 5: Fix the rest of `test_node_detail_collapse_tiers.py`**

The `TestNodeDetailGraphTier` class in the same file references `COMPACT`/`STANDARD`/`FULL` module constants throughout (now `PINS`/`WIDGETS`/`FULL` after Step 1's rename). Update every reference:
- `test_defaults_to_full`: unchanged in shape, still asserts `FULL`.
- `test_unset_node_tracks_graph_default`: replace `COMPACT` with `PINS`.
- `test_node_override_wins_and_resets_fall_one_tier`: replace `COMPACT`/`STANDARD`/`FULL` with `PINS`/`WIDGETS`/`FULL` (three-tier chain still needs 3 distinct values, any 3 of the 5 ranks work — use `PINS` (framework), `WIDGETS` (graph), `FULL` (node) to keep the test's shape).
- `test_round_trip_preserves_all_three_tiers`: replace `STANDARD`/`COMPACT` with `WIDGETS`/`PINS`.
- `test_pre_feature_graph_without_detail_loads`: unchanged in shape (still asserts default `FULL`).
- `test_graph_tier_change_reaches_a_tracking_node`: replace `COMPACT` with `PINS`.

`TestBothAxesRedraw.test_axis_is_a_redraw_field` is parametrized `["collapsed", "detail"]` — this now FAILS by design once Task 3 removes `detail` from `REDRAW_FIELDS`. Leave it failing for now; Task 3 fixes it (do not fix it here, so Task 3's own red→green cycle is real).

- [ ] **Step 6: Run the whole file**

```bash
uv run pytest tests/core/test_node/test_node_detail_collapse_tiers.py -v
```
Expected: everything green except `test_axis_is_a_redraw_field[detail]`, which fails until Task 3.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/enums.py tests/core/test_node/test_node_detail_collapse_tiers.py
git commit -m "feat(node-detail): 5-rank NodeDetail ladder (PINS/PINS_ALL/WIDGETS/LABELS/FULL)

Breaking change: old 3-rank wire values (compact/standard) are no longer
recognised and degrade to FULL via the existing coerce() fallback — no
migration shim, per design session (no external install base to protect).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: `NodeVisibility` — CSS classes instead of construction booleans

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/skin/visibility.py`
- Modify: `packages/haywire-core/src/haywire/core/node/properties.py` (remove `"detail"` from `REDRAW_FIELDS`)
- Test: `tests/ui/skin/test_node_visibility.py`
- Test: `tests/core/test_node/test_node_detail_collapse_tiers.py` (`TestBothAxesRedraw`)

**Interfaces:**
- Consumes: `NodeDetail` from Task 2.
- Produces: `NodeVisibility` keeps `collapsed: bool` and `detail: NodeDetail` fields. New properties: `pins_all: bool`, `widget: bool`, `label: bool`, `diagnostics: bool` (all now describe "does this rank's ladder include this content", used to decide which CSS class to add — NOT whether to build). `ports()` UNCHANGED (still the construction-time port filter; NodeDetail no longer affects which ports exist, per ADR 0032 decision — this doesn't change). New: `detail_class` property returning the single `.hw-detail-*` string for the resolved rank's floor (see Task 4 for how it's consumed).

- [ ] **Step 1: Write the failing tests**

Update `tests/ui/skin/test_node_visibility.py`'s `TestRankMapping` class:

```python
class TestRankMapping:
    """The truth table. Read it as the spec."""

    @pytest.mark.parametrize(
        ("detail", "pins_all", "widget", "label", "diagnostics"),
        [
            (NodeDetail.PINS, False, False, False, False),
            (NodeDetail.PINS_ALL, True, False, False, False),
            (NodeDetail.WIDGETS, True, True, False, False),
            (NodeDetail.LABELS, True, True, True, False),
            (NodeDetail.FULL, True, True, True, True),
        ],
    )
    def test_unfolded_ranks(self, detail, pins_all, widget, label, diagnostics):
        show = _show(detail)
        assert show.pins_all is pins_all
        assert show.widget is widget
        assert show.label is label
        assert show.diagnostics is diagnostics

    @pytest.mark.parametrize("detail", list(NodeDetail))
    def test_folding_beats_every_rank(self, detail):
        """A folded card draws none of it, whatever the detail says."""
        show = _show(detail, collapsed=True)
        assert not show.pins_all
        assert not show.widget
        assert not show.label
        assert not show.diagnostics

    def test_labels_sit_above_widgets(self):
        """Deliberate ordering (ADR 0032): tooltips already identify a port, and
        a label is one element per port against a widget's whole subtree — so
        WIDGETS buys widgets and LABELS adds the cheaper half."""
        assert _show(NodeDetail.WIDGETS).widget
        assert not _show(NodeDetail.WIDGETS).label

    def test_predicates_are_properties_not_methods(self):
        """`if show.label:` on a method is silently always true — this object
        exists to make that class of bug impossible."""
        for name in ("pins_all", "widget", "label", "diagnostics"):
            assert isinstance(getattr(NodeVisibility, name), property)

    def test_is_a_frozen_value(self):
        """Built inside a SkinFactory-cached skin shared across every node in
        every open graph, so it must carry no mutable per-node state."""
        show = _show(NodeDetail.FULL)
        with pytest.raises(FrozenInstanceError):
            show.collapsed = True  # type: ignore[misc]
```

Also update `_show()`'s default argument if it references old names (it takes `detail`/`collapsed` positionally, unaffected).

Update `TestPortFilter` — replace every `NodeDetail.COMPACT`/`.FULL` reference with `NodeDetail.PINS`/`.FULL` (the FULL ones are unchanged; only COMPACT references need renaming to PINS). `for detail in NodeDetail:` loops are unaffected — they now iterate 5 members instead of 3.

Update `TestResolver`:
```python
def test_reads_both_axes(self):
    show = resolve_node_visibility(_fake_wrapper(_FakeProps(True, "pins")))
    assert show.collapsed is True
    assert show.detail is NodeDetail.PINS
```
(`"compact"` → `"pins"`.) `test_corrupt_detail_degrades_to_full` and `test_unreadable_props_never_raise` are unaffected — still assert `NodeDetail.FULL`.

Update `TestAgainstRealNodes.test_tier_writes_reach_the_resolver`: replace `NodeDetail.COMPACT`/`NodeDetail.STANDARD` with `NodeDetail.PINS`/`NodeDetail.WIDGETS`.

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/ui/skin/test_node_visibility.py -v
```
Expected: FAIL — `AttributeError: 'NodeVisibility' object has no attribute 'pins_all'`.

- [ ] **Step 3: Rewrite `NodeVisibility`**

In `packages/haywire-core/src/haywire/ui/skin/visibility.py`, replace the "What to draw" block (the `label`/`widget`/`diagnostics` properties, lines 62-86 in the pre-edit file):

```python
    # ------------------------------------------------------------------
    # What to draw — now CSS-class membership, not construction booleans.
    #
    # Every element below is ALWAYS BUILT. These properties answer "does the
    # resolved rank's ladder include this content", which a caller uses to
    # decide whether to add the matching `.hw-detail-*` class (see
    # `NodeSkin` callers and canvas.vue's `[data-node-props-detail]` rules).
    # Folding still means "draw none of it" — collapse is unchanged and
    # still gates CONSTRUCTION (a folded card really does not build these
    # elements), so these properties stay False while collapsed even though
    # nothing here is a construction gate for the unfolded case.
    # ------------------------------------------------------------------

    @property
    def pins_all(self) -> bool:
        """Unlinked ports, in addition to linked ones. PINS_ALL and above."""
        return not self.collapsed and self.detail.includes(NodeDetail.PINS_ALL)

    @property
    def widget(self) -> bool:
        """Inline port widgets, and the group toggles that are themselves
        widgets. WIDGETS and above."""
        return not self.collapsed and self.detail.includes(NodeDetail.WIDGETS)

    @property
    def label(self) -> bool:
        """Port labels. LABELS and above — pin and config-row tooltips
        already carry identification, and a label is one element per port."""
        return not self.collapsed and self.detail.includes(NodeDetail.LABELS)

    @property
    def diagnostics(self) -> bool:
        """Inline diagnostics detail — the alternate-versions notice and the
        eagerly-built error menu body. FULL only.

        NOT the badge: a badge is drawn at every rank, folded included, because
        a node nobody can see is broken is worse than a slow one.
        """
        return not self.collapsed and self.detail.includes(NodeDetail.FULL)
```

Note `ports()` (the method below this block) is UNCHANGED — leave it exactly as-is. NodeDetail still doesn't affect which ports exist, only what's drawn per port, and that reasoning didn't change.

- [ ] **Step 4: Remove `detail` from `REDRAW_FIELDS`**

Read `packages/haywire-core/src/haywire/core/node/properties.py:32-40` first (confirm current shape), then remove the `"detail",` line:

```python
    REDRAW_FIELDS: tuple[str, ...] = (
        "collapsed",
        "locked",
        "skin",
        "layout_direction",
        "comment",
        "label",
    )
```

Update the docstring immediately below it (originally documents why each field triggers a redraw) — add a note that `detail` used to be here and now isn't, because it stopped being a construction gate. Read the existing docstring text before editing so the addition matches its style.

- [ ] **Step 5: Fix `TestBothAxesRedraw` in `test_node_detail_collapse_tiers.py`**

```python
@pytest.mark.unit
class TestBothAxesRedraw:
    def test_collapse_is_a_redraw_field(self):
        """Collapse is still a CONSTRUCTION gate, so a change must rebuild the
        card. Without the entry no tier change ever reaches the canvas."""
        from haywire.core.node.properties import NodeProperties

        assert "collapsed" in NodeProperties.REDRAW_FIELDS

    def test_detail_is_not_a_redraw_field(self):
        """NodeDetail stopped being a construction gate (2026-09 CSS-filter
        redesign) — a rank change is a class-attribute flip handled by
        UINode._apply_detail_attr, not a card rebuild. If this ever needs to
        change back, it is a deliberate reversal, not a bug fix."""
        from haywire.core.node.properties import NodeProperties

        assert "detail" not in NodeProperties.REDRAW_FIELDS
```

(Replaces the old parametrized `test_axis_is_a_redraw_field`.)

- [ ] **Step 6: Run the full set**

```bash
uv run pytest tests/ui/skin/test_node_visibility.py tests/core/test_node/test_node_detail_collapse_tiers.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/skin/visibility.py packages/haywire-core/src/haywire/core/node/properties.py tests/ui/skin/test_node_visibility.py tests/core/test_node/test_node_detail_collapse_tiers.py
git commit -m "feat(node-detail): NodeVisibility exposes CSS-class membership, not construction gates

detail leaves REDRAW_FIELDS — a rank change no longer rebuilds the card.
collapsed stays: it is still a real construction gate.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: `UINode` stamps `data-node-props-detail`

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py`
- Test: `tests/ui/graph_canvas/test_node_size_apply.py` (check for collisions), new test file `tests/ui/graph_canvas/test_node_detail_attr.py`

**Interfaces:**
- Consumes: `wrapper.node.props.detail` (already exists), the `_apply_locked_attr` pattern at `ui_node.py:252-269` as the template.
- Produces: `UINode._apply_detail_attr()` method; container carries `data-node-props-detail="<rank value>"` always (unlike `locked`, this is never absent — every node has SOME rank, whereas `locked` is presence-tested).

- [ ] **Step 1: Write the failing test**

Create `tests/ui/graph_canvas/test_node_detail_attr.py`:

```python
"""UINode stamps data-node-props-detail on the container — the mechanism
canvas.vue's [data-node-props-detail] CSS rules key off. Mirrors
_apply_locked_attr's existing test coverage pattern."""

import pytest

from haywire.core.types import NodeDetail

pytestmark = pytest.mark.unit


def _add_node(graph_obj):
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return graph_obj.create_node_wrapper(TestPrintNode.class_identity.registry_key, position=(100, 100))


@pytest.mark.integration
class TestDetailAttrStamp:
    def test_container_carries_the_resolved_rank(self, graph_with_library_system):
        from haybale_graph_editor.editors.graph_canvas.ui_node import UINode
        from nicegui import ui

        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)

        with ui.column() as container:
            node = UINode(container=container, wrapper=wrapper, factory=_fake_factory())

        assert container._props.get("data-node-props-detail") == NodeDetail.FULL.value

    def test_attr_updates_when_detail_changes(self, graph_with_library_system):
        from haybale_graph_editor.editors.graph_canvas.ui_node import UINode
        from nicegui import ui

        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)

        with ui.column() as container:
            node = UINode(container=container, wrapper=wrapper, factory=_fake_factory())

        wrapper.node.props.detail = NodeDetail.PINS.value
        assert container._props.get("data-node-props-detail") == NodeDetail.PINS.value
```

This test needs a `_fake_factory()` helper — check `tests/ui/graph_canvas/test_node_size_apply.py` first for the existing fixture/fake used to construct a bare `UINode` in tests, and reuse it rather than inventing a new one. If that file constructs `UINode` differently (e.g. via a fixture named `factory` or `skin_factory`), match its exact pattern instead of the sketch above.

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/ui/graph_canvas/test_node_detail_attr.py -v
```
Expected: FAIL — attribute not present (KeyError/None).

- [ ] **Step 3: Add `_apply_detail_attr` to `UINode`**

In `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py`, add a subscription alongside the existing `locked` one in `_subscribe_slot_fields` (around line 250):

```python
        # `detail` rides its own handler, same as `locked`: it stamps the
        # CONTAINER (not the slot), because canvas.vue's [data-node-props-detail]
        # rules key off it the same way [data-node-props-locked] does — and
        # custom attributes do not inherit down to descendants the way CSS
        # vars do.
        props.subscribe_field("detail", lambda _v, _o: self._apply_detail_attr())
```

And add the method itself, mirroring `_apply_locked_attr` (place it directly after that method, around line 269):

```python
    def _apply_detail_attr(self) -> None:
        """Stamp ``data-node-props-detail`` on the container for canvas.vue to read.

        Unlike ``locked`` (presence-tested), this is ALWAYS present — every
        node resolves to some ``NodeDetail`` rank, so the client never has to
        distinguish "absent" from "at the floor rank". Value is the resolved
        rank's wire string (``NodeDetail.coerce`` already degrades anything
        unreadable to ``FULL``), read once here rather than re-deriving the
        resolution logic client-side.

        The ``data-node-props-`` prefix is the convention for an attribute that
        mirrors a ``NodeProperties`` field — see the attribute index at the top
        of canvas.vue's ``<script>``; this entry was added there alongside this
        method.
        """
        from haywire.core.types import NodeDetail

        detail = NodeDetail.coerce(self.wrapper.node.props.detail)
        self.container._props["data-node-props-detail"] = detail.value
        self.container.update()
```

And call it once at construction time, alongside the existing `self._apply_locked_attr()` call in `__init__` (line 72):

```python
        self._apply_locked_attr()
        self._apply_detail_attr()
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run pytest tests/ui/graph_canvas/test_node_detail_attr.py -v
```
Expected: PASS.

- [ ] **Step 5: Update the attribute index comment block in `canvas.vue`**

Read `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue:55-88` first (the "DOM attributes this component reads" block), then add an entry matching the existing `…-locked` line's format:

```
 *     …-locked          props.locked — refuses drag pickup, hides the resize
 *                       gadget. On the [data-node-id] CONTAINER.
 *     …-detail          props.detail — the resolved NodeDetail rank
 *                       (ADR 0032). On the [data-node-id] CONTAINER. Always
 *                       present (unlike locked): every node resolves to a
 *                       rank. Read by the [data-node-props-detail] rules
 *                       this file defines further down.
```

- [ ] **Step 6: Run the wider graph_canvas test dir to catch collisions**

```bash
uv run pytest tests/ui/graph_canvas/ -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py packages/haywire-core/src/haywire/ui/components/graph/canvas.vue tests/ui/graph_canvas/test_node_detail_attr.py
git commit -m "feat(node-detail): stamp data-node-props-detail on the node container

Same pattern as _apply_locked_attr. canvas.vue's forthcoming
[data-node-props-detail] CSS rules (next commit) key off this.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: `canvas.vue` CSS — the `.hw-detail-*` display rules

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` (the "widget-container-sizing" block area, ~line 3540-3559)

**Interfaces:**
- Consumes: `data-node-props-detail` attribute (Task 4), `.hw-detail-pins_all`, `.hw-detail-widget`, `.hw-detail-label`, `.hw-detail-diagnostic` classes (Task 6 adds them to actual elements — this task only adds the CSS rules matching them).
- Produces: 4 `display: none` rule groups, one per non-floor rank, exactly mirroring the `[data-lod-level=...]` structure already in `pan.vue`.

- [ ] **Step 1: Add the CSS rules**

Read `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue:3540-3559` first (the existing "widget-container-sizing" comment, which currently documents the OLD construction-gate reasoning — this step's rules go directly after that block, and Step 2 rewrites the comment itself).

Insert after line 3559 (`/* --8<-- [end:widget-container-sizing] */`):

```css
/* --8<-- [start:node-detail-css-classes] */
/* NodeDetail (ADR 0032, 5-rank CSS-filter redesign, 2026-09) drives visibility
 * the same way LOD does (pan.vue): a resolved value is stamped as a DOM
 * attribute — data-node-props-detail, by UINode._apply_detail_attr — and CSS
 * hides whatever the rank excludes via descendant combinators. Every element
 * below is ALWAYS BUILT; nothing here is a construction gate. See
 * haywire/ui/skin/visibility.py for the rank -> class mapping this mirrors.
 *
 * Ranks, low to high: pins < pins_all < widgets < labels < full. Each rule
 * below hides what a rank does NOT yet include — so `pins` (the floor) hides
 * all four classes, and `full` hides none of them (no rule matches it).
 *
 * `display: none`, matching pan.vue's LOD rules and the perf/detail-via-css
 * probe: takes the elements out of layout and paint, not just opacity, which
 * is what the pan-performance measurement (decision A) actually tested. */
[data-node-props-detail="pins"] .hw-detail-pins_all,
[data-node-props-detail="pins"] .hw-detail-widget,
[data-node-props-detail="pins"] .hw-detail-label,
[data-node-props-detail="pins"] .hw-detail-diagnostic,
[data-node-props-detail="pins_all"] .hw-detail-widget,
[data-node-props-detail="pins_all"] .hw-detail-label,
[data-node-props-detail="pins_all"] .hw-detail-diagnostic,
[data-node-props-detail="widgets"] .hw-detail-label,
[data-node-props-detail="widgets"] .hw-detail-diagnostic,
[data-node-props-detail="labels"] .hw-detail-diagnostic {
    display: none;
}
/* --8<-- [end:node-detail-css-classes] */
```

- [ ] **Step 2: Rewrite the "widget-container-sizing" comment above it**

The existing comment (lines 3540-3554) documents the OLD construction-gate reasoning ("A widget that EXISTS is visible. Whether it exists is decided in Python..."). Read it, then replace with:

```css
/* --8<-- [start:widget-container-sizing] */
/* A widget's EXISTENCE no longer implies its visibility (2026-09): NodeDetail
 * is a CSS filter now (see node-detail-css-classes below), so a widget can
 * exist, be built, hold state and receive server pushes while CSS-hidden at
 * a low rank. This block is SIZE only — the max-height ceiling — and applies
 * whether or not the widget is currently shown.
 *
 * History: this used to be a reveal (opacity 0 / max-height 0 by default,
 * restored on .node-selected), then briefly a construction gate (every
 * widget was built only at WIDGETS+ and displayed unconditionally once
 * built). What survives verbatim through both changes is the SIZE contract:
 * the 200px default ceiling and the `overflow: hidden` that enforces it. */
[data-node-id] .widget-container {
    max-height: 200px !important;
    overflow: hidden !important;
}
/* --8<-- [end:widget-container-sizing] */
```

- [ ] **Step 3: Manual visual check (no automated test for pure CSS)**

Start the studio, open `graphs/10x200nodes.haywire`, select a node, and use the Detail submenu (right-click → Detail) to click through all 5 ranks. Confirm: PINS shows only linked pins; PINS_ALL adds unlinked pins; WIDGETS adds inline widgets; LABELS adds port labels; FULL adds the diagnostics notice (on a node with diagnostics, if any is available — otherwise confirm no error).

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/canvas.vue
git commit -m "feat(node-detail): CSS rules for the 5-rank .hw-detail-* ladder

Mirrors pan.vue's [data-lod-level] structure. Nothing here is built
conditionally — this only hides what a rank excludes.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: Skins — add `.hw-detail-*` classes, stop consulting booleans as construction gates

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/skins/node_skin.py`
- Modify: `barn/haybale-studio/haybale_studio/skins/stacked_skin.py`
- Test: `tests/ui/skin/test_node_visibility.py` (`TestSkinsHonourTheAxes` — verify still passes unmodified)
- Test: `tests/ui/skin/test_detail_render.py`

**Interfaces:**
- Consumes: `show.pins_all`, `show.widget`, `show.label`, `show.diagnostics` from Task 3 (now CSS-membership booleans, not construction gates).
- Produces: every port row and diagnostics element in `stacked_skin.py` always builds its widget/label/diagnostics content, with the appropriate `.hw-detail-*` class always added alongside `zoom-pan-lod2` where that already exists. `show.ports()` usage for the linked/unlinked split (PINS vs PINS_ALL) stays construction-time — unlinked ports still are not built at all when collapsed, but this is the EXISTING folded-card behavior (unchanged); the new PINS/PINS_ALL split for an UNFOLDED card is purely a CSS-class question (all ports are already built unfolded per `ports()`'s existing "unfolded defers to get_visible_ports" contract).

- [ ] **Step 1: Read `test_detail_render.py` in full to understand current coverage**

```bash
cat tests/ui/skin/test_detail_render.py
```

This file's exact current assertions were not captured during design — read it now before editing. It almost certainly asserts "at COMPACT, no widget element exists in the rendered card" (an existence check). Every such assertion needs to change to "the widget element exists AND carries `.hw-detail-widget`" (an existence-plus-class check). Do this rewrite as this step; there is no way to give exact diffs without having read the file, so treat this as: locate every `assert ... not in ...` / `assert ... is None` style existence check keyed on a `NodeDetail` rank, and convert it to a class-presence check using the pattern in Step 4 below.

- [ ] **Step 2: Write/update the failing tests**

Using whatever test harness `test_detail_render.py` already uses to render a card (read its fixtures first), add or update cases of this shape:

```python
def test_widget_element_exists_but_is_css_gated_at_pins(self, ...):
    """2026-09: NodeDetail stopped being a construction gate. The widget
    element exists at every rank now; only its CSS class changes."""
    card = render_card_at(detail=NodeDetail.PINS)
    widget_el = find_widget_element(card)
    assert widget_el is not None, "widget must still be BUILT at PINS"
    assert "hw-detail-widget" in widget_el.classes

def test_widget_visible_class_present_at_widgets_rank(self, ...):
    card = render_card_at(detail=NodeDetail.WIDGETS)
    widget_el = find_widget_element(card)
    assert "hw-detail-widget" in widget_el.classes
```

(Adjust `render_card_at`/`find_widget_element` to whatever helpers the existing file actually defines.)

- [ ] **Step 3: Run to verify failure**

```bash
uv run pytest tests/ui/skin/test_detail_render.py -v
```
Expected: FAIL (widget elements either don't exist yet at low ranks, or lack the new class).

- [ ] **Step 4: Update `stacked_skin.py`'s port-row rendering**

Read `barn/haybale-studio/haybale_studio/skins/stacked_skin.py` in full around lines 300-440 (the areas Grep found consulting `show.label`/`show.widget`/`show.diagnostics`) before editing — the exact current code was read during design but only in fragments; confirm the surrounding structure before changing it.

The pattern to apply throughout: wherever the code currently does

```python
if show.label:
    ui.label(port.label).classes("text-xs zoom-pan-lod2")
if show.widget and port.widget_key is not None and port.should_show_widget():
    ...  # build widget
```

change to: always build the label (drop the `if show.label:` construction gate), and always append `.hw-detail-label`:

```python
ui.label(port.label).classes("text-xs zoom-pan-lod2 hw-detail-label")
```

For the widget, the `port.widget_key is not None and port.should_show_widget()` conditions are NOT part of the NodeDetail gate — they're independent reasons a widget might not exist at all (no widget configured, or the port type opts out). Keep those; only drop `show.widget` from the condition, and add the class to whatever the widget's built container carries:

```python
if port.widget_key is not None and port.should_show_widget():
    self._render_config(
        port, wrapper,
        widget_classes="widget-container zoom-pan-lod2 hw-detail-widget",
        show=show,
    )
```

Find every one of the ~6 call sites Grep located (lines ~280, 287, 346-351, 435-437 in the original read) and apply the same transform: drop the `if show.X:` wrapper around construction, add `hw-detail-X` to the classes string. For the diagnostics badge/notice split (line 255: `if runtime_errors and show.diagnostics and wrapper._alternate_registry_keys:`), read the surrounding code carefully — ADR 0032 decision 6 says the BADGE draws at every rank (unaffected) but the inline notice body is `show.diagnostics`-gated. Apply the same transform: the notice body is always built, gains `hw-detail-diagnostic`, and the `show.diagnostics` boolean is dropped from the `if` (keep `runtime_errors and wrapper._alternate_registry_keys`, which are real existence conditions, not rank gates).

- [ ] **Step 5: Add the pins/pins_all split to `node_skin.py` or `stacked_skin.py`'s pin rendering**

Read the pin-rendering loop (wherever `show.ports(node)` is consumed in `stacked_skin.py`, since the folded-card port filter is untouched but the UNFOLDED port loop needs the new PINS vs PINS_ALL class). For each rendered pin, add `hw-detail-pins_all` to unlinked ports' classes (linked ports need no class — they're the floor, always shown):

```python
for port in show.ports(node):
    pin_classes = "connection-pin" if port.is_linked() else "connection-pin hw-detail-pins_all"
    ...
```

The exact call site/variable names depend on what Step 1's read of `stacked_skin.py` shows — match the existing pin-rendering code's actual variable names rather than the sketch above.

- [ ] **Step 6: Run to verify pass**

```bash
uv run pytest tests/ui/skin/test_detail_render.py tests/ui/skin/test_node_visibility.py -v
```
Expected: PASS. `TestSkinsHonourTheAxes` (unmodified) must still pass — it checks source text for `"show_of"` or `"NodeVisibility"`, both still present.

- [ ] **Step 7: Run the wider skin test dir**

```bash
uv run pytest tests/ui/skin/ -v
```
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add barn/haybale-studio/haybale_studio/skins/node_skin.py barn/haybale-studio/haybale_studio/skins/stacked_skin.py tests/ui/skin/test_detail_render.py
git commit -m "feat(node-detail): skins always build port content, tag it with .hw-detail-*

Widgets, labels and the diagnostics notice are constructed at every rank now;
only their CSS class (and canvas.vue's display:none rule) changes what's
shown. widget_key/should_show_widget existence checks are untouched — those
are real absence, not a rank gate.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: Suppress model→view push traffic for CSS-hidden widgets

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/widget/base.py`
- Test: new test file `tests/ui/widget/test_detail_gated_dispatch.py`

**Interfaces:**
- Consumes: `BaseWidget.render()`/`on_model_changed()`/`_model_dispatch_cb` (existing, `base.py:130-156`, `92-100`).
- Produces: `BaseWidget` gains an optional way to know whether it is currently CSS-hidden by NodeDetail, and `on_model_changed`'s default dispatch skips `binding.sync_to_view()` when hidden. This is a narrow, additive change — it must NOT change behavior for a widget that is always visible (STANDARD+/no NodeDetail awareness at all, e.g. widgets outside a node card).

- [ ] **Step 1: Decide the exact wiring — read `render()`'s call site first**

`BaseWidget` itself has no reference to `NodeVisibility` or the port's node — it only knows `self.port`. Check whether `WidgetModel`/`port` (the type hint on `BaseWidget.__init__`) exposes a way to reach the owning node's resolved `NodeVisibility`, or whether this needs to be threaded in from the skin at construction time.

```bash
grep -n "class WidgetModel" -A 30 packages/haywire-core/src/haywire/core/types/*.py
```

Read the result. If `WidgetModel` (or whatever `port` actually is at runtime — likely a `DataPort`) has a back-reference to its owning `NodeWrapper`, use that to call `resolve_node_visibility()` directly inside `on_model_changed`. If it does NOT, the skin must pass the resolved `show.widget` (or the whole `NodeVisibility`) into the widget at construction/render time — check how `_render_config`/widget construction in `stacked_skin.py` (from Task 6) currently builds a `BaseWidget` subclass instance, and thread a `visible: bool` or `node_visibility: NodeVisibility` param through if no back-reference exists.

- [ ] **Step 2: Write the failing test**

```python
"""A widget's model->view push is suppressed while it's CSS-hidden by
NodeDetail (design session, 2026-09): the DOM element exists (CSS filter,
not construction gate) but must not keep paying server->view traffic while
invisible."""

import pytest

pytestmark = pytest.mark.unit


class _FakePort:
    def __init__(self, value):
        self._value = value
        self.id = "p1"
        self.widget_config = {}

    def get_value(self):
        return self._value

    def set_value(self, v):
        self._value = v


class _RecordingWidget:
    """Minimal BaseWidget stand-in that records on_model_changed calls."""
    # Fill in using BaseWidget's actual constructor/hook shape from base.py,
    # once Step 1's wiring decision is made — this sketch names the behavior
    # to test, not the final fixture shape.


def test_dispatch_is_skipped_when_widget_is_detail_hidden():
    ...  # construct with visible=False (or whatever Step 1 settled on),
    ...  # fire a model change, assert on_model_changed was NOT called

def test_dispatch_fires_normally_when_widget_is_visible():
    ...  # construct with visible=True, fire a model change, assert it WAS called

def test_widgets_with_no_visibility_context_dispatch_normally():
    """A widget built outside a node card (e.g. a settings panel) has no
    NodeDetail concept at all — must default to always-dispatch, never
    silently drop updates."""
    ...
```

This test's exact fixture shape depends entirely on Step 1's wiring decision — write it concretely once that's settled, following whatever pattern `tests/ui/widget/_sync_fixtures.py` (referenced as an existing `bind()` test fixture in the codebase) already uses for constructing a bare widget in tests. Read that file first.

- [ ] **Step 3: Run to verify failure**

```bash
uv run pytest tests/ui/widget/test_detail_gated_dispatch.py -v
```
Expected: FAIL (suppression doesn't exist yet).

- [ ] **Step 4: Implement the suppression in `base.py`**

Following Step 1's wiring decision, modify `on_model_changed` (currently at `base.py:92-100`):

```python
    def on_model_changed(self, value: Any) -> None:
        """Override for custom model->view sync. Default drives bind()-ings.

        Skipped entirely when this widget is CSS-hidden by NodeDetail
        (2026-09): the DOM element exists but a hidden widget receiving no
        value updates keeps "a low rank costs ~nothing" true for server
        traffic, not just element count. A widget with no NodeDetail context
        (built outside a node card) always dispatches — see
        :meth:`_is_detail_hidden`.

        Subclasses that override should call ``super().on_model_changed(value)``
        to keep their bind()-registered elements live, or omit the super() call
        to take full ownership of sync.
        """
        if self._is_detail_hidden():
            return
        for binding in self._bindings:
            binding.sync_to_view()

    def _is_detail_hidden(self) -> bool:
        """True when NodeDetail's resolved rank excludes this widget.

        Defaults to False (always dispatch) when there is no NodeDetail
        context to consult — degrading toward MORE traffic, not less, matches
        NodeVisibility's own degrade-upward posture (a widget that silently
        stops updating looks broken; one that updates while hidden is only a
        performance cost)."""
        return False  # overridden per Step 1's wiring decision
```

The body of `_is_detail_hidden` depends entirely on Step 1's finding — fill it in with the actual attribute/back-reference path once known, rather than the `return False` placeholder shown here (that placeholder is only correct as a starting point before Step 1's wiring lands; it must not be the final state).

- [ ] **Step 5: Run to verify pass**

```bash
uv run pytest tests/ui/widget/test_detail_gated_dispatch.py -v
```
Expected: PASS.

- [ ] **Step 6: Run the full widget test dir to check for regressions**

```bash
uv run pytest tests/ui/widget/ -v
```
Expected: PASS. Pay particular attention to `test_bind_nested.py`, `test_bind_sugar.py`, `test_single_activation.py` (found as existing `bind()` callers during design) — these must be unaffected for any widget without NodeDetail context.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/widget/base.py tests/ui/widget/test_detail_gated_dispatch.py
git commit -m "feat(node-detail): suppress model->view dispatch for CSS-hidden widgets

Closes the traffic gap the CSS-filter redesign opened: a widget existing
but hidden at PINS/PINS_ALL/PINS_ALL rank no longer keeps pushing value
updates over the wire. Widgets outside a NodeDetail context (no node card)
are unaffected — default is always-dispatch.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: LOD — drop `display:none` crossing rules, keep `data-lod-level` as a dormant hook

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/zoom/pan.vue`

**Interfaces:**
- Consumes: nothing new.
- Produces: `pan.vue` still computes and writes `data-lod-level` on every zoom-change frame (`_updateZoomAndLODClass`, unchanged). The CSS rules that currently hide `.zoom-pan-lod1/2/3` via `display:none` and the `--lod-N-opacity`/`--lod-N-pointer-events` custom-property machinery are removed. `.hw-lod-hover`/hover-persistence rules and `.zoom-pan-lod0`'s hover box-shadow/magnifier transition are UNCHANGED (they're not part of the crossing mechanism being removed).

- [ ] **Step 1: Read the full `<style>` block once more to confirm exact boundaries**

```bash
sed -n '588,730p' packages/haywire-core/src/haywire/ui/components/zoom/pan.vue
```

(Already read during design — re-read here in case Task 5-7 touched anything nearby, which they didn't, but confirm before deleting.)

- [ ] **Step 2: Remove the crossing-cost CSS**

Delete these blocks from `pan.vue` (lines from the design-time read):
- Lines 593-598 (`.zoom-pan-lod1, .zoom-pan-lod2, .zoom-pan-lod3 { transition: opacity ... }`) — the transition is for a crossing that no longer happens.
- Lines 600-657 (the `:root` custom-property block, the `[data-lod-level="raw"/"low"/"medium"]` opacity/pointer-events overrides, and the `.zoom-pan-lodN { opacity: var(...) }` rules).
- Lines 659-697 (the `display: none` block and its long comment explaining why `display:none` beats opacity — this reasoning is now historical; keep a short pointer instead, see Step 3).
- Lines 705-712 (`.hw-lod-hover { --lod-N-opacity: 1; ... }`) — this restored the custom properties the deleted rules used, so it goes too.

KEEP lines 714-729 (`.zoom-pan-lod0` hover box-shadow + transition + the magnifier transform comment) — this is the hover/magnify affordance, unrelated to LOD hiding.

- [ ] **Step 3: Add a short replacement comment where the deleted block was**

```css
/* LOD-driven display:none rules removed (design session, 2026-09): measured
 * at 2.15x pan cost for a 0.2%/0.04% framerate gain (see
 * internals/handoff/node-detail-and-lod-classes.md, decision B, and
 * .scratch/pan-perf/RESULTS.md for the full matrix). The crossing itself —
 * not what it hides — was the cost; the collapsed-sweep control measured
 * flat (68.60 vs 68.57 fps) with nothing to hide, ruling out "not enough was
 * hidden" as the explanation.
 *
 * data-lod-level is STILL computed and written below (_updateZoomAndLODClass)
 * as a dormant hook for a future PAINT-ONLY, per-frame change — the zoom
 * value it needs is already tracked here. Nothing currently reads it. */
```

- [ ] **Step 4: Verify `_updateZoomAndLODClass` and its call site are untouched**

```bash
grep -n "_updateZoomAndLODClass\|_lodLevelFor\|data-lod-level" packages/haywire-core/src/haywire/ui/components/zoom/pan.vue
```
Expected: the same 5 references found during design (lines ~280-300, ~420-421) — none of the JS changed, only the CSS.

- [ ] **Step 5: Manual visual check**

Start the studio, open a graph with nodes, zoom out slowly across the old 0.3/0.5/0.75 thresholds while panning. Confirm: no visible hitch at the crossings (the freeze this removes), and nothing is now permanently invisible (since nothing hides anymore, everything stays visible regardless of zoom — this is the expected, intended new behavior).

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/zoom/pan.vue
git commit -m "perf(lod): drop the display:none zoom-crossing rules; keep data-lod-level dormant

Measured 2.15x pan cost for 0.2%/0.04% gain (decision B). data-lod-level
stays computed as a hook for a future paint-only feature; nothing reads it
today.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: `image-rendering: optimizeSpeed` measurement (standalone loose end)

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/zoom/pan.vue` (conditionally — only if the measurement says to change it)

**Interfaces:**
- Consumes: `debug_overlay.vue`'s `record`/`sweep` tooling.
- Produces: a recorded verdict either way; a code change only if warranted.

- [ ] **Step 1: Read the current comment and rule**

```bash
grep -n "optimizeSpeed" -B 5 -A 3 packages/haywire-core/src/haywire/ui/components/zoom/pan.vue
```

- [ ] **Step 2: Measure with and without it**

Using the same protocol as `.scratch/pan-perf/RESULTS.md` (fixed-window `record 5s`, `sweep` mode, on `graphs/10x200nodes.haywire`, zoomed low, LOD off after Task 8): take a baseline run with `image-rendering: optimizeSpeed` / `-webkit-optimize-contrast` present, then comment them out and take a second run. Discard a warm-up sweep first per the handoff's documented instrument caveat.

- [ ] **Step 3: Record the result**

Append a row to `.scratch/pan-perf/RESULTS.md` following its existing table format (read the file's header row first to match columns exactly), noting both runs and the verdict.

- [ ] **Step 4: Apply the change if warranted**

If removing the rule shows no regression (within the noise band the RESULTS.md protocol defines — read its "judge on fps median with disjoint spreads" guidance before concluding either way), remove it from `pan.vue` and update the comment. If it still matters, leave the code as-is and update the comment to record that this was re-measured post-flatten-3d and still holds, with the date.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/zoom/pan.vue .scratch/pan-perf/RESULTS.md
git commit -m "perf(pan): re-measure image-rendering: optimizeSpeed post-flatten-3d

<one line stating the verdict — kept or removed>. See .scratch/pan-perf/RESULTS.md
for the run.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 10: Documentation — ADR 0032 supersession, ADR 0006 note, glossary, probe-branch cleanup

**Files:**
- Modify: `docs/adr/0032-node-detail-and-collapse.md`
- Modify: `docs/adr/0006-node-render-performance.md`
- Modify: `docs/reference/glossary.md`
- Modify: `internals/handoff/node-detail-and-lod-classes.md`

**Interfaces:** none (documentation only).

- [ ] **Step 1: Add a "Superseded" section to ADR 0032**

Read the existing "Superseded in part (2026-08-31)" section at the end of the file first (it's the template — same heading style, same "what was right, what was wrong" structure). Append a new section after it:

```markdown
## Superseded in part (2026-09-02): NodeDetail becomes a CSS filter, not a construction gate

Decision 3 above — "Both axes gate construction, not CSS... A CSS gate would
leave every element built, mounted and re-walked" — was right about **Node
collapse** and wrong about **NodeDetail**, for a reason ADR 0006 later
measured directly: NodeDetail's construction-gate cost was never the
mounted-element re-walk this decision worried about. It was the pan-time
paint/layout cost of what those elements render, and `display: none` removes
that cost identically to never building them — measured at 0.98x/1.02x of
constructed WIDGETS-equivalent (see `.scratch/pan-perf/RESULTS.md` and
`internals/handoff/node-detail-and-lod-classes.md`, decision A).

**What changed:**
- `NodeDetail` grew from 3 ranks (`COMPACT`/`STANDARD`/`FULL`) to 5
  (`PINS`/`PINS_ALL`/`WIDGETS`/`LABELS`/`FULL`) — a floor step for "unlinked
  pins" is now distinct from "linked pins only", where the old COMPACT
  conflated them.
- Every element a rank could exclude is now always built. What a skin adds is
  a `.hw-detail-*` class (`haywire/ui/skin/visibility.py`'s `pins_all`/
  `widget`/`label`/`diagnostics` properties), matched by
  `[data-node-props-detail]` rules in `canvas.vue` — the SAME mechanism
  `locked` already used for its own attribute, and the same TECHNIQUE
  (attribute-selector + `display:none`) the zoom-driven LOD system uses,
  though the two remain conceptually separate (ADR 0006).
- `detail` left `NodeProperties.REDRAW_FIELDS`; `collapsed` did not. **Node
  collapse is unaffected by this supersession** — it stays a real
  construction gate, exactly as decision 3 originally specified, because
  nothing in the pan measurement touched it.
- A CSS-hidden widget's model→view push traffic is now explicitly suppressed
  (`BaseWidget._is_detail_hidden`), closing the gap a pure CSS-filter would
  otherwise open: "hidden but built" must not mean "hidden but still costing
  server round-trips every frame".

**Breaking change, no migration.** Old saved-graph values `"compact"`/
`"standard"` are unrecognised strings under the new enum and degrade to
`FULL` via `NodeDetail.coerce()`'s existing (unchanged) fallback. No shim was
built — there is no external install base to protect at the time of this
change.

**Not reopened:** decision 1 (two axes, not one). Collapse and NodeDetail
remain independently composable exactly as originally decided; the 5-rank
ladder lives entirely inside the NodeDetail axis.
```

- [ ] **Step 2: Add a note to ADR 0006**

Read the file's "Considered and declined" section first (where LOD/zoom-tiering is discussed) and its "Consequences" section, then add a short paragraph (matching the file's existing terse, measured style) noting: LOD's `display:none` crossing rules were removed (2026-09), measured at 2.15x pan cost for 0.2%/0.04% gain; `data-lod-level` remains computed as a dormant hook; pointer to the handoff doc and `.scratch/pan-perf/RESULTS.md` for the matrix.

- [ ] **Step 3: Update the glossary**

Read `docs/reference/glossary.md` lines 449-454 (the exact rows found during design) before editing. Update the **NodeDetail** row's rank list and construction-gate language:

```
| **NodeDetail** | The density rank of an uncollapsed node card — `PINS` (linked ports) < `PINS_ALL` (+ unlinked ports) < `WIDGETS` (+ inline widgets) < `LABELS` (+ port labels) < `FULL` (+ diagnostics detail). A **StrEnum** with a `rank` property and an `includes()` predicate, twinning `AccessTier`: wire values stay strings so adding a rank later renumbers nothing, and `coerce` degrades to `FULL` rather than raising on the render path. Carried by `NodeProperties.detail` through the framework < graph < node chain. A **CSS filter** (2026-09, superseding the original construction-gate design — see ADR 0032's "Superseded" section): every element is built; a `.hw-detail-*` class and a `[data-node-props-detail]` rule decide what's shown. | detail level, LOD (LOD is the separate zoom axis — see **LOD**) |
```

Update the **LOD** row to note the `display:none` crossing rules were removed and `data-lod-level` is now a dormant hook:

```
| **LOD** | Level of detail on the **zoom** axis only: `pan.vue` stamps `data-lod-level` (`raw` / `low` / `medium` / `high`) on the pan container from the current zoom. As of 2026-09 this is a **dormant hook** — the `display:none` crossing rules that used to key off it were removed (measured 2.15x pan cost for a 0.2%/0.04% gain), so nothing currently reads the attribute, but it stays computed for a future paint-only, per-frame feature. Decides what is **painted** of what already exists; **NodeDetail** decides what a rank includes. The two share a CSS technique (attribute selector + `display:none`) but do not compose — no rank arithmetic between them. | detail (reserve for NodeDetail) |
```

- [ ] **Step 4: Mark the handoff document resolved**

Update `internals/handoff/node-detail-and-lod-classes.md`'s frontmatter `status: open` to `status: resolved`, and add a closing note at the top pointing to this plan file and ADR 0032's superseded section, so a future reader lands on the resolution rather than the open questions.

- [ ] **Step 5: Delete the four probe branches**

```bash
git branch -D perf/lod-sweep-instrument perf/flat-cards-always perf/chrome-ladder perf/detail-via-css
```

(Local-only delete; if any were pushed to a remote, also run `git push origin --delete <branch>` for each — check first with `git branch -vv | grep -E "lod-sweep-instrument|flat-cards-always|chrome-ladder|detail-via-css"`.)

- [ ] **Step 6: Commit**

```bash
git add docs/adr/0032-node-detail-and-collapse.md docs/adr/0006-node-render-performance.md docs/reference/glossary.md internals/handoff/node-detail-and-lod-classes.md
git commit -m "docs(node-detail): record the CSS-filter supersession; retire probe branches

ADR 0032 gains a Superseded section, ADR 0006 notes the LOD display:none
removal, glossary NodeDetail/LOD rows updated, handoff marked resolved.
Probe branches (lod-sweep-instrument, flat-cards-always, chrome-ladder,
detail-via-css) deleted — their working rule shipped for real.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 11: Full verification sweep

**Files:** none — verification only.

- [ ] **Step 1: Lint and format**

```bash
uv run ruff check .
uv run ruff format --check .
```
Expected: clean. If drift is found, run `uv run ruff format .` and re-commit.

- [ ] **Step 2: Type check**

```bash
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```
Expected: clean (matches CLAUDE.md's pre-established baseline — anything new is this plan's).

- [ ] **Step 3: Full non-slow test suite**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/t.log
grep -E "passed|failed" /tmp/t.log | tail -1
```
Expected: exit=0, no FAILED/ERROR lines.

- [ ] **Step 4: Browser tests (this touched canvas.vue/pan.vue — worth the slower tier)**

```bash
uv run pytest -m browser -q > /tmp/t_browser.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/t_browser.log
```
Expected: exit=0.

- [ ] **Step 5: Report**

State plainly: full suite pass/fail counts, lint/format/mypy status, and confirm the gate-measurement outcome from Task 1 (fast/proceeded) is what actually happened — don't let a later task's success imply the gate was run if it wasn't.

---

## Self-Review Notes

**Spec coverage check**, against the design-session summary:
- Decision A (CSS filter, gate-dependent) — Tasks 1-7. ✓ (fast path only; slow path is a documented early-exit in Task 1)
- 5-rank enum, exact names — Task 2. ✓
- No migration shim, breaking change — Task 2 Step 3 (docstring), Task 10 Step 1 (ADR). ✓
- Widget traffic suppression — Task 7. ✓
- Decision B (LOD classes) — Task 8. ✓
- Scope boundary unchanged (Ports panel etc.) — no task touches those files; correct by omission. ✓
- Probe branch cleanup — Task 10 Step 5. ✓
- `optimizeSpeed` measurement — Task 9. ✓
- ADR/glossary corrections — Task 10. ✓
- SelectionToolbar/`DetailRankMenuPanel` — confirmed during design to already iterate `NodeDetail` generically; no task needed, and none was added. Verify in Task 11 that `tests/graph_editor/test_toolbar_panels.py` (found as an existing covering test) still passes with 5 rows instead of 3 — if it hard-codes a row COUNT, it will need a one-line update; flagged here since it wasn't captured as its own task.

**Follow-up flagged, not forgotten:** if Task 11's full suite surfaces a hard-coded 3-row assumption in `tests/graph_editor/test_toolbar_panels.py` or `tests/graph_editor/test_toolbar_surface.py`, fix it inline as part of Task 11 rather than leaving the suite red — this is a mechanical fix (update the expected count/labels), not a design question.

---

## Fallback: gate is slow (Task 1 says no-go)

If Task 1's measurement comes back slow, this plan's Tasks 2-9 do not run. The only remaining work is documentation:
1. Task 10 Steps 4-5 only (mark the handoff resolved with the "construction gating confirmed necessary" verdict from Task 1 Step 4, delete the four probe branches).
2. No ADR 0032 supersession — the ADR stands as originally written, decision 3 confirmed correct for NodeDetail after all.
3. No glossary changes.

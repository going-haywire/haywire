# Swinglets and the annotation rework Implementation Plan

> **Landed 2026-10-08.** Executed 2026-10-07 by subagent-driven development, live-checked by the
> user 2026-10-08, squashed into two commits on master 727d336b. Departures from the tasks below:
>
> - A master bug surfaced under Review Focus 4: a data node downstream of a data-only Group ran
>   before the Group's interior. Fixed as its own commit (the ordering walks in `DataFlowBuilder`
>   use inlet-side lookups); `FlatGraphView`'s outgoing `_interior_sinks` splice became dead and
>   was removed, which supersedes the outgoing half of Q109.
> - `out()` refuses only a pure inlet, not every non-outlet: a visiongraph node writes a config
>   port through `out()`. A config written that way does not fire its `on_change` (Q108).
> - A reconnect anchored on a swinglet and dropped on a pure inlet or outlet takes its
>   orientation from that pin; between two swinglets the anchor keeps its role (Q111).
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A port can be a *swinglet*: one pin that may be either end of an edge, on every wire type. Annotation notes use one growing set of swinglets per side, drawn centred, so the user links any side of one note to any side of another with one gesture.

**Architecture:**

- `PortType.SWINGLET` answers True to both `is_inlet()` and `is_outlet()`.
- A port's edges move into two `LinkSet`s, `port.incoming` and `port.outgoing`. Every reader that lists edges picks the set for the end it means.
- Values:
  - An edge's write to a swinglet behaves like an inlet write: it is stored as the linked value and goes no further.
  - The node's `out()` behaves like an outlet write: it goes to the own value through `DataPort._emit`.
  - A pipe reads its source's own value.
- The canvas learns a third pin direction, `"swinglet"`. A drag between two swinglets takes its direction from the drag order.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3 (`canvas.vue`), pytest (+ xdist, Playwright browser tier), uv, ruff, mypy.

**Spec:** [2026-10-05-diagram-annotations.md](2026-10-05-diagram-annotations.md), decisions Q95 to Q117 and the section "Verification of 2026-10-06". A throwaway spike of the core is at `.scratch/swinglet-spike/spike.diff`: a reference only, never applied. Corrections found while writing this plan are in [Corrections to the design](#corrections-to-the-design); the user decided them on 2026-10-07 (Q106 to Q117), and the tasks below already follow those answers.

## Global Constraints

- **Repo:** `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo`. haybale-visiongraph (`barn/haybale-visiongraph`, a symlink) is not changed; its tests run as a regression check only.
- **Branch:** `diagram-annotations`. The `wip(annotation)` commit 4594f86e is the starting point; this plan reworks it. Never push; the user pushes.
- **Commit trailer:** every commit message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Never commit:**
  - `docs/superpowers/plans/` (plans are left for the user to commit);
  - `.scratch/`, `internals/`, `.superpowers/`, `.claude/settings.json`.

  Always `git add` explicit paths, never `-A` or `.`.
- **Commit `barn/haybale-testing/` first.** Commit every change there before running the full suite. `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing` in its teardown and discards uncommitted edits and untracked files.
- **Intended behaviour changes.** These are the only ones, each with its test named in its task. Any other red behavioural test is a bug: stop and report it.
  1. `PortType.SWINGLET` exists. `is_inlet()` and `is_outlet()` are True for it, and `get_ports(is_port_type=INLET|OUTLET)` returns it (Q95).
  2. The formal check is positive: the outlet end must be `is_outlet()` and the inlet end `is_inlet()` (Q96).
  3. An edge whose reverse is already in the graph is refused, on every wire: one edge between two pins (Q112).
  4. A swinglet's values follow Q100, Q101 and Q107. The pipe reads the source's own value, which changes nothing for an outlet.
  5. `on_change` reports only what a node receives (Q108):
     - the outlet half of a write (`out()`, `_emit`, and `set_value` on an outlet) never fires it;
     - `as_outlet(..., on_change=...)` raises `ValueError`; no port declares one today.
  6. The annotation node's port ids become `{side}_{index}` (one swinglet set per side), and its pins are drawn centred (Q99, Q105, Q117). No annotation graph has shipped, so nothing is migrated.
  7. Canvas:
     - a swinglet takes part in drags;
     - a drop onto a pin pair already linked in either direction is ignored (Q112);
     - a reconnect keeps both ends' roles (Q111);
     - suggestion paths use the target pin's own vector. On ordinary cards that vector is the same as before.
- **Out of scope:**
  - promoting a setting to a swinglet;
  - linking a note to an ordinary node ("pins anywhere");
  - Markdown in note text;
  - undoable text and style edits (Q92);
  - the inverted-looking but documented `is_inlet` argument of `NodeData.iter_hidden_connected_ports`;
  - the dead `graph_to_python.py` inlet branch.
- **Hot path:** `set_value`, `out()`, `Pipe.pull`, `Pipes.propagate` and `resolve_dirty_data` gain no branch (Q101). `LinkSet` is read at patch time only. Task 11 runs the benchmark against Task 0's baseline.
- **Docstrings and comments** follow `.claude/rules/python-docs.md`. Docstrings of registered components (nodes, types, skins) are displayed: Markdown, single backticks, no reST.
- **"Ruff check"** means both `uv run ruff check <paths>` and `uv run ruff format --check <paths>`; line length 109.
- **Pre-commit gate:**
  - Run: `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`
  - Then: `grep -E "^FAILED|^ERROR" /tmp/t.log` and `tail -1 /tmp/t.log`.
  - Timeout at least 600000 ms. The baseline is recorded in Task 0.
- **Browser tier:** `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`. Rerun once before calling a single timing test red (`tests/README.md`).
- **visiongraph tests:** from this repo, `uv run pytest ../haybale-visiongraph/tests -q -p no:randomly`.
- **mypy set:** `uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/`. The baseline is clean.
- **Canvas changes are checked in a browser**, not only in unit tests (`.insights/project_multi_canvas_dom_globals.md`).
- **Registry keys in tests** come from `Cls.class_identity.registry_key`, never string literals (`.insights/project_unknown_key_yields_error_node.md`).
- **Code lookup:** the repo is indexed by CodeGraph. `codegraph explore "<symbols>"` returns verbatim source plus callers.

## Review Focus

Failure modes the spec implies that the per-feature tests would miss. Each has its test in the owning task.

1. **A swinglet re-typed while it holds edges at both ends** (hot reload, `rejig`): `adopt_state_from` must carry both sets and re-point every edge (`.insights/project_rejig_orphans_edge_port_refs.md`). Test: Task 3, `test_a_retyped_swinglet_keeps_both_edges`.
2. **Undo of a deleted note link:** restoring the edge must not trip the reverse check. Test: Task 3, `test_undo_restores_a_deleted_visual_swinglet_edge`.
3. **Save and load of a swinglet that holds both ends on a data wire:** link limits per set on load, and the node's own value saved under `NODE_SET`. Test: Task 5, `test_a_swinglet_round_trips_with_both_edges_and_its_own_value`.
4. **A value-carrying swinglet node collapsed into a Group,** with its incoming edge crossing in and its outgoing edge crossing out: `FlatGraphView` splices must still order the run. Test: Task 5, `test_a_collapsed_swinglet_node_still_passes_its_write_on`.
5. **Paste of two linked notes:** edge ids are re-minted, and the reverse check must not refuse the pasted edge. Test: Task 9, `test_pasting_two_linked_notes_keeps_their_link`.

---

## Corrections to the design

Found while writing this plan and decided by the user on 2026-10-07; the design records them as Q106 to Q117. The tasks below follow the decided column.

| # | Design said | The code says | Decided |
|---|---|---|---|
| C1 (Q106) | Q98: a `VISUAL` edge crossing a collapse is removed by the collapse | Q41 (wire types) made a `VISUAL` wire cross a Group boundary like any other, tested in `tests/core/test_graph/test_visual_wire_group.py`. Q98 assumed crossing swinglet edges fail validation; under Q96 they re-wire validly | Drop Q98; keep Q41. Task 9 adds a collapse/expand test across note links |
| C2 (Q107) | Q100: an unfed swinglet "counts up on every run" | A data node runs only when a port is dirty (`BaseNode._execute`), and its own `out()` dirties nothing (spike) | Data nodes stay dirty-gated. The docs explain it from the inlet and outlet rules, show `out("x", value("x") + 1)` as one pattern, and point to `on_change` for reacting to input changes |
| C2b (Q108) | (not stated) | `out()` on an outlet fires that port's `on_change` synchronously; a swinglet would inherit it, so a handler that calls `out()` would call itself. No port declares an outlet `on_change` | `on_change` reports only what a node receives. The outlet half never fires it, and `as_outlet(..., on_change=...)` raises `ValueError` |
| C3 (Q109) | Q103: split `graph._get_edge_wrappers_for_port` into one method per direction | `FlatGraphView` overrides that method to splice Subgraph crossings | One method with a required keyword, `_get_edge_wrappers_for_port(node_id, port_id, *, incoming: bool)`, on `BaseGraph` and `FlatGraphView`. Every caller names the end; the view applies `_reroute_source` to incoming and `_interior_sinks` to outgoing edges |
| C4 (Q110) | Q103: `should_show_widget` reads the incoming set | An outlet with `WHEN_LINKED` asks about its outgoing edges | An inlet or swinglet asks its incoming set; an outlet asks its outgoing set |
| C5 (Q111) | (not stated) | A reconnect drag starts at the kept end. Between two swinglets the drag order then decides, so re-dragging the outlet end of A→B gives B→C and moves the arrow head | `SyncEdgeReconnectEvent.anchorEnd` (`"outlet"` or `"inlet"`). Between two swinglets the canvas keeps the anchor's role |
| C6 (Q112, corrects Q97) | Q97: refuse a reverse edge on `VISUAL` wires only | The user's rule: one edge between two pins, whatever the wire or direction | `add_edge_wrapper` refuses an edge whose reverse id exists, on every wire. The canvas's `_edgeExists` checks both orders on every drop. No wire-role pin attribute |
| C7 (Q113) | (not stated) | `as_swinglet` needs per-direction defaults | `store_strategy` defaults to `HAS_WIDGET \| NODE_SET` and `show_widget` to `NOT_LINKED`; the type's own declaration wins |
| C8 (Q114) | Q102: each set has its own ceiling | `takes_many_links` is read by the pin glyph (`_multi`) and by Farmhand | `DataPort.takes_many_links` stays: the outgoing set's ceiling for an outlet, the incoming set's otherwise. Farmhand adds `outgoing_takes_many` to a swinglet's row |
| C9 (Q115) | (not stated) | The pin glyph resolver knows the roles `in` and `out` | Role `swing`: `<kind>_swing[_multi]`, then `<kind>`, then the fallback. Defaults: `data_swing`/`compound_swing` `radio_button_checked`, `control_swing` `join_inner`, `callback_swing` `swap_horiz`. A declared glyph uses `icon_in`/`icon_in_multi` |
| C10 (Q116) | (not stated) | The studio skins split pins into inlet and outlet columns. The split and error skins would draw a swinglet twice; the stacked skin drops it | Each skin draws a swinglet once, on the inlet side. Properties gets a "Swinglets" lane; Farmhand reports `direction: "swinglet"` under a `"swinglets"` bucket; the docs generator orders inlet, swinglet, config, outlet |
| C11 (Q117) | Q105: centred pins | Slots are revealed with `visibility: hidden`, so they keep their box | Grown pins are centred as a group. The slot sits in a zero-width wrapper after the last pin (centred when the side has none). Ghost pins move to their own wrapper, rendered before the strip |

## Names this plan introduces

| Name | Where | What |
|---|---|---|
| `PortType.SWINGLET` | `core/types/enums.py` | Value `"swinglet"` |
| `DataPort.is_swinglet()` | `core/types/port.py` | True for a swinglet |
| `IType.as_swinglet(id, **kwargs) -> PortSpec` | `core/types/interface.py` | The factory |
| `LinkSet` | `core/types/link_set.py` (new) | One end's edges: `linked`, `all`, `takes_many`, link methods |
| `DataPort.incoming`, `DataPort.outgoing` | `core/types/port.py` | The two `LinkSet`s |
| `DataPort._emit(new_value: Any) -> None` | same | The outlet half of a write; `out()` calls it; fires no `on_change` |
| `DataPort.get_own_value() -> Any` | same | The own value, whether or not a linked value stands in front |
| `_get_edge_wrappers_for_port(node_id, port_id, *, incoming: bool)` | `core/graph/base.py`, `core/assembly/flat_view.py` | Changed signature: a port's edges at one end |
| `SyncEdgeReconnectEvent.anchorEnd: str` | `ui/components/graph/event_definitions.py` | `"outlet"` or `"inlet"` |
| `_orientEdge(startPin, endPin)` | `canvas.vue` | `[outletEndPin, inletEndPin]` for a drop |
| `ICONS.JOIN_INNER`, `ICONS.SWAP_HORIZ` | `ui/themes/icons.py` | New glyph constants (`"join_inner"`, `"swap_horiz"`) |
| `SwingletPassProbeNode`, `SwingletStopProbeNode`, `SwingletControlProbeNode`, `SwingletVisualProbeNode`, `SwingletEchoProbeNode` | `barn/haybale-testing/haybale_testing/nodes/testbed/swinglet_probe.py` (new) | Testbed nodes |

## File structure

| File | Change |
|---|---|
| `packages/haywire-core/src/haywire/core/types/enums.py` | `SWINGLET`; `default_show_widget`; `side_for`/`vector_for` docstrings |
| `packages/haywire-core/src/haywire/core/types/link_set.py` | new: `LinkSet` |
| `packages/haywire-core/src/haywire/core/types/port.py` | predicates, `_is_inlet` cache, the two sets, `_emit`, `get_own_value`, readers, `on_change` only on receiving |
| `packages/haywire-core/src/haywire/core/types/interface.py` | `as_swinglet`; `as_outlet` refuses `on_change` |
| `packages/haywire-core/src/haywire/core/types/pipe.py` | `pull` reads the own value |
| `packages/haywire-core/src/haywire/core/node/data.py` | `get_ports`, `out()`, `_pop` |
| `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` | link calls per set; positive formal check |
| `packages/haywire-core/src/haywire/core/graph/base.py` | reverse check; `control_transitions`; `_get_edge_wrappers_for_port(..., incoming=)` |
| `packages/haywire-core/src/haywire/core/assembly/flat_view.py`, `data_flow_builder.py` | every edge lookup names its end |
| `packages/haywire-core/src/haywire/core/node/inspector.py` | `"swinglet"` direction |
| `barn/haybale-core/haybale_core/types/pooled_type.py` | error message |
| `barn/haybale-testing/haybale_testing/nodes/testbed/swinglet_probe.py` | new: probe nodes |
| `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py` | direction, filter, bucket, `outgoing_takes_many` |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py` | "Swinglets" lane |
| `packages/haywire-studio/src/haywire_studio/packaging/docs/render.py` | `_DIRECTION_ORDER` |
| `packages/haywire-core/src/haywire/ui/skin/pin_render.py`, `pin_icons.py`, `ui/themes/icons.py` | `data-pin-dir="swinglet"`, `swing` glyph role, two glyph constants |
| `barn/haybale-studio/haybale_studio/skins/split_skin.py`, `error_skin.py`, `stacked_skin.py` | one swinglet pin, inlet side |
| `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`, `event_definitions.py` | swinglet drags, both-order duplicate check, reconnect role, suggestion tangents |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py`, `context_menu.py` | auto-wire, reconnect anchor end |
| `packages/haywire-core/src/haywire/barn/builtin/nodes/annotation.py`, `skins/annotation_skin.py` | swinglet slots, centred pins |
| docs: glossary, ADR 0048 (new), `docs/guides/ports.md`, `docs/components/skins/skin-canon.md`, builtin generated docs, the design's status | Task 10 |

---

### Task 0: Baseline (controller)

- [x] **Step 1: Confirm the corrections.** Done 2026-10-07: Q106 to Q117 in the design doc, folded into the tasks below.
- [ ] **Step 2: Clean tree.** `git status --short` shows nothing but the plan files, `.scratch/swinglet-spike/` and `.claude/settings.json`.
- [ ] **Step 3: Baselines.** Run the pre-commit gate, the browser tier, the visiongraph tests, the mypy set and `uv run ruff check . && uv run ruff format --check .`. Record the pass counts in `.superpowers/sdd/progress.md` under a new section "swinglets". All must be green; if not, stop and start an error-fix session with the user (CLAUDE.md).
- [ ] **Step 4: Benchmark baseline.** Run the `haywire-benchmark` skill on the clean tree; Task 11 compares against it.

---

### Task 1: `PortType.SWINGLET`, the predicates and the factory

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/enums.py` (`PortType`, `default_show_widget`)
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (`is_outlet`, `is_inlet`, new `is_swinglet`, `adopt_port_type`, `__post_init__` cache)
- Modify: `packages/haywire-core/src/haywire/core/types/interface.py` (new `as_swinglet` after `as_outlet`)
- Modify: `packages/haywire-core/src/haywire/core/node/data.py` (`get_ports`)
- Modify: `barn/haybale-core/haybale_core/types/pooled_type.py:73-77` (message only)
- Create: `barn/haybale-testing/haybale_testing/nodes/testbed/swinglet_probe.py`
- Create: `tests/core/test_types/test_swinglet_port.py`

**Interfaces:**
- Produces:
  - `PortType.SWINGLET` (value `"swinglet"`).
  - `DataPort.is_swinglet() -> bool`. `is_inlet()` is True for `INLET` and `SWINGLET`; `is_outlet()` is True for `OUTLET` and `SWINGLET`.
  - `DataPort._is_inlet` is True for `INLET` and `SWINGLET`.
  - `IType.as_swinglet(id: str, **kwargs) -> PortSpec`, which calls `_validate_port_type(PortType.SWINGLET)`.
  - `get_ports(is_port_type=PortType.INLET)` matches `is_inlet()`, `PortType.OUTLET` matches `is_outlet()`, and any other value matches exactly.
  - Probe nodes:
    - `SwingletPassProbeNode`: `DATA`, `FLOAT` swinglet `s` default `0.0`. Its worker appends `s` to `self.seen: list[float]`, then calls `out("s", s * 10)`.
    - `SwingletStopProbeNode`: the same, without the `out`.
    - `SwingletControlProbeNode`: `CONTROL`, `EXEC` swinglet `flow`. Its worker increments `self.runs: int` and returns `"flow"`.
    - `SwingletVisualProbeNode`: `DATA`, `TEST_VISUAL` swinglet `note`, a worker that returns `None`.
    - `SwingletEchoProbeNode`: `DATA`, `FLOAT` swinglet `s` with `on_change="hb_s"`. `hb_s(self, port, value)` appends `value` to `self.changes: list[float]`, then calls `out("s", value + 1)`. Its worker does nothing.
    - `seen`, `runs` and `changes` are set in `init()`.

- [ ] **Step 1: Write the failing tests** in `tests/core/test_types/test_swinglet_port.py`:

```python
"""A swinglet: one port that may be either end of an edge."""

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, PortType, ShowWidgetStrategy, StoreStrategy

from tests.conftest import make_node


def _port(type_cls, port_type, **kwargs) -> DataPort:
    return DataPort(
        registry_id="p", registry_key=type_cls.class_identity.registry_key, label="P",
        id="p", type_cls=type_cls, port_type=port_type, **kwargs,
    )


@pytest.mark.unit
def test_a_swinglet_is_both_an_inlet_and_an_outlet():
    port = _port(FLOAT, PortType.SWINGLET)
    assert port.is_inlet() and port.is_outlet() and port.is_swinglet()
    assert port._is_inlet is True


@pytest.mark.unit
def test_inlets_and_outlets_stay_one_direction():
    inlet, outlet = _port(FLOAT, PortType.INLET), _port(FLOAT, PortType.OUTLET)
    assert not inlet.is_outlet() and not inlet.is_swinglet()
    assert not outlet.is_inlet() and not outlet.is_swinglet()


@pytest.mark.unit
def test_adopting_the_swinglet_type_refreshes_the_cache():
    port = _port(FLOAT, PortType.OUTLET)
    port.adopt_port_type(PortType.SWINGLET)
    assert port._is_inlet is True


@pytest.mark.unit
def test_as_swinglet_defaults():
    kwargs = FLOAT.as_swinglet("s")["kwargs"]
    assert PortType(kwargs["port_type"]) is PortType.SWINGLET
    assert ShowWidgetStrategy(kwargs["show_widget"]) is ShowWidgetStrategy.NOT_LINKED
    assert StoreStrategy(kwargs["store_strategy"]) == StoreStrategy.HAS_WIDGET | StoreStrategy.NODE_SET


@pytest.mark.unit
def test_a_pooled_type_refuses_a_swinglet():
    from haybale_core.types import PooledType

    with pytest.raises(ValueError, match="inlets only"):
        PooledType[FLOAT].as_swinglet("s")  # type: ignore[valid-type]


@pytest.mark.integration
def test_get_ports_finds_a_swinglet_under_either_direction(graph_with_library_system):
    from haybale_testing.nodes.testbed.swinglet_probe import SwingletPassProbeNode

    node = make_node(graph_with_library_system, SwingletPassProbeNode.class_identity.registry_key).node
    for port_type in (PortType.INLET, PortType.OUTLET, PortType.SWINGLET):
        assert [p.id for p in node.get_ports(is_port_type=port_type)] == ["s"]


@pytest.mark.integration
def test_a_swinglet_round_trips_through_a_save(graph_with_library_system):
    from haybale_testing.nodes.testbed.swinglet_probe import SwingletPassProbeNode

    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    graph = graph_with_library_system
    node = make_node(graph, SwingletPassProbeNode.class_identity.registry_key)
    loaded = BaseGraph(filestem="g2", validation_scheduler=SyncScheduler())
    assert loaded.load_from_dict(graph.to_dict(include_data=True)) is True
    assert loaded.get_node_wrapper(node.node_id).node.ports["s"].is_swinglet()
```

- [ ] **Step 2: Run them; expect failures** on `PortType.SWINGLET`, `as_swinglet` and the missing probe module.
  Run: `uv run pytest tests/core/test_types/test_swinglet_port.py -q -p no:randomly`

- [ ] **Step 3: Implement.**
  - `default_show_widget` gets an explicit `SWINGLET → NOT_LINKED` branch, and its docstring lists it.
  - `as_swinglet` documents its kwargs like `as_inlet`, plus one paragraph on values (Q100, Q107) and one on `on_change` (Q108: it reports what arrives, never the node's own write). Its example is `self.add(FLOAT.as_swinglet("value", default=0.0))`.
  - The `PooledType` message becomes "PooledType supports inlets only: pooled fields aggregate multiple inputs."
  - The probe file follows `visual_probe.py` (`@node(..., menu="testing/testbed", search_tags=["test", "swinglet"])`).

- [ ] **Step 4: Run the tests; expect PASS.** Then `uv run pytest tests/core/test_types tests/core/test_node -q -n 4`; expect green.
- [ ] **Step 5: Ruff check and mypy on the touched files. Commit `barn/haybale-testing/` first, then the rest.**

```bash
git add barn/haybale-testing/haybale_testing/nodes/testbed/swinglet_probe.py
git commit -m "test(testbed): swinglet probe nodes"
git add packages/haywire-core/src/haywire/core/types/enums.py packages/haywire-core/src/haywire/core/types/port.py packages/haywire-core/src/haywire/core/types/interface.py packages/haywire-core/src/haywire/core/node/data.py barn/haybale-core/haybale_core/types/pooled_type.py tests/core/test_types/test_swinglet_port.py
git commit -m "feat(ports): PortType.SWINGLET, a port that may be either end of an edge"
```

---

### Task 2: `LinkSet`, one edge set per end (no behaviour change)

A pure refactor: inlets and outlets behave exactly as before. A swinglet is only exercised from Task 3 on.

**Files:**
- Create: `packages/haywire-core/src/haywire/core/types/link_set.py`
- Create: `tests/core/test_types/test_link_set.py`
- Modify: `packages/haywire-core/src/haywire/core/types/port.py`:
  - `_linked_edges` and `_all_edges` are replaced by `incoming` and `outgoing`;
  - remove `_add_link`, `_clear_link`, `_remove_edge`, `_try_reenable`, `_is_linked_to` and `_detach_all_edges`;
  - update `is_linked`, `get_valid_edges`, `_get_linked_edges_uuid`, `takes_many_links`, `should_show_widget`, `adopt_state_from`, `_reveal_own_value_if_unlinked` and `_refresh_pipes`.
- Modify: `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py`: `link`, `unlink`, `detach`, `_on_displaced_from_inlet`, `_update_link_state`, `_try_reenable_on_ports`.
- Modify: `packages/haywire-core/src/haywire/core/node/data.py`: `_pop`.
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py`: `control_transitions`.
- Modify: every test that reaches the removed internals. List them with `grep -rlnE "_linked_edges|_all_edges|_add_link|_clear_link|_try_reenable|_detach_all_edges|_is_linked_to" tests`; today that is 14 files, among them `test_unlink_reveals_own_value.py`, `test_edges.py`, `test_link_ceiling.py` and `test_promoted_shared_cell.py`.

**Interfaces:**
- Consumes: Task 1's `PortType.SWINGLET` (unit tests only).
- Produces:
  - `LinkSet(port: DataPort, is_incoming: bool)` with `__slots__ = ("_port", "is_incoming", "linked", "all")`.
    - `linked: dict[str, EdgeWrapper]` and `all: dict[str, EdgeWrapper]`.
    - `takes_many: bool` (property).
    - `add_link(edge) -> list[EdgeWrapper]` (the displaced edges, oldest first).
    - `clear_link(edge_id: str) -> None`, `remove_edge(edge_id: str) -> None`, `is_linked_to(edge_id: str) -> bool`.
    - `try_reenable() -> EdgeWrapper | None`, `valid_edges() -> list[EdgeWrapper]`, `detach_all() -> list[EdgeWrapper]`.
    - `adopt(other: LinkSet) -> None` copies `other`'s two dicts.
  - `DataPort.incoming` and `DataPort.outgoing`: `field(init=False, repr=False, compare=False, metadata={"serialize": False})`, both created in `__post_init__` for every port.
  - Kept on `DataPort`:
    - `is_linked()` is True if either set is linked;
    - `get_valid_edges()` and `_get_linked_edges_uuid()` cover both sets;
    - `takes_many_links` is `outgoing.takes_many` for an `OUTLET`, otherwise `incoming.takes_many` (C8).

- [ ] **Step 1: Write the failing tests** in `tests/core/test_types/test_link_set.py`:

```python
"""A port's edges in two sets: those ending at it (incoming) and those leaving it (outgoing)."""

import pytest

from haywire.barn.builtin.types import CALLBACK, EXEC, FLOAT
from haywire.core.types import DataPort, PortType
from haywire.core.types.link_set import LinkSet

pytestmark = pytest.mark.unit


def _port(type_cls, port_type, **kwargs) -> DataPort:
    return DataPort(
        registry_id="p", registry_key=type_cls.class_identity.registry_key, label="P",
        id="p", type_cls=type_cls, port_type=port_type, **kwargs,
    )


@pytest.mark.parametrize("port_type", [PortType.INLET, PortType.OUTLET, PortType.SWINGLET, PortType.CONFIG])
def test_every_port_has_both_sets(port_type):
    port = _port(FLOAT, port_type)
    assert isinstance(port.incoming, LinkSet) and port.incoming.is_incoming
    assert isinstance(port.outgoing, LinkSet) and not port.outgoing.is_incoming
    assert port.incoming.linked == {} and port.outgoing.all == {}


@pytest.mark.parametrize(
    ("type_cls", "incoming_many", "outgoing_many"),
    [(FLOAT, False, True), (EXEC, True, False), (CALLBACK, False, True)],
)
def test_each_set_takes_its_half_of_the_ceiling(type_cls, incoming_many, outgoing_many):
    port = _port(type_cls, PortType.SWINGLET)
    assert port.incoming.takes_many is incoming_many
    assert port.outgoing.takes_many is outgoing_many


def test_a_visual_swinglet_takes_many_at_both_ends():
    from haybale_testing.types import TEST_VISUAL

    port = _port(TEST_VISUAL, PortType.SWINGLET)
    assert port.incoming.takes_many and port.outgoing.takes_many


def test_single_link_narrows_both_sets():
    port = _port(FLOAT, PortType.SWINGLET, single_link=True)
    assert not port.incoming.takes_many and not port.outgoing.takes_many


def test_takes_many_links_reads_the_receiving_set_except_on_an_outlet():
    assert _port(EXEC, PortType.SWINGLET).takes_many_links is True
    assert _port(EXEC, PortType.INLET).takes_many_links is True
    assert _port(EXEC, PortType.OUTLET).takes_many_links is False
```

- [ ] **Step 2: Run; expect an ImportError on `link_set`.**
  Run: `uv run pytest tests/core/test_types/test_link_set.py -q`

- [ ] **Step 3: Implement `LinkSet`.**
  - Move the bodies of `DataPort._add_link`, `_clear_link`, `_remove_edge`, `_try_reenable`, `_is_linked_to`, `get_valid_edges` and `_detach_all_edges` over unchanged.
  - `self._linked_edges` becomes `self.linked`, `self._all_edges` becomes `self.all`, and port state is reached through `self._port`.
  - Two incoming-only actions sit behind `if self.is_incoming`:
    - `_port._data.remove_source(...)`, both on displacement in `add_link` and in `clear_link`;
    - the `_pending_lazy_pipes` purge in `clear_link`.
  - `takes_many`:
    - incoming: `not single_link and (has_role(SEQUENCE) or has_role(VISUAL) or data.keeps_value_per_source())`;
    - outgoing: `not single_link and not has_role(SEQUENCE)`.
  - Import `DataPort` and `EdgeWrapper` under `TYPE_CHECKING` only.

- [ ] **Step 4: Rewire `DataPort`, `EdgeWrapper`, `NodeData._pop` and `control_transitions`.**
  - `EdgeWrapper` addresses `self._inlet_port.incoming.<m>` and `self._outlet_port.outgoing.<m>` at every former `_inlet_port._<m>` and `_outlet_port._<m>` call.
  - `_refresh_pipes`: builds pipes from `self.outgoing.valid_edges()` while `self.outgoing.linked`, and clears them otherwise. There is no port-type test.
  - `_reveal_own_value_if_unlinked` reads `self.incoming.linked`.
  - `should_show_widget` reads `incoming.linked` for an inlet or swinglet and `outgoing.linked` for an outlet (C4).
  - `adopt_state_from` adopts both sets, then re-points every edge in both sets' `all`.
  - `_pop`:

```python
for link_set in (port.incoming, port.outgoing):
    for edge in link_set.detach_all():
        if link_set.is_incoming:
            # The source end needs its pipe removed; the sink end of an outgoing edge is not told.
            source = edge._outlet_port
            if source is not None and source is not port:
                source.outgoing.remove_edge(edge.edge_id)
                edge._update_link_state()
                source._housekeeping()
        else:
            edge._update_link_state()
        edge.redraw()
```

  - `control_transitions` reads `outlet.outgoing.valid_edges()`.

- [ ] **Step 5: Port the tests that reach removed internals.** `port._linked_edges` becomes `port.incoming.linked` on an inlet and `port.outgoing.linked` on an outlet; the same for `_all_edges`/`all`. `port._add_link(e)` becomes `port.incoming.add_link(e)` or `port.outgoing.add_link(e)`, by the end the test means. Change nothing else in those tests.
- [ ] **Step 6: Run the new tests, then the pre-commit gate.** Expect PASS, with the gate count equal to the baseline plus the new tests.
- [ ] **Step 7: Ruff check and mypy. Commit.**

```bash
git add packages/haywire-core/src/haywire/core/types/link_set.py packages/haywire-core/src/haywire/core/types/port.py packages/haywire-core/src/haywire/core/edge/edge_wrapper.py packages/haywire-core/src/haywire/core/node/data.py packages/haywire-core/src/haywire/core/graph/base.py tests/core/test_types/test_link_set.py <ported test files>
git commit -m "refactor(ports): LinkSet, a port's edges split into incoming and outgoing"
```

---

### Task 3: Swinglet links, the positive formal check and the reverse check

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py`: `_formal_validation`, the two direction checks
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py`: `add_edge_wrapper`, the reverse check and the docstring's `Raises:`
- Create: `tests/core/test_edge/test_swinglet_links.py`

**Interfaces:**
- Consumes: Task 1's probe nodes; Task 2's `incoming`/`outgoing`.
- Produces: `add_edge_wrapper` raises `ValueError` when the reverse id is already in the graph, on every wire (Q112: one edge between two pins).

- [ ] **Step 1: Write the failing tests** in `tests/core/test_edge/test_swinglet_links.py`. Helpers: `_key(cls)` returns `cls.class_identity.registry_key`, and `_add()` creates a `TestAddFloatNode` (from `haybale_testing.nodes.testbed.math_op_node`). Every test is `@pytest.mark.integration` and uses `graph_with_library_system` as `graph`; every graph ends with `graph.force_validation()` before asserting.

```python
def test_a_swinglet_takes_either_end_of_a_data_edge(graph):
    a, p, b = _add(graph), make_node(graph, _key(SwingletPassProbeNode)), _add(graph)
    e_in = make_edge(graph, a.node_id, "result", p.node_id, "s")
    e_out = make_edge(graph, p.node_id, "s", b.node_id, "value_a")
    graph.force_validation()
    s = p.node.ports["s"]
    assert e_in.is_valid() and e_out.is_valid()
    assert list(s.incoming.linked) == [e_in.edge_id]
    assert list(s.outgoing.linked) == [e_out.edge_id]


def test_two_swinglets_link_on_a_visual_wire_in_drag_order(graph):
    v1, v2 = (make_node(graph, _key(SwingletVisualProbeNode)) for _ in range(2))
    edge = make_edge(graph, v1.node_id, "note", v2.node_id, "note")
    graph.force_validation()
    assert edge.is_valid() and not edge.carries_values
    assert (edge.source_node_id, edge.sink_node_id) == (v1.node_id, v2.node_id)


def test_a_second_incoming_data_edge_displaces_only_the_first(graph):
    a1, a2, p, b = _add(graph), _add(graph), make_node(graph, _key(SwingletPassProbeNode)), _add(graph)
    first = make_edge(graph, a1.node_id, "result", p.node_id, "s")
    out = make_edge(graph, p.node_id, "s", b.node_id, "value_a")
    second = make_edge(graph, a2.node_id, "result", p.node_id, "s")
    graph.force_validation()
    assert not first.is_valid() and second.is_valid() and out.is_valid()


def test_a_control_swinglet_keeps_one_outgoing_edge_and_many_incoming(graph):
    c, i1, i2, o1, o2 = (make_node(graph, _key(SwingletControlProbeNode)) for _ in range(5))
    in1 = make_edge(graph, i1.node_id, "flow", c.node_id, "flow")
    in2 = make_edge(graph, i2.node_id, "flow", c.node_id, "flow")
    out1 = make_edge(graph, c.node_id, "flow", o1.node_id, "flow")
    out2 = make_edge(graph, c.node_id, "flow", o2.node_id, "flow")
    graph.force_validation()
    assert in1.is_valid() and in2.is_valid()
    assert not out1.is_valid() and out2.is_valid()


def test_removing_a_swinglet_detaches_both_sets(graph):
    a, p, b = _add(graph), make_node(graph, _key(SwingletPassProbeNode)), _add(graph)
    e_in = make_edge(graph, a.node_id, "result", p.node_id, "s")
    e_out = make_edge(graph, p.node_id, "s", b.node_id, "value_a")
    graph.force_validation()
    with p.node.rejig(include=["s"]):
        pass
    graph.force_validation()
    assert a.node.ports["result"].outgoing.linked == {}
    assert not e_in.is_valid() and not e_out.is_valid()


def test_a_reverse_visual_edge_is_refused(graph):
    v1, v2 = (make_node(graph, _key(SwingletVisualProbeNode)) for _ in range(2))
    make_edge(graph, v1.node_id, "note", v2.node_id, "note")
    graph.force_validation()
    with pytest.raises(ValueError, match="other way"):
        graph.create_edge_wrapper(v2.node_id, "note", v1.node_id, "note")


def test_a_reverse_control_edge_is_refused_too(graph):
    c1, c2 = (make_node(graph, _key(SwingletControlProbeNode)) for _ in range(2))
    make_edge(graph, c1.node_id, "flow", c2.node_id, "flow")
    with pytest.raises(ValueError, match="other way"):
        graph.create_edge_wrapper(c2.node_id, "flow", c1.node_id, "flow")


def test_undo_restores_a_deleted_visual_swinglet_edge(graph):  # Review Focus 2
    from haywire.core.undo.actions.graph_actions import RemoveElementsAction

    v1, v2 = (make_node(graph, _key(SwingletVisualProbeNode)) for _ in range(2))
    edge = make_edge(graph, v1.node_id, "note", v2.node_id, "note")
    graph.force_validation()
    action = RemoveElementsAction(graph=graph, edges=[edge.edge_id])
    action.execute()
    action.undo()
    graph.force_validation()
    assert graph.get_edge_wrapper(edge.edge_id).is_valid()


def test_a_retyped_swinglet_keeps_both_edges(graph):  # Review Focus 1
    from haywire.barn.builtin.types import INT

    a, p, b = _add(graph), make_node(graph, _key(SwingletPassProbeNode)), _add(graph)
    e_in = make_edge(graph, a.node_id, "result", p.node_id, "s")
    e_out = make_edge(graph, p.node_id, "s", b.node_id, "value_a")
    graph.force_validation()
    with p.node.rejig(include=["s"]):
        p.node.add(INT.as_swinglet("s"))
    new = p.node.ports["s"]
    assert e_in._inlet_port is new and e_out._outlet_port is new
    assert e_in.edge_id in new.incoming.all and e_out.edge_id in new.outgoing.all
```

- [ ] **Step 2: Run; expect failures** on the swinglet as an outlet end (the old negative check refuses it), and on the reverse check.
  Run: `uv run pytest tests/core/test_edge/test_swinglet_links.py -q -p no:randomly`

- [ ] **Step 3: Implement.**
  - `_formal_validation` raises when `not self._outlet_port.is_outlet()` ("Outlet port … cannot be an edge's outlet end") or `not self._inlet_port.is_inlet()` (likewise).
  - `add_edge_wrapper`, after its duplicate-id check:

```python
reverse = generate_edge_uuid(
    edge_wrapper.sink_node_id, edge_wrapper.inlet_port_id,
    edge_wrapper.source_node_id, edge_wrapper.outlet_port_id,
)
if reverse in self.edge_wrappers:
    raise ValueError(f"Edge wrapper '{reverse}' already links these pins the other way")
```

- [ ] **Step 4: Run the tests; expect PASS. Run the pre-commit gate; expect green.**
- [ ] **Step 5: Ruff check, mypy, commit** (`feat(edges): a swinglet links at either end; one edge between two pins`).

---

### Task 4: Every edge lookup names its end

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py`: `_get_edge_wrappers_for_port` (682-692)
- Modify: `packages/haywire-core/src/haywire/core/assembly/flat_view.py`:
  - the override `_get_edge_wrappers_for_port` (~174-214);
  - the Subgraph Input lookup in `_interior_sinks` (~276).
- Modify: `packages/haywire-core/src/haywire/core/assembly/data_flow_builder.py`: `_backpropagate` (~120), `_check_cycles` (~179), `_topological_sort` (~242)
- Create: `tests/core/test_assembly/test_swinglet_assembly.py`

**Interfaces:**
- Produces: `_get_edge_wrappers_for_port(node_id: str, port_id: str, *, incoming: bool) -> list` on `BaseGraph` and `FlatGraphView` (Q109).
  - `incoming=True` returns the edges whose inlet end is this port; `incoming=False`, those whose outlet end is.
  - The keyword has no default, so every caller names the end.
  - `FlatGraphView` applies `_reroute_source` to the incoming edges only and appends `_interior_sinks` to the outgoing ones only.
  - Its comment about rewriting only an edge whose inlet end is the port becomes the `incoming` branch.

- [ ] **Step 1: Write the failing tests.** Use a shared helper, which Task 5 reuses:

```python
def _run_frame(graph) -> None:
    flows = FlowAssemblyManager().assemble_graph(graph)
    assert len(flows) == 1
    HaywireVM().execute_control_flow(flows[0], cast("Trigger", None))
```

Pattern: `tests/core/test_assembly/test_subgraph_execution_edges.py`. The tests:
  - `test_the_edge_lookup_names_its_end`: with `A.result → P.s` and `P.s → B.value_a`:
    - `graph._get_edge_wrappers_for_port(p.node_id, "s", incoming=True)` returns only `A→P`;
    - `incoming=False` returns only `P→B`.
  - `test_an_arriving_value_reaches_the_swinglets_worker`. The graph:
    - `TestBeginPlayNode.exec → TestPrintNode.exec`;
    - `Add(1, 2).result → StopProbe.s`;
    - `StopProbe.s → Add2.value_a`, with `Add2.value_b = 100`;
    - `Add2.result → Print.message`.

    Run one frame. Assert `stop.node.seen == [3.0]` and `add2.node.ports["result"].get_value() == 100.0`.
    Today this raises "Illegal cycle": the swinglet's incoming edge is read as one of its outgoing edges.
  - `test_control_passes_through_a_control_swinglet`:
    - `Begin.exec → C1.flow`, `C1.flow → C2.flow`; run one frame;
    - assert `c1.node.runs == 1` and `c2.node.runs == 1`.

- [ ] **Step 2: Run; expect failures.** The lookup takes no `incoming` yet, and the second test fails with `RuntimeError: Illegal cycle`.
- [ ] **Step 3: Implement.**
  - `BaseGraph`: the method keeps its two existing `if`s and returns only the branch the keyword names.
  - `FlatGraphView`: the override passes `incoming` to the owner graph's lookup, then splices per end as above.
  - The Input lookup at ~276 passes `incoming=False`; its `source_node_id` filter is then redundant and goes.
  - `DataFlowBuilder` passes `incoming=True` in `_backpropagate`, and `incoming=False` in `_check_cycles` and `_topological_sort`.
  - Confirm there are no other callers: `grep -rn "_get_edge_wrappers_for_port(" packages barn tests` lists only these sites and the new test.
- [ ] **Step 4: Run the new tests, `uv run pytest tests/core/test_assembly tests/core/test_graph -q -n 4`; expect PASS.** `test_flat_view.py` and `test_subgraph_execution_edges.py` prove the splices still order Groups.
- [ ] **Step 5: Ruff check, mypy, commit** (`refactor(assembly): every edge lookup names the end it means`).

---

### Task 5: Swinglet values: `_emit`, `out()` and the own-value pipe

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/port.py`:
  - `set_value`: the inlet branch clears `_is_set_by_node` only when `edge_id is None`. The immediate path at the top is an edge write, so it no longer clears it. The outlet branch shares its tail with `_emit` and no longer fires `on_change` (Q108).
  - new `_emit`, new `get_own_value`;
  - `set_value`'s docstring covers swinglets, and says `on_change` reports only what the port receives.
- Modify: `packages/haywire-core/src/haywire/core/types/interface.py`: `as_outlet` raises `ValueError("an outlet's on_change would never fire: only its own node writes it")` when `on_change` is given and not `None`. Its docstring drops `on_change` from the callbacks.
- Modify: `packages/haywire-core/src/haywire/core/node/data.py`: `out()` checks `is_outlet()` and calls `port._emit(value)`; its docstring covers swinglets.
- Modify: `packages/haywire-core/src/haywire/core/types/pipe.py`: `Pipe.pull` reads `self._outlet_port.get_own_value()`.
- Create: `tests/core/test_execution/test_swinglet_values.py`

**Interfaces:**
- Consumes: Task 4's `_run_frame` pattern; Task 1's probes.
- Produces:
  - `DataPort._emit(new_value: Any) -> None`: stores the own value, sets `_is_set_by_node`, runs the pipes. It fires no `on_change`.
  - `DataPort.get_own_value() -> Any`: `None` without a field.

- [ ] **Step 1: Write the failing tests.**
  - A factory fixture `chain(middle, lazy_in=False, lazy_out=False, with_feed=True)` builds the graph of Task 4's first test. It returns `(graph, a, p, b, e_in, s)`, where `p` is the `middle` probe, `s = p.node.ports["s"]`, and `e_in` is `None` without a feed.
  - `lazy_in`/`lazy_out` set `Propagation.LAZY` on `A→S`/`S→B`, then `graph.force_validation()`.
  - Port the tests from the spike's `tests/core/test_spike_swinglet.py` (in `.scratch/swinglet-spike/spike.diff`), reading the probe nodes' `seen` instead of the spike's module list.
  - The unit test reuses Task 1's `_port` helper.

```python
@pytest.mark.parametrize(("lazy_in", "lazy_out"), [(False, False), (True, False), (False, True), (True, True)])
def test_the_nodes_write_is_passed_on(graph, lazy_in, lazy_out):
    _run_frame(graph)
    assert p.node.seen == [3.0]
    assert b.node.ports["result"].get_value() == 130.0  # 3 * 10 + 100
    s = p.node.ports["s"]
    assert s.get_value() == 3.0 and s.get_own_value() == 30.0


def test_an_arriving_value_stops_at_the_swinglet(graph):  # stop probe, eager and lazy
    _run_frame(graph)
    assert b.node.ports["result"].get_value() == 100.0


def test_an_unfed_data_node_reads_its_own_last_write_when_it_runs_again(graph):  # no A→S
    s.set_value(1.0)  # a widget write marks the port dirty
    _run_frame(graph)
    _run_frame(graph)  # nothing dirty: a data node does not run again
    assert p.node.seen == [1.0]
    p.node.mark_port_as_dirty(s)
    _run_frame(graph)
    assert p.node.seen == [1.0, 10.0]
    assert b.node.ports["result"].get_value() == 200.0


def test_removing_the_feed_shows_the_nodes_last_write(graph):
    _run_frame(graph)
    graph.remove_edge_wrapper(e_in.edge_id)
    graph.force_validation()
    assert not s._data.has_linked_value()
    _run_frame(graph)
    assert p.node.seen == [3.0, 30.0]
    assert b.node.ports["result"].get_value() == 400.0


def test_an_arriving_value_keeps_the_node_set_mark(graph):
    _run_frame(graph)
    a.node.out("result", 5.0)
    assert s._is_set_by_node is True


def test_an_edge_write_to_an_immediate_swinglet_fires_immediately(monkeypatch):  # unit
    port = _port(CALLBACK, PortType.SWINGLET)
    fired = []
    monkeypatch.setattr(port, "_fire_immediate", lambda store, value: fired.append(value))
    port.set_value("sub", edge_id="e")
    assert fired == ["sub"]


def test_a_swinglet_round_trips_with_both_edges_and_its_own_value(graph):  # Review Focus 3
    _run_frame(graph)
    loaded = BaseGraph(filestem="g2", validation_scheduler=SyncScheduler())
    assert loaded.load_from_dict(graph.to_dict(include_data=True)) is True
    loaded.force_validation()
    s2 = loaded.get_node_wrapper(p.node_id).node.ports["s"]
    assert s2.get_own_value() == 30.0
    assert len(s2.incoming.linked) == 1 and len(s2.outgoing.linked) == 1


def test_on_change_reports_what_arrives_not_the_nodes_own_write(graph):  # Q108, echo probe as middle
    _run_frame(graph)
    assert p.node.changes == [3.0]  # once: the handler's own out() did not fire it again
    assert b.node.ports["result"].get_value() == 104.0  # (3 + 1) + 100


def test_an_outlet_refuses_on_change():  # unit
    with pytest.raises(ValueError, match="on_change"):
        FLOAT.as_outlet("o", on_change="hb_o")


def test_a_collapsed_swinglet_node_still_passes_its_write_on(graph):  # Review Focus 4
    CollapseToGraphNodeAction(
        graph=graph, node_ids=[p.node_id], card_registry_key=..., input_registry_key=...,
        output_registry_key=..., label="Group",
    ).execute()
    graph.force_validation()
    _run_frame(graph)
    assert b.node.ports["result"].get_value() == 130.0
```

  The collapse keys are as in `tests/core/test_graph/test_visual_wire_group.py`.

- [ ] **Step 2: Run; expect failures.** `out()` refuses a swinglet, the pipe reads the linked value, and `as_outlet` accepts `on_change`. The immediate test passes already; keep it as a guard.
- [ ] **Step 3: Implement as listed under Files.**
- [ ] **Step 4: Run the new tests, then the pre-commit gate; expect green.**
- [ ] **Step 5: Ruff check, mypy, commit** (`feat(ports): a swinglet passes on what its node writes, not what arrives`).

---

### Task 6: Reporting: inspector, Farmhand, Properties, generated docs

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/inspector.py:48-52`: `_port_direction` returns `"swinglet"` first
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`:
  - `_port_direction` (62-67) checks `is_swinglet()` first;
  - `PortInfo.direction` (214) uses `_port_direction`;
  - `_DIRECTIONS` (609) gains `"swinglet"`;
  - the bucket map (765) gains `"swinglet": "swinglets"`, and `groups` gains `"swinglets": []`;
  - a swinglet's port row (84 and 251, next to `takes_many_links`) adds `outgoing_takes_many` (Q114);
  - the tool's instructions name the new direction.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py:357-358`: inlets and outlets exclude swinglets, and a third lane `"swinglet"` is labelled "Swinglets"
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/docs/render.py:10`: `{"inlet": 0, "swinglet": 1, "config": 2, "outlet": 3}`
- Test: extend `tests/farmhand/test_graph_editor_tools.py`; new `tests/core/test_node/test_inspector_swinglet.py`; extend the introspection panel test that covers lanes (`codegraph explore "_render_lane node_ports"` names it)

- [ ] **Step 1: Write the failing tests.**
  - The inspector reports `"swinglet"` for a pass probe's `s`.
  - Farmhand `inspect_node` on a pass probe returns `ports == {"swinglets": [<row for s>]}`. `by_dir=["swinglet"]` keeps it, and `by_dir=["inlet"]` drops it.
  - On a control probe, the row for `flow` has `takes_many_links: True` and `outgoing_takes_many: False`. A pass probe's row has both keys; an Add node's inlet row has no `outgoing_takes_many`.
  - The introspection panel renders one row for `s`, under "Swinglets".
  - The docs table lists `inlet`, then `swinglet`, then `outlet` rows.
- [ ] **Step 2: Run; expect failures.** Today the inspector says `"inlet"`, and Farmhand files the port under inlets.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the touched test files; expect PASS.**
- [ ] **Step 5: Ruff check, mypy, commit** (`feat(reporting): name swinglets in the inspector, Farmhand, Properties and docs`).

---

### Task 7: Pin rendering and the studio skins

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/skin/pin_render.py`:
  - line 213: `pin_direction = "swinglet" if pin.is_swinglet() else "inlet" if pin.is_inlet() else "outlet"`;
  - ghosts unchanged.
- Modify: `packages/haywire-core/src/haywire/core/types/enums.py:135-141`: `side_for`/`vector_for` docstrings say a swinglet sits on the inlet side. The code is already right once `is_inlet()` includes it.
- Modify: `packages/haywire-core/src/haywire/ui/skin/pin_icons.py` (`_role` 94, `_declared` 100, `_from_map` 107, role docs 32-37), Q115:
  - the direction segment is `swing` for a swinglet;
  - `_declared` uses `icon_in`/`icon_in_multi` for a swinglet;
  - `ICONS` gains `data_swing` and `compound_swing` (`ICONS.RADIO_BUTTON_CHECKED`), `control_swing` (`ICONS.JOIN_INNER`) and `callback_swing` (`ICONS.SWAP_HORIZ`).
- Modify: `packages/haywire-core/src/haywire/ui/themes/icons.py`: `JOIN_INNER = "join_inner"`, `SWAP_HORIZ = "swap_horiz"`.
- Modify: `barn/haybale-studio/haybale_studio/skins/split_skin.py:111-112,159-160` and `error_skin.py:116-117`: the outlet lists use `p.is_outlet() and not p.is_swinglet()`.
- Modify: `barn/haybale-studio/haybale_studio/skins/stacked_skin.py` (94-95, 185, 236, 272): compare against a lane `PortType.INLET if p.is_swinglet() else p.port_type`.
- Test:
  - `tests/ui/skin/test_pin_render_layout.py` (add a swinglet to `simple_ports`), `test_pin_icon_resolution.py`;
  - `tests/core/test_types/test_layout_direction.py` (its `_FakePort` gains `is_swinglet()`);
  - a new harness route `/graph-swinglet-skins` in `tests/ui/harness/routes.py` with one pass probe per skin (node, split, stacked, error; skin keys from each class's `class_identity.registry_key`), and `tests/ui/harness/test_swinglet_skins.py`.

- [ ] **Step 1: Write the failing tests.**
  - A swinglet's pin carries `data-pin-dir="swinglet"`.
  - `LayoutDirection.LEFT_TO_RIGHT.side_for(swinglet) == "left"`, and `vector_for` is the inlet vector.
  - Glyphs: a `FLOAT` swinglet draws `radio_button_checked`, an `EXEC` one `join_inner`, a `CALLBACK` one `swap_horiz`. A swinglet whose kind has no map entry resolves `annotation_swing`, then `annotation`, then the fallback.
  - Browser test: each skin's card has exactly one `[data-pin-id="s"]`, on the card's inlet side.
- [ ] **Step 2: Run; expect failures** (the attribute says `"inlet"`; the split and error skins draw two pins; the stacked skin draws none).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the unit tests, then `uv run pytest tests/ui/harness/test_swinglet_skins.py -m browser -q`; expect PASS.** Look at the three glyphs on a card in the browser; if a Material icon name doesn't render, pick a neighbour and record it in the design's Q115.
- [ ] **Step 5: Ruff check, mypy, commit** (`feat(skins): draw a swinglet once, with its own direction and glyph`).

---

### Task 8: Canvas: swinglet drags, duplicates in either order, reconnect roles, auto-wire

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`:
  - the contract comment (84-97) documents `data-pin-dir` (`inlet`|`outlet`|`swinglet`);
  - `_isValidEdge` (3823-3838);
  - the drop commit (2749-2762) uses `_orientEdge`;
  - `_edgeExists` (3878) checks both orders on every drop (Q112);
  - `_rebuildPinIndex` (2790) stores `dir`;
  - suggestion paths (2869, 2893-2900) take the target's own vector;
  - `_syncEdgeReconnect` (1489) stores `anchorEnd`, and `_returnToIdleEdge` clears it.
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py`:
  - `SyncEdgeReconnectEvent` gains `anchorEnd: str`;
  - the `pendingPinDir` comment (371) lists `'swinglet'`.
  - `generated/graph_events.js` lists event names only, so it is not regenerated.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py`:
  - `_reconnect_anchor` returns `(node_id, port_id, end)`, where `end` is `"outlet"` for the source and `"inlet"` for the sink;
  - `reconnect_active_edge` and `can_reconnect_active_edge` follow.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py:1065-1107`: `as_outlet = pending_pin_dir in ("outlet", "swinglet")` decides both the target direction and the edge order.
- Test:
  - new route `/graph-swinglet` in `tests/ui/harness/routes.py`: three `SwingletVisualProbeNode`s, two `SwingletPassProbeNode`s and one `TestAddFloatNode`;
  - new `tests/ui/harness/test_graph_swinglet_connect.py`, after `tests/ui/harness/test_graph_connect.py`;
  - extend `tests/ui/graph_canvas/test_session_context_menu_provider.py` (the anchor end) and `tests/ui/test_canvas_handlers/test_visual_layer_auto_wire.py` (a `"swinglet"` pending direction).

**Interfaces:**
- Consumes: Task 7's `data-pin-dir="swinglet"`; Task 3's server-side reverse check (the canvas check only spares the round trip and the error notice).

- [ ] **Step 1: Write the failing tests.**
  - Browser:
    - `test_a_drag_between_two_swinglets_follows_the_drag_order` (V1→V2 gives source V1);
    - `test_a_drag_from_an_inlet_to_a_swinglet_makes_the_swinglet_the_outlet_end` (Add.value_a ← P.s);
    - `test_a_reverse_drag_is_ignored` (after V1→V2, a drag V2→V1 leaves one edge and shows no error notice);
    - `test_reconnecting_the_outlet_end_of_a_swinglet_edge_keeps_its_direction` (reconnect V1→V2 at V1 onto V3: the result is V3→V2, not V2→V3).
  - Python:
    - `_reconnect_anchor` returns `"inlet"` when the outlet end was clicked;
    - auto-wire from a pending `"swinglet"` connects the pending pin as the outlet end.
- [ ] **Step 2: Run; expect failures.**
- [ ] **Step 3: Implement.** `_isValidEdge` accepts a pair where one end can send and the other can receive, in either order. The drop orientation:

```js
/** [outletEndPin, inletEndPin] for a drop. A pure inlet or outlet decides; between two
 *  swinglets the drag order does, unless a reconnect keeps the anchor's role. */
_orientEdge(startPin, endPin) {
    const s = startPin.dataset.pinDir, e = endPin.dataset.pinDir;
    if (s === 'swinglet' && e === 'swinglet') {
        return this.edgeDrag.anchorEnd === 'inlet' ? [endPin, startPin] : [startPin, endPin];
    }
    return (s === 'inlet' || e === 'outlet') ? [endPin, startPin] : [startPin, endPin];
},
```

  `_edgeExists(src, outPin, snk, inPin)` is true when `_buildEdgeID` in either order is in `edgePaths`.

- [ ] **Step 4: Run the new browser and Python tests, then `uv run pytest tests/ui/harness/test_graph_connect.py tests/ui/harness/test_graph_reconnect.py -m browser -q`; expect PASS.**
- [ ] **Step 5: Check by hand in a browser** (`haywire-live-studio` skill):
  - a drag between two swinglets on differently facing sides draws a suggestion curve that leaves each pin outward;
  - drawn edges stay attached after zoom.
- [ ] **Step 6: Ruff check, mypy, commit** (`feat(canvas): swinglet drags, duplicates in either order, reconnect roles`).

---

### Task 9: The annotation node and skin on swinglets, pins centred

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/annotation.py`:
  - `init` adds one `ADD[ANNOTATION]` swinglet slot per side, `{side}_0`;
  - `_parse` returns `(side, index)`;
  - `_grow` re-adds the connected slot as `ANNOTATION.as_swinglet(..., origin=PortOrigin.RESOLVED)`, then opens `{side}_{next}`;
  - `_next_index(side)`;
  - `_add_slot(side, index, itype, origin=None)` uses `as_swinglet` with `label=f"{side.title()} {index}"`;
  - the displayed docstring says one pin per side, centred, any pin to any pin.
- Modify: `packages/haywire-core/src/haywire/barn/builtin/skins/annotation_skin.py`:
  - `_LAYOUT: dict[str, LayoutDirection]` is `{"left": L2R, "right": R2L, "top": T2B, "bottom": B2T}`;
  - `_parse` matches the node's;
  - `_pins_by_side` lists the control pins, then grown pins by index, then the side's slot;
  - the strip uses `justify-content: center`, and the slot sits in a zero-width wrapper after the last pin (C11);
  - ghosts get their own wrapper per side, rendered before the strip;
  - the module docstring is updated.
- Modify tests:
  - `tests/core/test_node/test_annotation_node.py`: four slots, growth per side, indices never reused;
  - `tests/ui/skin/test_annotation_skin.py`;
  - `tests/ui/harness/routes.py`: `_build_annotation_graph` and `_linked_edge` use `right_0` → `left_0`;
  - `tests/ui/harness/test_annotation_node.py`;
  - `tests/farmhand/test_graph_editor_tools.py:233-235`;
  - `tests/ui/harness/test_graph_reconnect.py` (annotation ids).
- Create: `tests/core/test_graph/test_annotation_links.py`
- Regenerate: the builtin library's generated docs (`uv run haywire docs --all`; commit only the builtin's changed files).

- [ ] **Step 1: Write the failing tests.**
  - Core, in `test_annotation_links.py`, all integration:
    - `test_any_side_links_to_any_side`: `right_0 → top_0`, `left_0 → left_0` and `bottom_0 → right_0` are all valid, and each connected slot grows `{side}_1`.
    - `test_a_reverse_note_link_is_refused`.
    - `test_collapsing_across_note_links_keeps_them` (C1): three notes chained; collapse the middle one; every edge in host and interior is valid; undo restores the chain. Mirrors `tests/core/test_graph/test_visual_wire_group.py`.
    - `test_pasting_two_linked_notes_keeps_their_link` (Review Focus 5): copy two linked notes through the clipboard path the paste action uses (`codegraph explore "PasteAction clipboard"`); the paste adds one new valid edge between the new notes.
    - `test_a_reroute_splits_a_note_link`: `SplitEdgeWithRerouteAction` on `right_0 → left_0` (reroute key from `RerouteNode.class_identity.registry_key`) leaves two valid edges on the annotation wire. The spike confirmed this on 5.5's slots; this pins it on swinglets.
  - Browser, in `tests/ui/harness/test_annotation_node.py`:
    - `test_a_sides_pins_are_centred`: with two grown pins on `right`, their centres' midpoint is within 1 px of the card's vertical centre, and the hidden slot overlaps neither;
    - `test_a_lone_slot_is_centred`: a side with no pins shows its slot, on hover, at the side's centre;
    - `test_hovering_does_not_move_pins`: pin rectangles are equal before and after hover.
- [ ] **Step 2: Run; expect failures** (old port ids, `space-evenly`).
- [ ] **Step 3: Implement.** Keep `visibility` as the reveal mechanism (`hw-pin-reveal`); never `display: none`.
- [ ] **Step 4: Run the touched core, skin and browser tests; expect PASS.** Regenerate the docs and check `git status` lists only builtin doc files.
- [ ] **Step 5: Check by hand in a browser:**
  - two notes;
  - links between all four side pairs;
  - an arrow head at the drop end;
  - re-dragging an end keeps the head where it was;
  - pins stay centred as links are added and removed.
- [ ] **Step 6: Ruff check, mypy, commit** (`feat(annotation): one swinglet set per side, centred`).

---

### Task 10: Documentation

**Files:**
- Modify: `docs/reference/glossary.md`:
  - **swinglet**: a port that may be either end of an edge; values per Q100, Q107 and Q108;
  - **link set**: `LinkSet`, a port's incoming or outgoing edges, each with its own link ceiling.
- Create: `docs/adr/0048-swinglets.md`:
  - context: annotation notes, and why direction was the blocker;
  - decision: Q95 to Q117;
  - consequences:
    - no new hot-path branch;
    - an older build cannot initialise a node with a swinglet;
    - a data node re-reads its own write only when it runs again;
    - one edge between two pins, for every wire;
    - `on_change` reports only what a node receives, and an outlet refuses one.
- Modify: `docs/guides/ports.md`:
  - a "Swinglets" section with `as_swinglet` and its defaults;
  - the four value rules: an arriving value stops, `out()` passes on, the pipe reads the own value, an unfed swinglet reads its own last write when its node next runs;
  - `out("x", value("x") + 1)` as one pattern, explained from those rules, and `on_change` for reacting only to what arrives (Q107);
  - the link ceilings per end;
  - in the outlet section, that an outlet takes no `on_change` (Q108).
- Modify: `docs/components/skins/skin-canon.md`: the annotation section describes centred pins, one swinglet set per side, and `_LAYOUT[side]`.
- Modify: `docs/superpowers/plans/2026-10-05-diagram-annotations.md` status (do not commit it).

- [ ] **Step 1: Write the four docs.** Link the ADR from the glossary entries and from `ports.md`. Follow `docs/reference/doc-authoring.md` (front matter, nav).
- [ ] **Step 2: `uv run mkdocs build --strict` passes.**
- [ ] **Step 3: Commit** (`docs: swinglets — glossary, ADR 0048, ports guide, skin canon`).

---

### Task 11: Final verification (controller)

- [ ] **Step 1:** Pre-commit gate, browser tier, visiongraph tests, mypy set, and `uv run ruff check . && uv run ruff format --check .`. Compare the counts with Task 0's in `.superpowers/sdd/progress.md`; every difference must be a test this plan added.
- [ ] **Step 2: Benchmark.** Run the `haywire-benchmark` skill. Any case marked ↑ (regressed) beyond its noise against Task 0's baseline is a stop: report it before merging.
- [ ] **Step 3: Live check with the user.** Studio up (`haywire-live-studio`):
  - draw notes, link all side pairs, set heads and colours;
  - collapse a note chain into a Group and expand it;
  - save, reload, undo.

  Record the result in the design doc.
- [ ] **Step 4: Whole-branch review** (`requesting-code-review`) against this plan and the design. Then hand over to the user for squash and merge (design "Next" step 3).

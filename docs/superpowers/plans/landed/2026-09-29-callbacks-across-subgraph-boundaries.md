# Callbacks Across Subgraph Boundaries (Edge Kinds, Step 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` (inline) or `subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A callback subscription crosses a Group or macro boundary in both directions — a listener outside feeding an emitter inside, and a listener inside feeding an emitter outside — through collapse, slot growth, expand, Promote to Macro, a macro reload and nested Groups; unlinking on either side unsubscribes.

**Architecture:** Every immediate interface pair relays at wiring time, the way a reroute does: the card's immediate inlet writes the Subgraph Input's outlet, the Subgraph Output's immediate inlet writes the card's outlet, each from an `on_change` handler on its own node that finds its partner by id (`subgraph_crossing`). `reconcile_interface` ends by copying every immediate pair once, which covers load order and a rebuilt interior. The execution-time copy keeps deferred pairs only. A bare `ADD` accepts an edge of any flow, so a boundary slot grows control and callback ports. A graph tree validates one batch at a time because a Subgraph shares its host's validation lock.

**Tech Stack:** Python 3.12, NiceGUI + Vue (canvas), pytest (+ xdist), uv, ruff, mypy, mkdocs.

**Settled in:** the inquisition of 2026-09-29 (Q1–Q10). Sequence: [2026-09-28-edge-kinds.md](2026-09-28-edge-kinds.md) step 4. Builds on ADR 0039 (propagation), ADR 0040 (unlinking reveals the own value) and step 3 (`NodeWrapper._locked`).

## Global Constraints

- Work on branch `unlink-own-value` (the user's choice: steps 2–4 on one branch). Every commit message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Decisions to honour: 1A/8A — every bare `ADD` accepts any flow, so the slot grows control and callback ports; 2A — both directions, Groups and macros, every source of an interface port; 3A — `on_change` relay on each side's own node, partner resolved by id per call, no cache; Q4 note — relay and resync are keyed on `port.is_immediate`, not on `CALLBACK`; 4A — `reconcile_interface` ends with one resync of every immediate pair; 5A — a graph tree validates one batch at a time; 6A — collapse/expand churn accepted; 7A — the execution-time copy leaves immediate pairs out; 9A — one subscription per interface port; 10A — new ADR 0041, ADR 0036 superseded in part.
- **5A refinement (flag to the user when reporting):** the inquisition proposed a run lock on `ThreadingTimerScheduler`. `force_immediate_validation()` bypasses schedulers and tests call it on timer graphs, so a scheduler lock leaves a gap. This plan makes a Subgraph share its host's validation **lock** instead (`BaseGraph._share_validation_lock`): every batch of a tree — scheduled or forced, any thread — serializes on one `RLock`, and host ↔ Subgraph nesting becomes re-entrant. Same decision, stronger mechanism. No scheduler changes.
- **Found during planning, fixed here:** collapse and `hb_grow` seed an interface port's default from the interior port. A listener's outlet declares `default=self.node_id`, so an outward callback interface inlet would hold the listener's name as its *own* value and relay it after the interior edge is removed — a stale subscription. Immediate interface ports take no seeded default (Tasks 3 and 6).
- Out of scope: card-side growth (ADR 0036), pooled interface ports (9A), smoothing collapse churn (6A), EdgeKind (step 5).
- Glossary, ADR and architecture-doc edits land in Task 9, with the code.
- Docstrings and comments follow `.claude/rules/python-docs.md`; class docstrings of registered components (types, nodes) are displayed Markdown.
- Node registry keys in tests come from constants already used in the test suite (`haybale-testing:node:TestCustomCallbackNode`, `…:TestEmitCallbackNode`, `haywire-core:node:SubgraphInputNode`/`SubgraphOutputNode`/`GraphNode`), which existing tests prove resolve.
- Commit every change under `barn/haybale-testing/` before running the full suite (the docs test reverts that directory).
- "Ruff check" means `uv run ruff check <path>` and `uv run ruff format --check <path>`; line length 109. Pre-commit gate: `uv run pytest -m "not browser and not perf" -n 4`.
- A failing test outside the files a task names: stop and report it by name.

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `packages/haywire-core/src/haywire/core/graph/validation.py` | `ValidationManager.share_lock` | 1 |
| `packages/haywire-core/src/haywire/core/graph/base.py` | `add_subgraph` shares the host's lock; `_share_validation_lock`; `create_edge_wrapper` edge flow | 1, 2 |
| `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` | bare-`ADD` flow wildcard; `edge_flow_type` | 2 |
| `packages/haywire-core/src/haywire/ui/skin/pin_render.py`, `ui/components/graph/canvas.vue` | `data-pin-any-flow`; drag check | 2 |
| `packages/haywire-core/src/haywire/barn/builtin/types/add.py` | `ADD` docstring | 2 |
| `packages/haywire-core/src/haywire/core/graph/subgraph_crossing.py` | `RELAY_HANDLER` | 3 |
| `packages/haywire-core/src/haywire/barn/builtin/nodes/subgraph_io.py` | `SubgraphOutputNode.hb_relay`; `hb_grow` relay + default; deferred-only pairs | 3, 5 |
| `packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py` | `GraphNode.hb_relay`; `_mirror` relay; resync; deferred-only inward pairs | 3, 4, 5 |
| `packages/haywire-core/src/haywire/core/graph/subgraph_collapse.py` | no seeded default for immediate ports | 6 |
| `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` | stamp relay on immediate Output inlets; refusal removed | 6 |
| `tests/core/test_graph/callback_group.py` (helper, create) | build a Group with callback interface ports | 3–5 |
| tests (create): `test_tree_validation_lock.py`, `test_any_flow_slot.py`, `test_callback_boundary_relay.py`, `test_callback_resync.py`, `test_immediate_pairs_not_copied.py`; `tests/core/test_undo/test_collapse_callback_crossing.py` (replaces `test_collapse_callback_refusal.py`); `tests/core/test_macro/test_macro_callback_interface.py`; `tests/ui/skin/test_pin_any_flow.py` | acceptance | 1–8 |
| docs | ADR 0041, ADR 0036 note, glossary, callbacks-arch, graph-arch, node-canon, insight, overview | 9 |

---

### Task 0: Baseline

- [ ] **Step 1:** `git branch --show-current` → `unlink-own-value`; `git status --short` → empty.
- [ ] **Step 2:** Lint and types for the areas this plan touches:

```bash
uv run ruff check packages/haywire-core/src/haywire tests/core tests/ui/skin
uv run ruff format --check packages/haywire-core/src/haywire tests/core tests/ui/skin
uv run mypy packages/haywire-core/src/ tests/
```

Expected: clean. Otherwise stop and raise it with the user.

- [ ] **Step 3:** `uv run pytest tests/core/test_undo/test_collapse_callback_refusal.py tests/core/test_edge/test_disconnect_semantics.py -q -p no:randomly` → all pass (the refusal tests describe today's behaviour; Task 6 replaces them).

---

### Task 1: A graph tree validates one batch at a time

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/validation.py` (new `share_lock` after `adopt_scheduler`)
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py` (`add_subgraph`; new `_share_validation_lock`)
- Modify: `.insights/project_subgraph_scheduler_deadlock.md` (cross-graph paragraph)
- Test: `tests/core/test_graph/test_tree_validation_lock.py` (create)

**Interfaces:**
- Produces: `ValidationManager.share_lock(lock) -> None`; `BaseGraph._share_validation_lock(lock) -> None` (recursive over `subgraphs`); after `add_subgraph`, `definition._validation.lock is host._validation.lock` for the definition and every definition nested in it.

- [ ] **Step 1: Write the failing tests**

```python
"""Every graph of one tree validates under one lock, so a host and its Subgraphs never validate at once."""

import threading
import time

import pytest

from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.graph.types import ChangeReason

pytestmark = pytest.mark.integration


def test_a_subgraph_validates_under_its_hosts_lock(graph_with_library_system):
    graph = graph_with_library_system

    definition = graph.add_subgraph(SubgraphDefinition(key="sg_lock", label="G"))

    assert definition._validation.lock is graph._validation.lock


def test_a_nested_subgraph_added_first_shares_the_roots_lock(graph_with_library_system):
    graph = graph_with_library_system
    outer = SubgraphDefinition(key="sg_outer", label="Outer")
    inner = outer.add_subgraph(SubgraphDefinition(key="sg_inner", label="Inner"))

    graph.add_subgraph(outer)

    assert inner._validation.lock is graph._validation.lock


def test_a_subgraph_batch_waits_while_its_host_validates(graph_with_library_system):
    graph = graph_with_library_system
    definition = graph.add_subgraph(SubgraphDefinition(key="sg_wait", label="G"))
    worker = threading.Thread(
        target=lambda: definition._validation.mark_graph_dirty(ChangeReason.GRAPH_REQUIRE_REASSEMBLY),
        daemon=True,
    )

    with graph._validation.lock:
        worker.start()
        time.sleep(0.2)
        assert worker.is_alive(), "the Subgraph marked itself dirty while its host held the lock"
    worker.join(timeout=10)

    assert not worker.is_alive()
```

- [ ] **Step 2:** Run `uv run pytest tests/core/test_graph/test_tree_validation_lock.py -q -p no:randomly` → the first two FAIL (`is` false), the third FAILS (`worker.is_alive()` false).

- [ ] **Step 3: `ValidationManager.share_lock`** — in `validation.py`, after `adopt_scheduler`, add:

```python
    def share_lock(self, lock: "threading.RLock") -> None:
        """Validate under ``lock`` from now on: the lock of the graph tree this graph joins.

        Graphs of one tree then validate one batch at a time, whatever thread
        runs it, so a Subgraph and its host may reach into each other inside a
        batch without a lock-order rule between them. Call it before this
        manager's lock is in use.
        """
        self._validation_lock = lock
```

- [ ] **Step 4: `add_subgraph` shares the lock** — in `base.py` `add_subgraph`, after `definition._validation.adopt_scheduler(self.validation_scheduler)`, add `definition._share_validation_lock(self._validation.lock)`, and in its docstring after the paragraph ending "`that deadlocks.`" add:

```
        It also validates under this graph's lock from now on, so the whole tree
        runs one batch at a time; see ``ValidationManager.share_lock``.
```

Add after `add_subgraph`:

```python
    def _share_validation_lock(self, lock: "threading.RLock") -> None:
        """Validate this graph and every Subgraph nested in it under ``lock``."""
        self._validation.share_lock(lock)
        for definition in self.subgraphs.values():
            definition._share_validation_lock(lock)
```

(`base.py` imports `threading` if it does not yet; check with `grep -n "^import threading" base.py`, or quote the annotation, which it already is.)

- [ ] **Step 5: The insight** — in `.insights/project_subgraph_scheduler_deadlock.md`, replace the paragraph starting `**Across graphs the order is Subgraph before host.**` with:

```markdown
**Across graphs: one lock per tree.** A Subgraph validates under its host's
validation lock (`add_subgraph` → `BaseGraph._share_validation_lock`), so every
batch of a graph tree — scheduled or forced, on any thread — runs one at a
time, and a Subgraph batch reaching the host through the card (or the host's
reaching in through a callback relay, edge-kinds step 4) re-enters a lock its
thread already holds. The node-lock rule above is unchanged: the (shared)
validation lock first, then a node's.
```

- [ ] **Step 6:** Run `uv run pytest tests/core/test_graph/ tests/core/test_node/ tests/core/test_undo/ tests/core/test_macro/ -m "not browser and not perf" -n 4 -q -p no:randomly` → PASS.

- [ ] **Step 7:** Ruff, mypy on the touched files; commit `feat(graph): a graph tree validates under one lock`.

---

### Task 2: A bare `ADD` accepts any flow

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` (module helpers; `_formal_validation` flow check at ~741)
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py` (`create_edge_wrapper`, ~606)
- Modify: `packages/haywire-core/src/haywire/ui/skin/pin_render.py` (`common_props`, ~219)
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` (`_isValidEdge`, ~3646)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/add.py` (`ADD` class docstring)
- Test: `tests/core/test_graph/test_any_flow_slot.py`, `tests/ui/skin/test_pin_any_flow.py` (create)

**Interfaces:**
- Produces: `edge_flow_type(outlet, inlet) -> FlowType` in `edge_wrapper.py` — the outlet's flow unless the outlet is a bare `ADD`, then the inlet's; formal validation accepts a flow mismatch when either end is a bare `ADD`; a bare `ADD` pin renders `data-pin-any-flow="true"`, and the canvas accepts such a pin against any flow.

- [ ] **Step 1: Failing tests** — `tests/core/test_graph/test_any_flow_slot.py`:

```python
"""A boundary node's growing slot grows a port of whatever flow connects to it (ADR 0041)."""

import pytest

from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.types import FlowType, Propagation

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_LISTEN = "haybale-testing:node:TestCustomCallbackNode"
_EMIT = "haybale-testing:node:TestEmitCallbackNode"
_BEGIN = "haybale-testing:node:TestBeginPlayNode"


def _slot(wrapper):
    return next(p for p in wrapper.node.ports.values() if p.id.startswith("slot_"))


@pytest.fixture
def definition(graph_with_library_system):
    return graph_with_library_system.add_subgraph(SubgraphDefinition(key="sg_any", label="G"))


def test_a_control_edge_into_the_output_slot_grows_a_control_inlet(definition):
    output_node = make_node(definition, _OUTPUT)
    begin = make_node(definition, _BEGIN)
    slot = _slot(output_node)

    edge = definition.create_edge_wrapper(begin.node_id, "exec", output_node.node_id, slot.id)
    definition.force_validation()

    assert edge.state.is_valid()
    assert output_node.node.ports[slot.id].flow_type is FlowType.CONTROL


def test_a_callback_edge_into_the_output_slot_grows_a_callback_inlet(definition):
    output_node = make_node(definition, _OUTPUT)
    listener = make_node(definition, _LISTEN)
    slot = _slot(output_node)

    edge = definition.create_edge_wrapper(listener.node_id, "listen_callback", output_node.node_id, slot.id)
    definition.force_validation()

    assert edge.state.is_valid()
    assert output_node.node.ports[slot.id].flow_type is FlowType.CALLBACK


def test_an_edge_out_of_the_input_slot_takes_the_inlets_flow(definition):
    input_node = make_node(definition, _INPUT)
    emitter = make_node(definition, _EMIT)
    slot = _slot(input_node)

    edge = definition.create_edge_wrapper(input_node.node_id, slot.id, emitter.node_id, "edge_callback")
    definition.force_validation()

    assert edge.edge_type is FlowType.CALLBACK
    assert edge.propagation is Propagation.IMMEDIATE
    assert input_node.node.ports[slot.id].flow_type is FlowType.CALLBACK
```

`tests/ui/skin/test_pin_any_flow.py`:

```python
"""A bare ADD pin tells the canvas it accepts any flow."""

import pytest

from haywire.barn.builtin.types import ADD, FLOAT
from haywire.core.types import DataPort, FlowType, PortType
from haywire.ui.skin.pin_render import render_pin

pytestmark = pytest.mark.unit


def _port(type_cls) -> DataPort:
    return DataPort(
        registry_id="p",
        registry_key=type_cls.class_identity.registry_key,
        label="P",
        id="p",
        type_cls=type_cls,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
    )


def _render(port):
    return render_pin(port, "node-1", pin_gutter=20, card_padding=16, pin_protrusion=0)


def test_a_bare_add_pin_accepts_any_flow(nicegui_slot_context):
    assert _render(_port(ADD))._props.get("data-pin-any-flow") == "true"


def test_a_typed_pin_does_not(nicegui_slot_context):
    assert "data-pin-any-flow" not in _render(_port(FLOAT))._props
```

- [ ] **Step 2:** Run both files → the three growth tests FAIL (edge invalid / flow unchanged), `test_a_bare_add_pin_accepts_any_flow` FAILS.

- [ ] **Step 3: The wildcard in `edge_wrapper.py`** — add at module level, before `class EdgeWrapper`:

```python
def _accepts_any_flow(port: "DataPort") -> bool:
    """True for a bare ``ADD`` pin, which grows a port of whatever flow connects to it."""
    return port.type_cls is not None and port.type_cls._is_any


def edge_flow_type(outlet: "DataPort", inlet: "DataPort") -> FlowType:
    """Return the flow an edge between ``outlet`` and ``inlet`` carries.

    The outlet's flow, unless the outlet is a bare ``ADD``: then the inlet's,
    so an edge out of a boundary node's growing slot is typed by what it feeds.
    """
    return inlet.flow_type if _accepts_any_flow(outlet) else outlet.flow_type
```

In `_formal_validation`, replace

```python
            if self._outlet_port.flow_type != self._inlet_port.flow_type:
```

with

```python
            if self._outlet_port.flow_type != self._inlet_port.flow_type and not (
                _accepts_any_flow(self._outlet_port) or _accepts_any_flow(self._inlet_port)
            ):
```

(`DataPort` is under `TYPE_CHECKING` in this module already, as `_outlet_port`'s annotation shows; keep the quoted annotations.)

- [ ] **Step 4: `create_edge_wrapper`** — in `base.py`, replace

```python
        flow_type = self.node_wrappers[source_node_id].node.ports[outlet_port_id].flow_type
```

with

```python
        from ..edge.edge_wrapper import edge_flow_type

        outlet = self.node_wrappers[source_node_id].node.ports[outlet_port_id]
        sink = self.node_wrappers.get(sink_node_id)
        inlet = sink.node.ports.get(inlet_port_id) if sink is not None else None
        flow_type = edge_flow_type(outlet, inlet) if inlet is not None else outlet.flow_type
```

and drop the now-duplicate `from ..edge.edge_wrapper import EdgeWrapper` only if ruff flags it (keep one import line: `from ..edge.edge_wrapper import EdgeWrapper, edge_flow_type`).

- [ ] **Step 5: The canvas** — in `pin_render.py`, replace

```python
        f'data-hw-layout="{layout.value}"'
    )
```

with

```python
        f'data-hw-layout="{layout.value}"'
        # A bare ADD grows a port of any flow, so the canvas lets any pin connect to it.
        + (' data-pin-any-flow="true"' if pin.type_cls is not None and pin.type_cls._is_any else "")
    )
```

In `canvas.vue` `_isValidEdge`, replace

```js
            // Ghost pins are flow-type agnostic — they accept any connection type.
            const eitherIsGhost = startFlowType === 'ghost' || endFlowType === 'ghost';
            if (!eitherIsGhost && startFlowType !== endFlowType) {
```

with

```js
            // Ghost pins and bare ADD pins are flow-type agnostic — they accept any connection type.
            const eitherIsGhost = startFlowType === 'ghost' || endFlowType === 'ghost';
            const eitherTakesAnyFlow =
                startPin.dataset.pinAnyFlow === 'true' || endPin.dataset.pinAnyFlow === 'true';
            if (!eitherIsGhost && !eitherTakesAnyFlow && startFlowType !== endFlowType) {
```

- [ ] **Step 6: `ADD`'s docstring** — in `add.py`, after the paragraph ending `both resolve once either connects to something concrete.` add:

```
    A bare `ADD` accepts an edge of any flow — data, control or callback — and
    the edge carries the other end's flow, so a pin grown from it can be any
    of them. A typed `ADD[T]` keeps `T`'s flow.
```

- [ ] **Step 7:** Run `uv run pytest tests/core/test_graph/test_any_flow_slot.py tests/ui/skin/ tests/core/test_types/test_add_type.py -q -p no:randomly -n 4` → PASS. `tests/core/test_undo/test_collapse_callback_refusal.py::TestNoCallbackInterfacePortIsEverMinted` now FAILS — expected; Task 6 replaces that file. Delete just that class now so the suite stays green (Task 6 rewrites the rest).

- [ ] **Step 8:** Ruff, mypy; commit `feat(types): a bare ADD accepts any flow, so a boundary slot grows control and callback ports`.

---

### Task 3: The relay across the card

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/subgraph_crossing.py` (`RELAY_HANDLER`)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/subgraph_io.py` (`SubgraphOutputNode.hb_relay`; `hb_grow` kwargs)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py` (`_mirror`; `GraphNode.hb_relay`)
- Create: `tests/core/test_graph/callback_group.py` (helper)
- Test: `tests/core/test_graph/test_callback_boundary_relay.py` (create)

**Interfaces:**
- Produces: `RELAY_HANDLER = "hb_relay"`; `GraphNode.hb_relay(port, value)` writes the Subgraph Input's matching outlet; `SubgraphOutputNode.hb_relay(port, value)` writes the card's matching outlet; the card's immediate inlets and a grown immediate Subgraph Output inlet carry `on_change=RELAY_HANDLER`; a grown immediate port takes no seeded default.
- Consumed by Task 6 (`_build_boundary` stamps `RELAY_HANDLER`).

- [ ] **Step 1: The helper** — `tests/core/test_graph/callback_group.py`:

```python
"""A Group whose interface carries callback ports, for the edge-kinds step 4 tests.

The interface is stamped the way collapse stamps it: `sub_in` on the Subgraph
Input (card pin `in_sub_in`) and `sub_out` on the Subgraph Output (card pin
`out_sub_out`), both `CALLBACK` and `RESOLVED`, the Output's inlet relaying.
"""

from dataclasses import dataclass
from typing import Any

from tests.conftest import make_node

LISTEN = "haybale-testing:node:TestCustomCallbackNode"
EMIT = "haybale-testing:node:TestEmitCallbackNode"
INPUT = "haywire-core:node:SubgraphInputNode"
OUTPUT = "haywire-core:node:SubgraphOutputNode"
CARD = "haywire-core:node:GraphNode"


@dataclass
class CallbackGroup:
    graph: Any
    definition: Any
    input_node: Any
    output_node: Any
    card: Any | None = None


def subscriptions(emitter) -> list:
    """The event names an emit node would emit to."""
    return list(emitter.node.ports["edge_callback"].get_value().values())


def build_interior(graph, key: str = "sg_cb") -> CallbackGroup:
    """A Subgraph with one callback port on each boundary node, and no card yet."""
    from haywire.barn.builtin.types import FLOAT  # noqa: F401 — types load with the library system
    from haybale_core.types import CALLBACK
    from haywire.core.graph.subgraph import SubgraphDefinition
    from haywire.core.graph.subgraph_crossing import RELAY_HANDLER
    from haywire.core.types.enums import PortOrigin

    definition = graph.add_subgraph(SubgraphDefinition(key=key, label="Group"))
    input_node = make_node(definition, INPUT)
    output_node = make_node(definition, OUTPUT)
    with input_node.node.rejig(exclude=[PortOrigin.DECLARED]):
        input_node.node.add(CALLBACK.as_outlet("sub_in", label="Sub in", origin=PortOrigin.RESOLVED))
    with output_node.node.rejig(exclude=[PortOrigin.DECLARED]):
        output_node.node.add(
            CALLBACK.as_inlet("sub_out", label="Sub out", origin=PortOrigin.RESOLVED, on_change=RELAY_HANDLER)
        )
    definition.force_validation()
    return CallbackGroup(graph, definition, input_node, output_node)


def add_card(group: CallbackGroup) -> CallbackGroup:
    """Place the card standing for the group's Subgraph."""
    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

    group.card = make_node(group.graph, CARD, node_data={"store": {SUBGRAPH_KEY: group.definition.key}})
    return group


def build_group(graph, key: str = "sg_cb") -> CallbackGroup:
    """The interior and its card."""
    return add_card(build_interior(graph, key))
```

- [ ] **Step 2: Failing tests** — `tests/core/test_graph/test_callback_boundary_relay.py`:

```python
"""A subscription crosses a Group's boundary at wiring time, and unlinking either side unsubscribes."""

import pytest

from tests.conftest import make_node
from tests.core.test_graph.callback_group import EMIT, LISTEN, build_group, subscriptions

pytestmark = pytest.mark.integration


@pytest.fixture
def inward(graph_with_library_system):
    """A listener outside subscribed, through the card, to an emitter inside."""
    group = build_group(graph_with_library_system)
    emitter = make_node(group.definition, EMIT)
    group.definition.create_edge_wrapper(group.input_node.node_id, "sub_in", emitter.node_id, "edge_callback")
    listener = make_node(group.graph, LISTEN)
    outer = group.graph.create_edge_wrapper(listener.node_id, "listen_callback", group.card.node_id, "in_sub_in")
    return group, listener, emitter, outer


@pytest.fixture
def outward(graph_with_library_system):
    """A listener inside subscribed, through the card, to an emitter outside."""
    group = build_group(graph_with_library_system)
    listener = make_node(group.definition, LISTEN)
    inner = group.definition.create_edge_wrapper(
        listener.node_id, "listen_callback", group.output_node.node_id, "sub_out"
    )
    emitter = make_node(group.graph, EMIT)
    group.graph.create_edge_wrapper(group.card.node_id, "out_sub_out", emitter.node_id, "edge_callback")
    return group, listener, emitter, inner


class TestInward:
    def test_the_emitter_inside_hears_the_listener_outside(self, inward):
        _group, listener, emitter, _outer = inward

        assert subscriptions(emitter) == [listener.node.value("listen_callback")]

    def test_removing_the_outer_edge_unsubscribes(self, inward):
        group, _listener, emitter, outer = inward

        group.graph.remove_edge_wrapper(outer.edge_id)

        assert subscriptions(emitter) == []

    def test_the_card_inlet_relays(self, inward):
        from haywire.core.graph.subgraph_crossing import RELAY_HANDLER

        group, _listener, _emitter, _outer = inward

        assert group.card.node.ports["in_sub_in"].on_change == RELAY_HANDLER


class TestOutward:
    def test_the_emitter_outside_hears_the_listener_inside(self, outward):
        _group, listener, emitter, _inner = outward

        assert subscriptions(emitter) == [listener.node.value("listen_callback")]

    def test_removing_the_inner_edge_unsubscribes(self, outward):
        group, _listener, emitter, inner = outward

        group.definition.remove_edge_wrapper(inner.edge_id)

        assert subscriptions(emitter) == []


class TestGrowing:
    def test_a_callback_grown_into_the_output_relays_and_takes_no_default(self, graph_with_library_system):
        from haywire.core.graph.subgraph_crossing import RELAY_HANDLER

        group = build_group(graph_with_library_system)
        listener = make_node(group.definition, LISTEN)
        slot = next(p for p in group.output_node.node.ports.values() if p.id.startswith("slot_"))

        group.definition.create_edge_wrapper(listener.node_id, "listen_callback", group.output_node.node_id, slot.id)
        group.definition.force_validation()

        grown = group.output_node.node.ports[slot.id]
        assert grown.on_change == RELAY_HANDLER
        assert grown.data.get_own_value() == ""
```

- [ ] **Step 3:** Run the file → FAIL (`ImportError: RELAY_HANDLER`).

- [ ] **Step 4: `RELAY_HANDLER`** — in `subgraph_crossing.py`, after `EXIT_PREFIX = "exit_"`, add:

```python

#: The handler an immediate interface inlet calls on each write, on the card
#: (inward) and on the Subgraph Output (outward). It relays the value across
#: the boundary at once, as ``RerouteNode.forward_immediate`` does along an
#: edge; the partner is found by id, so no pairing needs assembly.
RELAY_HANDLER = "hb_relay"
```

and in the module docstring, after the paragraph starting `Values cross by worker copy, not by edge.` add:

```
An immediate value — a callback subscription — cannot wait for execution, so
it crosses at wiring time instead: each immediate interface inlet relays its
writes to its partner through ``RELAY_HANDLER``. See ADR 0041.
```

- [ ] **Step 5: The Subgraph Output relays outward** — in `subgraph_io.py`, change the import to

```python
from haywire.core.graph.subgraph_crossing import (
    RELAY_HANDLER,
    card_port_id,
    enter_crossing_id,
    exit_crossing_id,
)
```

In `hb_grow`, replace

```python
            "default": other.default,
            "origin": PortOrigin.RESOLVED,
        }
```

with

```python
            # An immediate port's default is its node's own subscription, meaningless here.
            "default": None if other.is_immediate else other.default,
            "origin": PortOrigin.RESOLVED,
        }
        if self._SLOT_PORT_TYPE is PortType.INLET and FlowType(incoming.class_identity.flow_type).is_immediate:
            kwargs["on_change"] = RELAY_HANDLER
```

In `SubgraphOutputNode`, after `init`, add:

```python
    def hb_relay(self, port, value) -> None:
        """Copy an immediate inlet's write to the card's matching outlet at once.

        Does nothing while no card stands for this Subgraph; the card copies the
        value out itself when it reconciles (see ``GraphNode.reconcile_interface``).
        """
        if not port.is_immediate:
            return
        definition = self.wrapper.graph if self.wrapper else None
        if not isinstance(definition, SubgraphDefinition):
            return
        card = definition.graph_node_wrapper()
        target = card.node.ports.get(card_port_id(port.id, is_inlet=False)) if card is not None else None
        if target is not None:
            target.set_value(value)
```

- [ ] **Step 6: The card relays inward** — in `graph_node.py`, add `RELAY_HANDLER` to the `subgraph_crossing` import. In `_mirror`, after the `widget_key` block, add:

```python
        if as_inlet and port.is_immediate:
            kwargs["on_change"] = RELAY_HANDLER
```

After `_mirror`, add:

```python
    def hb_relay(self, port: "DataPort", value: Any) -> None:
        """Copy an immediate inlet's write to the Subgraph Input's matching outlet at once."""
        if not port.is_immediate:
            return
        definition = self.resolve_definition()
        input_node = definition.input_node if definition is not None else None
        boundary_id = boundary_port_id(port.id)
        if input_node is None or boundary_id is None:
            return
        target = input_node.node.ports.get(boundary_id)
        if target is not None:
            target.set_value(value)
```

- [ ] **Step 7:** Run `tests/core/test_graph/test_callback_boundary_relay.py` → PASS; `uv run pytest tests/core/test_graph/ tests/core/test_undo/ tests/core/test_macro/ -n 4 -q -p no:randomly` → PASS.

- [ ] **Step 8:** Ruff, mypy; commit `feat(subgraph): immediate interface ports relay across the card`.

---

### Task 4: Reconcile resyncs every immediate pair

**Files:**
- Modify: `graph_node.py` (`reconcile_interface`; new `_resync_immediate_pairs`)
- Test: `tests/core/test_graph/test_callback_resync.py` (create)

**Interfaces:**
- Produces: after `reconcile_interface`, every immediate card inlet's value is on the Subgraph Input's matching outlet and every immediate Subgraph Output inlet's value on the card's matching outlet.

- [ ] **Step 1: Failing tests:**

```python
"""Whenever a card and its interior meet, their immediate ports agree."""

import pytest

from tests.conftest import make_node
from tests.core.test_graph.callback_group import EMIT, LISTEN, add_card, build_group, build_interior, subscriptions

pytestmark = pytest.mark.integration


def test_a_card_placed_after_the_interior_is_wired_carries_its_subscription_out(graph_with_library_system):
    group = build_interior(graph_with_library_system)
    listener = make_node(group.definition, LISTEN)
    group.definition.create_edge_wrapper(listener.node_id, "listen_callback", group.output_node.node_id, "sub_out")

    add_card(group)
    emitter = make_node(group.graph, EMIT)
    group.graph.create_edge_wrapper(group.card.node_id, "out_sub_out", emitter.node_id, "edge_callback")

    assert subscriptions(emitter) == [listener.node.value("listen_callback")]


def test_an_outward_subscription_survives_save_and_load(graph_with_library_system):
    group = build_group(graph_with_library_system)
    listener = make_node(group.definition, LISTEN)
    group.definition.create_edge_wrapper(listener.node_id, "listen_callback", group.output_node.node_id, "sub_out")
    emitter = make_node(group.graph, EMIT)
    group.graph.create_edge_wrapper(group.card.node_id, "out_sub_out", emitter.node_id, "edge_callback")
    name = listener.node.value("listen_callback")
    data = group.graph.to_dict()

    group.graph.clear()
    group.graph.load_from_dict(data)

    assert subscriptions(group.graph.node_wrappers[emitter.node_id]) == [name]


def test_a_reconcile_pushes_the_cards_subscription_into_a_reset_interior(graph_with_library_system):
    group = build_group(graph_with_library_system)
    emitter = make_node(group.definition, EMIT)
    group.definition.create_edge_wrapper(group.input_node.node_id, "sub_in", emitter.node_id, "edge_callback")
    listener = make_node(group.graph, LISTEN)
    group.graph.create_edge_wrapper(listener.node_id, "listen_callback", group.card.node_id, "in_sub_in")
    group.input_node.node.ports["sub_in"].set_value("")  # as a rebuilt interior starts
    assert subscriptions(emitter) == []

    group.card.node.reconcile_interface()

    assert subscriptions(emitter) == [listener.node.value("listen_callback")]
```

- [ ] **Step 2:** Run → the first and third FAIL (`[] == [...]`); the load test FAILS if the load path misses it (expected — Subgraphs load before the card).

- [ ] **Step 3: The resync** — in `reconcile_interface`, after `self._stamp_node_type()`, add `self._resync_immediate_pairs(input_node, output_node)`, and add after `reconcile_interface`:

```python
    def _resync_immediate_pairs(self, input_node, output_node) -> None:
        """Copy each immediate pair once, both ways, so the card and its interior agree.

        A relay fires only on a write, so a side built after its partner — the
        card after the interior on load, an interior rebuilt by a macro reload —
        would otherwise miss the other's current value.
        """
        if input_node is not None:
            for inlet in self.get_ports(is_port_type=PortType.INLET, has_pin=True):
                boundary_id = boundary_port_id(inlet.id)
                target = input_node.node.ports.get(boundary_id) if boundary_id else None
                if inlet.is_immediate and target is not None:
                    target.set_value(inlet.get_value())
        if output_node is not None:
            for inlet in output_node.node.get_ports(is_port_type=PortType.INLET, has_pin=True):
                target = self.ports.get(card_port_id(inlet.id, is_inlet=False))
                if inlet.is_immediate and target is not None:
                    target.set_value(inlet.get_value())
```

In `reconcile_interface`'s docstring, after the paragraph ending `leaving whatever pins the node already carries.` add: `Ends by copying every immediate pair once, in both directions (see ``hb_relay``).`

- [ ] **Step 4:** Run → PASS; then `uv run pytest tests/core/test_graph/ tests/core/test_undo/ tests/core/test_macro/ -n 4 -q -p no:randomly` → PASS.

- [ ] **Step 5:** Ruff, mypy; commit `feat(subgraph): reconciling a card resyncs its immediate pairs`.

---

### Task 5: The execution copy carries deferred pairs only

**Files:**
- Modify: `subgraph_io.py` (both `_resolve_pairs_and_crossings`), `graph_node.py` (`on_assembly` inward pairs)
- Test: `tests/core/test_graph/test_immediate_pairs_not_copied.py` (create)

- [ ] **Step 1: Failing test:**

```python
"""An immediate value crosses by the relay alone; execution copies deferred values only."""

import pytest

from tests.core.test_graph.callback_group import build_interior, add_card

pytestmark = pytest.mark.integration


def test_no_boundary_or_card_pairs_an_immediate_port(graph_with_library_system):
    from haywire.barn.builtin.types import FLOAT
    from haywire.core.types.enums import PortOrigin

    group = build_interior(graph_with_library_system)
    # Flags only the new id, so the stamped callback port stays.
    with group.input_node.node.rejig(include=["gain"]):
        group.input_node.node.add(FLOAT.as_outlet("gain", origin=PortOrigin.RESOLVED))
    add_card(group)

    for node in (group.input_node.node, group.output_node.node, group.card.node):
        assert node.on_assembly() == (True, None)

    pairs = group.input_node.node.cache.pairs + group.output_node.node.cache.pairs + group.card.node.cache.inward
    assert any(pair[1].id == "gain" for pair in group.input_node.node.cache.pairs)
    assert not any(port.is_immediate for pair in pairs for port in pair)
```

- [ ] **Step 2:** Run → FAIL (a callback port is paired).

- [ ] **Step 3: The filters** — in `SubgraphInputNode._resolve_pairs_and_crossings`, replace `if source is not None:` with `if source is not None and not outlet.is_immediate:`; in `SubgraphOutputNode._resolve_pairs_and_crossings`, replace `if target is not None:` with `if target is not None and not inlet.is_immediate:`; in `GraphNode.on_assembly`, replace `if source is not None:` (inward loop) with `if source is not None and not outlet.is_immediate:`. In `_GrowsInterface.worker`'s docstring, add: `Immediate ports are never paired: they relay at wiring time (``hb_relay``).`

- [ ] **Step 4:** Run → PASS; `tests/core/test_graph/ tests/core/test_execution/ -n 4` → PASS.

- [ ] **Step 5:** Ruff, mypy; commit `feat(subgraph): the execution copy leaves immediate pairs to the relay`.

---

### Task 6: Collapse and expand carry callback crossings

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` (remove the `straddling` refusal block and `_callback_edge_partners`; `_build_boundary` stamps `RELAY_HANDLER`)
- Modify: `packages/haywire-core/src/haywire/core/graph/subgraph_collapse.py` (`_build_ports` default)
- Delete: `tests/core/test_undo/test_collapse_callback_refusal.py`
- Test: `tests/core/test_undo/test_collapse_callback_crossing.py` (create)

- [ ] **Step 1: Failing tests** — create `test_collapse_callback_crossing.py`, reusing the refusal file's `_collapse`, keys and `listener_and_emitter` fixture (copy them), plus:

```python
def _subs(graph, emitter_id):
    from tests.core.test_graph.callback_group import subscriptions

    wrapper = graph.get_node_wrapper(emitter_id)
    if wrapper is None:
        for definition in graph.subgraphs.values():
            wrapper = definition.get_node_wrapper(emitter_id) or wrapper
    return subscriptions(wrapper)


class TestCollapsingAcrossACallback:
    def test_collapsing_the_emitter_keeps_it_subscribed(self, listener_and_emitter):
        graph, listener, emitter = listener_and_emitter
        name = listener.node.value("listen_callback")

        _collapse(graph, [emitter.node_id])

        assert _subs(graph, emitter.node_id) == [name]

    def test_collapsing_the_listener_keeps_the_emitter_subscribed(self, listener_and_emitter):
        graph, listener, emitter = listener_and_emitter
        name = listener.node.value("listen_callback")

        _collapse(graph, [listener.node_id])

        assert _subs(graph, emitter.node_id) == [name]

    def test_removing_the_outer_edge_after_collapse_unsubscribes(self, listener_and_emitter):
        graph, listener, emitter = listener_and_emitter
        action = _collapse(graph, [emitter.node_id])
        outer = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == action.card_node_id)

        graph.remove_edge_wrapper(outer.edge_id)

        assert _subs(graph, emitter.node_id) == []

    def test_removing_the_inner_edge_after_collapsing_the_listener_unsubscribes(self, listener_and_emitter):
        graph, listener, emitter = listener_and_emitter
        action = _collapse(graph, [listener.node_id])
        definition = graph.get_subgraph(action.subgraph_key)
        inner = next(e for e in definition.edge_wrappers.values() if e.source_node_id == listener.node_id)

        definition.remove_edge_wrapper(inner.edge_id)

        assert _subs(graph, emitter.node_id) == []

    def test_undo_restores_the_direct_subscription(self, listener_and_emitter):
        graph, listener, emitter = listener_and_emitter
        action = _collapse(graph, [emitter.node_id])

        action.undo()

        assert _subs(graph, emitter.node_id) == [listener.node.value("listen_callback")]

    def test_expand_restores_the_direct_subscription(self, listener_and_emitter):
        from haywire.core.undo.actions.graph_actions import ExpandGraphNodeAction

        graph, listener, emitter = listener_and_emitter
        action = _collapse(graph, [emitter.node_id])

        ExpandGraphNodeAction(graph=graph, node_id=action.card_node_id).execute()

        assert graph.subgraphs == {}
        assert _subs(graph, emitter.node_id) == [listener.node.value("listen_callback")]
```

Also keep `TestWhatIsStillAllowed` from the old file (both ends selected; no callback edge). Then `git rm tests/core/test_undo/test_collapse_callback_refusal.py`.

- [ ] **Step 2:** Run → FAIL (`ValueError: … callback edge would cross …`).

- [ ] **Step 3: Remove the refusal** — in `graph_actions.py`, delete the block

```python
        straddling = _callback_edge_partners(graph, selected)
        if straddling:
            raise ValueError(
                ...
            )
```

and the whole `_callback_edge_partners` function. Run `grep -rn "_callback_edge_partners" packages/ tests/` → no output.

- [ ] **Step 4: Stamp the relay** — in `_build_boundary`, after the `widget_key` block, add:

```python
                if not is_input and port.flow_type.is_immediate:
                    kwargs["on_change"] = RELAY_HANDLER
```

with `from ...graph.subgraph_crossing import RELAY_HANDLER` beside the `PortOrigin` import there.

- [ ] **Step 5: No seeded default for an immediate port** — in `subgraph_collapse.py` `_build_ports`, replace `default=naming.default,` with:

```python
                # An immediate port's default is its node's own subscription, meaningless here.
                default=None if naming.is_immediate else naming.default,
```

- [ ] **Step 6:** Run → PASS; `uv run pytest tests/core/test_undo/ tests/core/test_graph/ tests/graph_editor/ -n 4 -q -p no:randomly` → PASS (a test asserting the refusal elsewhere, e.g. in `tests/graph_editor/`, is a stop-and-report).

- [ ] **Step 7:** Ruff, mypy; commit `feat(subgraph): collapse and expand carry callback crossings`.

---

### Task 7: Macros carry callback interfaces

**Files:**
- Test: `tests/core/test_macro/test_macro_callback_interface.py` (create). Code changes are expected to be none — Tasks 3–5 already reach `MacroNode` (a `GraphNode`), a template keeps `on_change` (a serialized port field), and a reload ends in `reconcile_interface`. A failure here is a finding: report it before fixing.

- [ ] **Step 1: Tests** — build the template documents by serializing a real Subgraph, as `test_macro_reload.py` does, and reuse its `_identity`, `_save`, `_modified` helpers by importing them (`from tests.core.test_macro.test_macro_reload import _identity, _modified, _save`):

```python
"""A macro's callback interface relays like a Group's, through placement and reload."""

import itertools

import pytest

from tests.conftest import make_node
from tests.core.test_graph.callback_group import EMIT, INPUT, LISTEN, OUTPUT, subscriptions
from tests.core.test_macro.test_macro_reload import _identity, _modified, _save

pytestmark = pytest.mark.integration

_MACRO = "testlib:macro:Relay"
_KEYS = itertools.count()


def _document(graph, *, outward: bool):
    """A template with a callback interface: an interior emitter fed inward, or an interior listener fed out."""
    from haybale_core.types import CALLBACK
    from haywire.core.graph.subgraph import SubgraphDefinition
    from haywire.core.graph.subgraph_crossing import RELAY_HANDLER
    from haywire.core.types.enums import PortOrigin

    key = f"tpl_cb_{next(_KEYS)}"
    definition = graph.add_subgraph(SubgraphDefinition(key=key, label="Relay"))
    b_in = make_node(definition, INPUT)
    b_out = make_node(definition, OUTPUT)
    if outward:
        with b_out.node.rejig(exclude=[PortOrigin.DECLARED]):
            b_out.node.add(CALLBACK.as_inlet("sub", origin=PortOrigin.RESOLVED, on_change=RELAY_HANDLER))
        listener = make_node(definition, LISTEN)
        definition.create_edge_wrapper(listener.node_id, "listen_callback", b_out.node_id, "sub")
    else:
        with b_in.node.rejig(exclude=[PortOrigin.DECLARED]):
            b_in.node.add(CALLBACK.as_outlet("sub", origin=PortOrigin.RESOLVED))
        emitter = make_node(definition, EMIT)
        definition.create_edge_wrapper(b_in.node_id, "sub", emitter.node_id, "edge_callback")
    definition.force_validation()
    document = definition.to_dict()
    graph.remove_subgraph(key)
    document["meta"] = {"description": ""}
    document.pop("key", None)
    return document


@pytest.fixture
def macro(tmp_path, library_system):
    registry = library_system.get_macro_registry()
    identity = _identity(str(tmp_path))
    path = tmp_path / "Relay.hwm"

    def register(document):
        _save(path, document)
        registry.add_folder(str(tmp_path), identity)

    try:
        yield path, identity, registry, register
    finally:
        registry.remove_folder(str(tmp_path), identity)


def _interior_nodes(placement, registry_key):
    definition = placement.node.resolve_definition()
    return [w for w in definition.node_wrappers.values() if w.registry_key == registry_key]


def test_an_outward_subscription_reaches_an_emitter_outside_a_placement(graph_with_library_system, macro):
    graph = graph_with_library_system
    _path, _identity_, _registry, register = macro
    register(_document(graph, outward=True))
    placement = make_node(graph, _MACRO)
    emitter = make_node(graph, EMIT)

    graph.create_edge_wrapper(placement.node_id, "out_sub", emitter.node_id, "edge_callback")

    (listener,) = _interior_nodes(placement, LISTEN)
    assert subscriptions(emitter) == [listener.node.value("listen_callback")]


def test_an_inward_subscription_survives_a_reload(graph_with_library_system, macro):
    graph = graph_with_library_system
    path, identity, registry, register = macro
    register(_document(graph, outward=False))
    placement = make_node(graph, _MACRO)
    listener = make_node(graph, LISTEN)
    graph.create_edge_wrapper(listener.node_id, "listen_callback", placement.node_id, "in_sub")

    _save(path, _document(graph, outward=False))
    _modified(registry, path, identity)

    (emitter,) = _interior_nodes(placement, EMIT)
    assert subscriptions(emitter) == [listener.node.value("listen_callback")]


```

Write the promotion test by following `tests/core/test_macro/test_promote_swap.py` (`macro_folder`, `_editor`, `editor.promote_to_macro`), with the collapsed selection being a `LISTEN` node wired to an outer `EMIT`; after the swap, assert the outer emitter is subscribed to the placement's interior listener's value.

- [ ] **Step 2:** Run → PASS expected. A failure: report, then fix in the smallest place (likely a reload path that skips `reconcile_interface`).

- [ ] **Step 3:** Ruff, mypy; commit `test(macro): callback interfaces relay through placement, reload and promotion`.

---

### Task 8: Nested Groups

- [ ] **Step 1: Test** — append to `tests/core/test_undo/test_collapse_callback_crossing.py`:

```python
def _find(graph, node_id):
    """The wrapper for ``node_id`` anywhere in the graph tree."""
    wrapper = graph.get_node_wrapper(node_id)
    if wrapper is not None:
        return wrapper
    for definition in graph.subgraphs.values():
        found = _find(definition, node_id)
        if found is not None:
            return found
    return None


def test_a_subscription_crosses_two_nested_cards(listener_and_emitter):
    from tests.core.test_graph.callback_group import subscriptions

    graph, listener, emitter = listener_and_emitter
    name = listener.node.value("listen_callback")
    inner = _collapse(graph, [emitter.node_id], label="Inner")

    outer = _collapse(graph, [inner.card_node_id], label="Outer")

    assert subscriptions(_find(graph, emitter.node_id)) == [name]
    edge = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == outer.card_node_id)
    graph.remove_edge_wrapper(edge.edge_id)
    assert subscriptions(_find(graph, emitter.node_id)) == []
```

Use `_find` in `_subs` too (replace its body with `return subscriptions(_find(graph, emitter_id))`).

- [ ] **Step 2:** Run → PASS expected (each level relays and resyncs); a failure is a finding to report.

- [ ] **Step 3:** Commit `test(subgraph): a subscription crosses nested Groups`.

---

### Task 9: Docs, ADR 0041, full verification

- [ ] **Step 1: ADR 0041** — create `docs/adr/0041-callbacks-cross-a-subgraph-boundary.md`:

```markdown
---
name: callbacks-cross-a-subgraph-boundary
description: An immediate interface port relays each write across the card at wiring time, as a reroute does along an edge; reconcile resyncs both sides, execution copies only deferred values, a bare ADD grows any flow, and a graph tree validates under one lock — supersedes ADR 0036's "A callback may not cross the boundary"
status: accepted
see-also: ADR-0036, ADR-0037, ADR-0038, ADR-0039, ADR-0040
level: architectural
---

# Callbacks cross a Subgraph boundary through an immediate relay

**Context.** ADR 0036 refused callback crossings: a boundary node copies values when it executes, a subscription must arrive without anything executing, and a relayed copy would re-key the emitter's pool so that unlinking outside never reached inside. Two later changes removed both reasons. A reroute relays an immediate write at once from its inlet's `on_change` (ADR 0039), and an unlinked inlet shows its own value — for a callback, an empty name the emitter's pool drops (ADR 0040) — so removing any edge on a relay path unsubscribes through the next edge's own key. ADR 0036 also said the growing slot grows an `EXEC` port; it could not, because a bare `ADD` is `FlowType.DATA` and formal validation requires equal flows.

**Decision.**

- *Relay.* Every immediate interface inlet relays each write to its partner at once, from an `on_change` handler (`RELAY_HANDLER`) on its own node: the card's inlet writes the Subgraph Input's outlet, the Subgraph Output's inlet writes the card's outlet. The partner is found by id through `subgraph_crossing`, per call, with no cache. Keyed on `is_immediate`, not on `CALLBACK`.
- *Resync.* `reconcile_interface` — the single funnel where card and interior meet (collapse, re-bind, growth, load, macro reload) — ends by copying every immediate pair once in both directions.
- *One route per value.* The execution-time copy pairs deferred ports only.
- *Growth.* A bare `ADD` accepts an edge of any flow, and the edge takes the other end's flow, so a boundary slot grows data, control and callback ports.
- *Arity.* One subscription per interface port; emitters pool.
- *Defaults.* An immediate interface port takes no default from the interior port it was minted from: a listener's default is its own subscription.
- *Locks.* A Subgraph validates under its host's validation lock, so every batch of a graph tree runs one at a time on any thread, and relay writes nested either way inside a batch are re-entrant.

**Alternatives.** *Keep refusing* — the reasons no longer hold. *Cache the pairs* — needs invalidation on every reconcile, rebuild and reload. *A relay object owned by the definition* — a second relay mechanism beside the reroute's, and field events fire for writes the node never sees. *Serialize `ThreadingTimerScheduler` batches* — `force_immediate_validation()` bypasses schedulers. *Pooled interface ports* — a keyed pool relay, the per-source key problem ADR 0036 described. *Smooth over collapse churn* — a notification hold used by two actions.

**Consequences.**

- Collapse and expand drop the subscription and add it back under the new edge; an emitter reacting to pool changes sees both.
- A second listener outside needs a second interface port, grown inside.
- EdgeKind (edge-kinds step 5) gets the boundary relay for any immediate kind.
```

- [ ] **Step 2: ADR 0036** — change `see-also` to add `ADR-0041` and insert after the H1:

```markdown
> **"A callback may not cross the boundary" and the growing slot's flow are superseded by [ADR 0041](0041-callbacks-cross-a-subgraph-boundary.md).** Immediate interface ports relay across the card at wiring time; a bare `ADD` slot grows a port of any flow. Everything else here stands.
```

- [ ] **Step 3: Glossary** — in **CALLBACK port**, replace `It cannot cross a Subgraph boundary yet.` with `It crosses a Subgraph boundary the same way: an immediate interface port relays it across the card (ADR 0041).` and add `and [ADR 0041](../adr/0041-callbacks-cross-a-subgraph-boundary.md)` after the ADR 0036 link. In **Growing slot**, after `grows an **interface port** of that port's type`, insert ` — of any flow: data, control or callback`. In **Interface port**, append before the final sentence: `An immediate one relays each write across the card at once (ADR 0041).`

- [ ] **Step 4: Architecture docs** — `callbacks-arch.md`: rename `### 2.4 Through reroutes` to `### 2.4 Through reroutes and Subgraph boundaries`, and replace the paragraph `Subgraph boundaries do not relay callbacks yet: collapsing a selection that a callback edge would cross is still refused.` with:

```markdown
A Subgraph boundary relays the same way. The card's immediate inlets and the Subgraph Output's immediate inlets carry `on_change = hb_relay`, which writes the partner port on the other side at once — the Subgraph Input's outlet for a card inlet, the card's outlet for a Subgraph Output inlet — found by id through `subgraph_crossing`. `reconcile_interface` copies every immediate pair once whenever card and interior meet, so load order and a macro reload leave both sides agreeing. Unlinking either side reveals the next port's own value, which the relay carries on. See ADR 0041.
```

`graph-arch.md` §Interface: after the paragraph ending `so the view that builds a crossing and the worker that follows one cannot drift.` add:

```markdown
Deferred values cross when the boundary nodes execute; immediate ones — callback subscriptions — cross at wiring time: each immediate interface inlet relays its writes to its partner (`hb_relay`), and `reconcile_interface` resyncs every immediate pair. A graph tree validates under one lock (`BaseGraph._share_validation_lock`), so the two graphs a card spans never validate at once. See ADR 0041.
```

`node-canon.md` **Growing slot** paragraph: after `grows a real port of the incoming type in its place` insert ` — of any flow, since a bare `ADD` accepts data, control and callback edges alike —`.

- [ ] **Step 5: Docstrings** — `subgraph_io.py` module docstring: after `every value travels the rest of the way over real edges.` add `Immediate values — callback subscriptions — cross at wiring time instead, through ``hb_relay``; see ``haywire.core.graph.subgraph_crossing``.` `graph_node.py` module docstring: after `Either way the boundary nodes carry the values` add ` — deferred ones; an immediate value crosses at wiring time through ``hb_relay```.

- [ ] **Step 6: Overview** — in `2026-09-28-edge-kinds.md`: step 4's row → **Built** on `unlink-own-value`, not merged, detail plan this file, next: merge; the step 4 section's open-question list → `*Settled 2026-09-29; see the detail plan and ADR 0041.*`; step 5's inputs: add "the boundary relay is keyed on `is_immediate`, so an immediate kind needs nothing more".

- [ ] **Step 7: Regenerate and build:** `uv run haywire docs --all`; `git status --short` (expect `ADD`, `SubgraphInputNode`/`SubgraphOutputNode`/`GraphNode` docs only); `uv run mkdocs build --strict -d <scratchpad>/site` → only the pre-existing `guides/panels.md` warning.

- [ ] **Step 8:** Commit docs `docs: callbacks cross a Subgraph boundary, ADR 0041`.

- [ ] **Step 9: Full verification** — ruff (`.`), ruff format check, full mypy command from CLAUDE.md, gate `-m "not browser and not perf" -n 4` (only the 2 haystack xfails), browser tier `-m browser -n 4`, visiongraph `(cd ../haybale-visiongraph && uv run pytest tests/ -q)`, clean tree. Report the 5A refinement and the default-seeding fix to the user.

## Execution notes — 2026-09-29

Built inline on `unlink-own-value`. Deviations:

- **Task 3/6, defaults:** passing `default=None` builds `{"value": None}`, not the type's default, so an immediate port omits the `default` key (`hb_grow`, `_build_boundary`); `_build_ports` is unchanged.
- **Task 4, found:** `graph.clear()` cleans up nodes before it detaches their edges, and step 2's reveal then called `on_change` on a cleaned-up node — clearing any graph with a linked callback reroute raised. Fixed separately (`NodeWrapper.is_cleaned_up`), with a regression test in `test_disconnect_semantics.py`.
- **Task 7, design gap (Q11A):** every listener is an EVENT node, which a Subgraph may not contain (`validate_subgraph_contents`, the macro registry). Outward crossing therefore exists only as pass-through; the outward tests were rewritten to a reroute or a direct Input-to-Output edge inside the Group or macro. ADR 0041 says so.
- **Task 4 test:** `test_a_reconcile_pushes_the_cards_subscription_into_a_reset_interior` passed before the resync — the rejig inside `reconcile_interface` re-propagates the outer edge. Kept as a regression test.
- **Task 6:** `tests/core/test_assembly/test_subgraph_execution_edges.py`'s docstring claimed callback crossings it never tested; corrected.


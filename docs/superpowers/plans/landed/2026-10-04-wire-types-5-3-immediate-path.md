# The immediate path (edge-kinds step 5.3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A loop of immediate edges ends after one pass instead of recursing, a write that changes nothing the node sees tells the node nothing, and a callback value can be absent: `None` is "no subscription", saved as JSON `null`, and pools drop it. Array and map port values survive save and load.

**Architecture:** One helper, `DataPort._fire_immediate`, holds both guards. It is called from the immediate branch of `set_value` and from the reveal on unlink, with a thread-local set of the immediate inlets whose `on_change` is running. A wire type gains `holds_absence`; `IType.create_field` gives a type that declares such a wire a field class that can hold `None` (`_field_holding_absence`, a sibling of `_absence_tolerant_field` that keeps the stored type and covers `BaseField`). `DataField.to_dict`/`from_dict` become template methods: absence is handled in the base, a present value in the hooks `_own_to_dict`/`_own_from_dict`. Callback types then declare `default=None`, and `PooledField` drops `None` in place of the "element default" sentinel.

**Tech Stack:** Python 3.12, pytest (+ xdist, Playwright browser tier), uv, ruff, mypy.

**Settled in:** [2026-10-02-wire-types.md](2026-10-02-wire-types.md), sections "The immediate path" and "Absence on callback wires (Q14)", decisions Q13b, Q14, Q22 to Q25, and follow-up F12. Corrections found while writing this plan are listed in [Corrections to the design](#corrections-to-the-design); the user confirmed all eight on 2026-10-04 (design decisions Q63 to Q70).

## Global Constraints

- **Two repos.**
  - This repo: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo`.
  - haybale-visiongraph: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph`, linked here as `barn/haybale-visiongraph`. Edit through the symlink; run git for it in the visiongraph repo.
- **Branch.** Continue on `wire-types-5-1` in both repos (5.1, 5.2 and D are landed there, unmerged). Never push; the user pushes.
- **Commit trailer.** Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Never commit:**
  - `docs/superpowers/plans/` (plans are left for the user to commit);
  - `internals/`, `.superpowers/`, `.claude/settings.json`;
  - the scratch file `tests/core/test_zz_graph_snapshot.py`.

  Always `git add` explicit paths, never `-A` or `.`.
- **Commit `barn/haybale-testing/` first.** Commit every change there before running the full suite: `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing` in its teardown and discards uncommitted edits.
- **Intended behaviour changes.** These are the only ones, each with its test edit named in its task. Any other red behavioural test is a bug: stop and report it.
  1. **Echo guard** (Q13b): an edge's write to an immediate inlet that leaves the value the node sees unchanged is stored and fires no `on_change` (and marks nothing dirty). An immediate pool fed the same subscription twice tells its node once.
  2. **Re-entrancy guard** (Q13b, Q24): an edge's write that reaches an immediate inlet whose `on_change` is still running on the same thread is dropped, not stored, and logged as one warning naming the port and node. A loop of immediate edges no longer raises `RecursionError`.
  3. **Callback absence** (Q14, Q22): `CALLBACK`, `TEST_RECORD_CALLBACK` and `MULTIFRAME_CALLBACK` declare `default=None`. An unlinked callback port reads `None`, not `""` or a dataclass with `name=""`. A callback field `accepts_absence()`, so a pipe forwards `None` into it. A pool of a callback element drops a `None` entry; it no longer drops `""` or an element-default dataclass, which are now ordinary values.
  4. **Null serialization:** a field that `accepts_absence()` and holds no own value saves `null` as its `field_data`, and `from_dict(None)` restores absence. `OPTIONAL[T]` saves `null` instead of `{"value": null}`; `{"value": null}` still loads. `from_dict(None)` on a field that cannot hold absence raises `TypeError`.
  5. **Array and map values are saved** (Q25): an `ArrayField` or `MapsStringField` port saves its items, where it saved the type's declared default.
  6. **`@type(default=None)`** is accepted on a type whose wire type `holds_absence`, primitive or dataclass, and stores an empty default (Q22).
- **Accepted break (Q23):** an orphaned callback relay saved holding `""` loads holding `""`, now a real name; relinking or deleting it fixes it. None of the saved graphs in either repo has one.
- **Out of scope:** 5.4 (style bag, `RemappedEdge` propagation), 5.5 (annotation), F13 to F21, the Small items other than Q25. `ControlWire` gets no absence (see F12 under [Corrections](#corrections-to-the-design)).
- **Compare wire types by `.id`**, never with `is` on the class. `WireRole` members compare with `is`.
- **Docstrings and comments** follow `.claude/rules/python-docs.md`. Docstrings of registered components (types, nodes) are displayed: Markdown, single backticks, no reST.
- **"Ruff check"** means both `uv run ruff check <paths>` and `uv run ruff format --check <paths>`; line length 109.
- **Pre-commit gate:** `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`, then `grep -E "^FAILED|^ERROR" /tmp/t.log` and `tail -1 /tmp/t.log`. Timeout at least 600000 ms. Baseline recorded in Task 0.
- **Browser tier:** `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`. One known intermittent failure, `test_edge_batch_cost` (F13): rerun the tier once before calling it red.
- **visiongraph tests:** from this repo, `uv run pytest ../haybale-visiongraph/tests -q -p no:randomly`.
- **mypy set:** `uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/`. Baseline clean.
- **Code lookup:** the repo is indexed by CodeGraph. `codegraph explore "<symbols>"` returns verbatim source plus callers.

---

## Corrections to the design

Found while reading the code for this plan. All confirmed by the user on 2026-10-04 (design Q63 to Q70).

| # | Design said | The code says | This plan |
|---|---|---|---|
| C1 | Verify first: "two callback reroutes looped: linking the closing edge ends with one warning" | Two plain reroutes forward the value unchanged, so the closing edge delivers the value the inlet already holds, and the echo guard ends the loop before the re-entrancy guard is reached: no warning. A warning needs a node in the loop that changes the value | Task 1 tests both: plain reroutes end with no warning; a renaming test node (`CallbackRelayProbeNode`, new) ends with exactly one |
| C2 | Echo guard: "a write that equals the value the node already sees" | For a pooled inlet the written value is one element and the node sees the whole pool, so comparing the written value is wrong | Compare what the node sees before and after the store (`get_value()` twice), as the reveal path already does. `on_change` still receives what it receives today (the written value; the own value on reveal), so no handler signature changes |
| C3 | The guard's set holds "the immediate inlets" | `DataPort.__hash__` hashes the port id string, and two nodes' ports share ids (`in`, `out`) | The set holds `id(port)` |
| C4 | "Every `from_dict` override (`PrimitiveField`, `BaseField`, the builtin INT/FLOAT/STRING specs, the haybale-testing fields) moves to the hook" | The spec and haybale-testing overrides are **type** classmethods (`INT.from_dict`), called by `PrimitiveField` with a present payload only. The field-level overrides are `PrimitiveField`, `BaseField` and `ADDField` | Only the three field overrides move. Type classmethods are untouched |
| C5 | "`normalize_and_validate_default` accepts `None` for them, `BaseType` included" | `@type` calls it once; a `None` default never needs normalizing because it becomes `{}` (Q22) | `@type` maps `default=None` to `{}` before normalizing, for a `holds_absence` wire only. `normalize_and_validate_default` is unchanged |
| C6 | Q25: array and map saves fixed | Nothing to migrate: every saved array port (`graphs/any_and_nonde.haywire`, 10 ports) holds the stub `{"value": []}` and has no port default, so it loads `[]` as before | No migration |
| C7 | F12: "with `holds_absence`, a pool could record only sources that fired" | `holds_absence` lands on `CallbackWire` only; a pool of `EXEC` is on `ControlWire`. Lifting the refusal needs `ControlWire.holds_absence` with `EXEC` absent by default, which changes what every unfired control inlet reads (`{}` → `None`). And a source that fired in an earlier run keeps its payload, which absence does not fix | **Decided by the user 2026-10-04: keep the refusal**, F12 closed as decided. `ControlWire.holds_absence` would be a design question of its own. Task 6 records the decision |
| C8 | "Q24: a dropped fire stores nothing", stated for `set_value` | The reveal path stores by clearing the linked value | The reveal path follows Q24 too: a re-entrant reveal is dropped before `clear_linked()`. Reachable only by unlinking an inlet from inside its own `on_change` |

## Names this plan introduces

| Name | Where | What |
|---|---|---|
| `DataPort._fire_immediate(store, value)` | `core/types/port.py` | Both guards; see Task 1 |
| `_firing_inlets()` | `core/types/port.py` | The thread-local set of `id()`s of immediate inlets whose `on_change` is running |
| `WireType.holds_absence: ClassVar[bool]` | `core/types/wire.py` | `False` by default; `CallbackWire` sets `True` |
| `_field_holding_absence(field_cls)` | `core/types/base.py` | The field class a type on a `holds_absence` wire stores with |
| `BaseField._default_instance()` | `core/types/fields.py` | The own value a `BaseField` starts and resets to |
| `DataField._own_to_dict()` / `_own_from_dict(data)` | `core/types/fields.py` | The present-value hooks of the serialization template |
| `element_to_dict(element_type, value)` / `element_from_dict(element_type, data)` | `core/types/fields.py` | Serialize one container item the way a field of its element type does |
| `CallbackRelayProbeNode` | `haybale_testing/nodes/testbed/callback_relay_probe.py` | Test node: copies a callback inlet to its outlet on write, with a suffix |

## File structure

| File | Change |
|---|---|
| `packages/haywire-core/src/haywire/core/types/port.py` | guards, logger, `set_value`, `_reveal_own_value_if_unlinked`, `_serialize_value` return type |
| `packages/haywire-core/src/haywire/core/types/wire.py` | `holds_absence` |
| `packages/haywire-core/src/haywire/barn/builtin/wires.py` | `CallbackWire.holds_absence = True` |
| `packages/haywire-core/src/haywire/core/types/base.py` | `_field_holding_absence` |
| `packages/haywire-core/src/haywire/core/types/interface.py` | `create_field` applies it |
| `packages/haywire-core/src/haywire/core/types/decorator.py` | `default=None` on a `holds_absence` wire; docstring drift |
| `packages/haywire-core/src/haywire/core/types/identity.py` | docstring drift only |
| `packages/haywire-core/src/haywire/core/types/fields.py` | template methods, hooks, `_default_instance`, element helpers |
| `packages/haywire-core/src/haywire/barn/builtin/types/add.py` | `ADDField` hooks |
| `packages/haywire-core/src/haywire/barn/builtin/types/callback.py` | `default=None`, docstring |
| `packages/haywire-core/src/haywire/ui/panel/port_default_widget_model.py` | `as_default` return type |
| `barn/haybale-core/haybale_core/types/array_type.py` | `ArrayField` hooks |
| `barn/haybale-core/haybale_core/types/pooled_type.py` | absence replaces the default sentinel (deletion 9) |
| `barn/haybale-example/haybale_example/types/maps_string_type.py` | `MapsStringField` hooks |
| `barn/haybale-testing/haybale_testing/types/test_types.py` | `TEST_RECORD_CALLBACK` `default=None` |
| `barn/haybale-testing/haybale_testing/nodes/testbed/callback_relay_probe.py` | new test node |
| visiongraph `haybale_visiongraph/types/multiframe_callback_type.py` | `default=None` |
| tests: `tests/core/test_types/test_immediate_guards.py`, `test_wire_holds_absence.py`, `test_field_serialization.py`, `test_callback_absence.py` | new |
| tests: `test_callback_values.py`, `test_callback_boundary_relay.py`, `test_disconnect_semantics.py` | assertion edits (behaviour change 3) |
| docs: ADR 0046 (new), ADR 0033, callbacks-arch, datatype-canon, glossary, generated library docs, the design's status | Task 6 |

---

### Task 0: Baseline (controller)

- [x] **Step 1: Confirm the corrections.** Done 2026-10-04: C1 to C8 confirmed, logged as Q63 to Q70.
- [ ] **Step 2: Clean trees.** `git status --short` in both repos shows nothing but untracked plan files.
- [ ] **Step 3: Baselines.** Run the pre-commit gate, the browser tier, the visiongraph tests, the mypy set and `uv run ruff check . && uv run ruff format --check .`. Record the pass counts in `.superpowers/sdd/progress.md` under a new section "5.3". All must be green; if not, stop and start an error-fix session with the user (CLAUDE.md).
- [ ] **Step 3b: Benchmark baseline.** Run the `haywire-benchmark` skill on the clean tree; Task 7 compares against it.
- [ ] **Step 4: Saved-graph snapshot.** Recreate the scratch test `tests/core/test_zz_graph_snapshot.py` exactly as in [5.1's Task 0 Step 4](landed/2026-10-03-wire-types-5-1-sweep.md) (never committed; the Global Constraints' never-commit list covers it), and run `HW_GRAPH_SNAPSHOT=/tmp/graph_snapshot_before_5_3.json uv run pytest tests/core/test_zz_graph_snapshot.py -q -p no:randomly`. Task 4 Step 7 compares against it.

---

### Task 1: The immediate guards

**Files:**
- Create: `barn/haybale-testing/haybale_testing/nodes/testbed/callback_relay_probe.py`
- Create: `tests/core/test_types/test_immediate_guards.py`
- Modify: `packages/haywire-core/src/haywire/core/types/port.py` (imports and module helpers near line 30; `set_value` at 347-391; `_reveal_own_value_if_unlinked` at 710-728)

**Interfaces:**
- Produces: `DataPort._fire_immediate(store: Callable[[], None], value: Any) -> None`; `CallbackRelayProbeNode` (registry key `haybale-testing:node:CallbackRelayProbeNode`, ports `in` and `out`, class attribute `suffix: str`, instance list `heard`).

- [ ] **Step 1: The test node**

Create `barn/haybale-testing/haybale_testing/nodes/testbed/callback_relay_probe.py`:

```python
"""Test-only node that relays a callback value as soon as it is written."""

from typing import Any

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node


@node(
    label="Callback Relay Probe",
    description="Test-only: copies a callback inlet's value to its outlet on write, with a suffix.",
    menu="testing/callbacks",
    search_tags=["test", "callback", "relay", "loop"],
    node_type=NodeType.DATA,
)
class CallbackRelayProbeNode(BaseNode):
    """Copies each value written to `in` onto `out` at once, with `suffix` appended.

    An empty `suffix` relays the value unchanged; absence is relayed as absence.
    `heard` records every value `in` reported.
    """

    suffix = ""

    def init(self):
        from haywire.barn.builtin.types import CALLBACK

        self.add(CALLBACK.as_inlet("in", on_change="_relay"))
        self.add(CALLBACK.as_outlet("out"))

    def post_init(self):
        self.heard: list[Any] = []

    def _relay(self, port, value) -> None:
        self.heard.append(value)
        self.out("out", value if value is None else f"{value}{self.suffix}")

    def worker(self, context: ExecutionContext) -> str | None:
        return None
```

Check the `on_change` signature against `TestEmitCallbackNode.printout` (`port, new_value`) and that testbed nodes register by folder scan (as `container_signal_probes.py` did in 5.2): `uv run python -c "from haybale_testing.nodes.testbed.callback_relay_probe import CallbackRelayProbeNode as N; print(N.class_identity.registry_key)"` prints `haybale-testing:node:CallbackRelayProbeNode`.

Commit it now (the docs test resets `barn/haybale-testing`):

```bash
git add barn/haybale-testing/haybale_testing/nodes/testbed/callback_relay_probe.py
git commit -m "test(testing): callback relay probe node for immediate-loop tests

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 2: Write the failing tests**

Create `tests/core/test_types/test_immediate_guards.py`:

```python
"""The immediate path's guards: an unchanged value tells the node nothing, and a loop ends after one pass."""

import logging
from typing import Any, cast

import pytest

from tests.conftest import make_edge, make_node
from tests.core.test_graph.callback_group import EMIT, LISTEN, build_group, subscriptions

pytestmark = pytest.mark.integration

RELAY = "haybale-testing:node:CallbackRelayProbeNode"
PORT_LOGGER = "haywire.core.types.port"


def _split_with_reroute(graph, edge_id: str) -> str:
    """Split *edge_id* with a reroute node the way the canvas does, returning the reroute's id."""
    from haywire.barn.builtin.nodes.reroute import RerouteNode
    from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

    action = SplitEdgeWithRerouteAction(
        graph=cast(Any, graph),
        edge_id=edge_id,
        position=(200.0, 0.0),
        registry_key=RerouteNode.class_identity.registry_key,
    )
    action._execute_impl()
    reroute_id = action.reroute_node_id
    assert reroute_id is not None
    return reroute_id


def _loop_warnings(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == PORT_LOGGER and "loop" in r.getMessage()]


class TestEchoGuard:
    def test_two_callback_reroutes_looped_keep_the_listener_subscribed(self, graph_with_library_system, caplog):
        """Plain reroutes relay the value unchanged, so the echo guard ends the loop: no warning (C1)."""
        caplog.set_level(logging.WARNING, logger=PORT_LOGGER)
        graph = graph_with_library_system
        listener = make_node(graph, LISTEN, position=(0, 0))
        emitter = make_node(graph, EMIT, position=(600, 0))
        edge = make_edge(graph, listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
        first = _split_with_reroute(graph, edge.edge_id)
        onward = next(e for e in graph.edge_wrappers.values() if e.source_node_id == first)
        second = _split_with_reroute(graph, onward.edge_id)

        make_edge(graph, second, "out", first, "in")  # closes the loop, displacing the listener's edge
        graph.force_validation()

        assert subscriptions(emitter) == [listener.node.value("listen_callback")]
        assert _loop_warnings(caplog) == []

    def test_a_pool_fed_the_same_subscription_twice_tells_its_node_once(self, graph_with_library_system):
        graph = graph_with_library_system
        listener = make_node(graph, LISTEN, position=(0, 0))
        emitter = make_node(graph, EMIT, position=(400, 0))
        heard: list = []
        emitter.node.printout = lambda port, value: heard.append(value)  # type: ignore[method-assign]
        make_edge(graph, listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
        graph.force_validation()
        assert len(heard) == 1

        listener.node.out("listen_callback", listener.node.value("listen_callback"))

        assert len(heard) == 1


class TestReentrancyGuard:
    def test_a_renaming_loop_is_cut_after_one_pass(self, graph_with_library_system, caplog):
        graph = graph_with_library_system
        first = make_node(graph, RELAY, position=(0, 0))
        second = make_node(graph, RELAY, position=(300, 0))
        first.node.suffix = "2"  # type: ignore[attr-defined]
        second.node.suffix = "2"  # type: ignore[attr-defined]
        make_edge(graph, first.node_id, "out", second.node_id, "in")
        make_edge(graph, second.node_id, "out", first.node_id, "in")
        graph.force_validation()
        caplog.set_level(logging.WARNING, logger=PORT_LOGGER)

        first.node.out("out", "x")

        assert second.node.heard == ["x"]  # type: ignore[attr-defined]
        assert first.node.heard == ["x2"]  # type: ignore[attr-defined]
        # Q24: "x22" reached `second.in` while its on_change ran; it was dropped and not stored.
        assert second.node.ports["in"].get_value() == "x"
        warnings = _loop_warnings(caplog)
        assert len(warnings) == 1
        assert second.node_id in warnings[0]


class TestAcrossASubgraphBoundary:
    @staticmethod
    def _loop_through_a_group(graph, suffix: str):
        """listener -> card -> (interior relay) -> card -> probe -> card: the probe's edge closes the loop."""
        group = build_group(graph)
        group.definition.create_edge_wrapper(
            group.input_node.node_id, "sub_in", group.output_node.node_id, "sub_out"
        )
        listener = make_node(graph, LISTEN, position=(0, 0))
        make_edge(graph, listener.node_id, "listen_callback", group.card.node_id, "in_sub_in")
        probe = make_node(graph, RELAY, position=(600, 0))
        probe.node.suffix = suffix  # type: ignore[attr-defined]
        make_edge(graph, group.card.node_id, "out_sub_out", probe.node_id, "in")
        make_edge(graph, probe.node_id, "out", group.card.node_id, "in_sub_in")
        graph.force_validation()
        return group, listener, probe

    def test_an_unchanged_value_looped_through_a_group_ends(self, graph_with_library_system, caplog):
        caplog.set_level(logging.WARNING, logger=PORT_LOGGER)

        group, listener, _probe = self._loop_through_a_group(graph_with_library_system, "")

        assert group.card.node.ports["in_sub_in"].get_value() == listener.node.value("listen_callback")
        assert _loop_warnings(caplog) == []

    def test_a_renaming_loop_through_a_group_is_cut_once(self, graph_with_library_system, caplog):
        """The interior relay runs on the same call stack, so one set covers both graphs."""
        caplog.set_level(logging.WARNING, logger=PORT_LOGGER)

        self._loop_through_a_group(graph_with_library_system, "2")

        assert len(_loop_warnings(caplog)) == 1
```

- [ ] **Step 3: Run them (red)**

Run: `uv run pytest tests/core/test_types/test_immediate_guards.py -q -p no:randomly`
Expected: the two loop tests of `TestEchoGuard`/`TestAcrossASubgraphBoundary` and `test_a_renaming_loop_is_cut_after_one_pass` fail with `RecursionError`; `test_a_pool_fed_the_same_subscription_twice_tells_its_node_once` fails with `assert 2 == 1`. If any trace differs from this (a different count at link time, a self-loop refusal), stop and report: the tests encode the traces in the docstrings.

- [ ] **Step 4: Implement**

In `port.py`, add to the imports:

```python
import logging
import threading
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
```

and after `_same_value`:

```python
logger = logging.getLogger(__name__)

# ids of the immediate inlets whose on_change is running on this thread; see DataPort._fire_immediate.
_immediate_fires = threading.local()


def _firing_inlets() -> set[int]:
    """Return the ``id()`` of every immediate inlet whose ``on_change`` is running on this thread."""
    firing = getattr(_immediate_fires, "inlets", None)
    if firing is None:
        firing = _immediate_fires.inlets = set()
    return firing
```

Replace the body of `set_value` from `self._data.set_value(new_value, source_id=edge_id)` to the end with:

```python
        # _is_immediate first: on a data or control port the hot path pays one attribute read.
        if self._is_immediate and self._is_inlet and edge_id is not None:
            self._is_set_by_node = False
            self._fire_immediate(lambda: self._data.set_value(new_value, source_id=edge_id), new_value)
            return

        self._data.set_value(new_value, source_id=edge_id)

        if self._is_inlet:
            # Inlet values come from an edge (edge_id set) or a widget/programmatic
            # set — never from the owning node, so clear the node-set flag.
            self._is_set_by_node = False
            if edge_id is None and self._data.has_linked_value():
                # The own value changed behind the linked one; the node sees no change.
                return
            if self.on_change is not None and edge_id is None:
                # Widget/programmatic change → fire on_change immediately
                self._trigger_callback(self.on_change, new_value)
            else:
                # Edge-driven OR no callback → defer to resolve_dirty_data()
                self._mark_as_data_dirty()
        else:
            # Outlet: the node is always the setter (out() is the only caller).
            self._is_set_by_node = True
            # Fire on_change immediately (node is the setter)
            if self.on_change is not None:
                self._trigger_callback(self.on_change, new_value)
            if self._pipes is not None:
                self._pipes.propagate()
```

Update the docstring's inlet bullets to:

```
        For inlets:
        - an edge's write to an immediate inlet goes through ``_fire_immediate``
        - an own write (no edge_id) while an edge feeds the inlet changes only
          the own value: no on_change, no dirty mark
        - any other own write fires on_change immediately
        - any other edge's write defers to resolve_dirty_data()
```

Add after `set_value`:

```python
    def _fire_immediate(self, store: Callable[[], None], value: Any) -> None:
        """Store a write to this immediate inlet and tell the node only when what it sees changed.

        *store* writes the field; ``on_change`` receives *value*. Nothing fires when
        ``get_value()`` is the same before and after the store. A write that reaches
        this inlet while its own ``on_change`` is still running on this thread closes
        a loop of immediate edges: it is dropped without being stored and logged as a
        warning. Without ``on_change``, a change marks the port data-dirty.
        """
        firing = _firing_inlets()
        key = id(self)
        if key in firing:
            node_id = self._wrapper.node_id if self._wrapper is not None else "?"
            logger.warning(
                "Dropped a write to immediate inlet %r of node %s: it closes a loop of immediate edges",
                self.id,
                node_id,
            )
            return
        before = self._data.get_value()
        store()
        if _same_value(before, self._data.get_value()):
            return
        if self.on_change is None:
            self._mark_as_data_dirty()
            return
        firing.add(key)
        try:
            self._trigger_callback(self.on_change, value)
        finally:
            firing.discard(key)
```

Replace `_reveal_own_value_if_unlinked`'s body after its guard line with:

```python
        if self._is_immediate:
            self._fire_immediate(self._data.clear_linked, self._data.get_own_value())
            return
        linked = self._data.get_value()
        self._data.clear_linked()
        if not _same_value(linked, self._data.get_value()):
            self._mark_as_data_dirty()
```

and its docstring's second paragraph to: "An immediate inlet goes through ``_fire_immediate``; a deferred one is marked dirty for its node's next execution. Nothing happens while another edge still feeds the inlet, or when the own value equals the linked one."

Check `NodeWrapper.node_id` exists (`codegraph explore "NodeWrapper node_id"`); use whatever attribute the wrapper exposes for its id.

- [ ] **Step 5: Run (green), then the callback neighbourhood**

Run: `uv run pytest tests/core/test_types/test_immediate_guards.py tests/core/test_edge/test_disconnect_semantics.py tests/core/test_graph/test_callback_boundary_relay.py tests/core/test_graph/test_immediate_pairs_not_copied.py tests/core/test_macro/test_macro_callback_interface.py tests/core/test_types/test_container_signal_elements.py tests/core/test_undo/test_split_edge_reroute.py -q -p no:randomly`
Expected: all pass.

- [ ] **Step 6: Ruff, mypy on `port.py`, gate, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/types/port.py tests/core/test_types/test_immediate_guards.py
uv run ruff format --check packages/haywire-core/src/haywire/core/types/port.py tests/core/test_types/test_immediate_guards.py
uv run mypy packages/haywire-core/src/haywire/core/types/port.py tests/core/test_types/test_immediate_guards.py
```

Run the pre-commit gate. Then:

```bash
git add packages/haywire-core/src/haywire/core/types/port.py tests/core/test_types/test_immediate_guards.py
git commit -m "feat(ports): immediate inlets fire only on change and cut loops after one pass

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `holds_absence` and the field that holds it

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/wire.py` (class attributes, docstring)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/wires.py` (`CallbackWire`)
- Modify: `packages/haywire-core/src/haywire/core/types/fields.py` (`BaseField`)
- Modify: `packages/haywire-core/src/haywire/core/types/base.py` (after `_absence_tolerant_field`)
- Modify: `packages/haywire-core/src/haywire/core/types/interface.py:107-133` (`create_field`)
- Modify: `packages/haywire-core/src/haywire/core/types/decorator.py:155-165` and its docstring
- Create: `tests/core/test_types/test_wire_holds_absence.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `WireType.holds_absence`; `_field_holding_absence(base_field_cls: type) -> type` in `haywire.core.types.base`; `BaseField._default_instance() -> BaseType | None`; `create_field` returning the absence-holding class for a type that itself declares a `holds_absence` wire.

`CALLBACK` keeps `default={"value": ""}` until Task 4, so nothing that flows today changes: callback fields can now hold `None`, but no callback outlet holds it yet.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_types/test_wire_holds_absence.py`:

```python
"""A wire type that holds absence gives the types declared on it fields that can hold `None` (Q14, Q22)."""

from dataclasses import dataclass

import pytest

pytestmark = pytest.mark.integration


def _record_type(default):
    """A dataclass type on `CallbackWire` with the given declared default."""
    from haywire.barn.builtin.wires import CallbackWire
    from haywire.core.types import BaseType
    from haywire.core.types import type as type_dec

    @type_dec(wire_type=CallbackWire, label="Probe Record", default=default)
    @dataclass
    class PROBE_RECORD(BaseType):
        name: str = ""

    return PROBE_RECORD


class TestTheWire:
    def test_only_the_callback_wire_holds_absence(self, library_system):
        from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire

        assert CallbackWire.holds_absence
        assert not DataWire.holds_absence
        assert not ControlWire.holds_absence


class TestAPrimitiveOnTheWire:
    def test_it_holds_absence_and_keeps_its_stored_type(self, library_system):
        from haywire.barn.builtin.types import CALLBACK

        field = CALLBACK.create_field()
        field.set_value(None)

        assert field.accepts_absence()
        assert field.get_value() is None
        assert field.get_stored_type() is CALLBACK

    def test_a_linked_value_can_be_absent(self, library_system):
        from haywire.barn.builtin.types import CALLBACK

        field = CALLBACK.create_field()
        field.set_value(None, source_id="e1")

        assert field.has_linked_value()
        assert field.get_value() is None

    def test_a_none_default_is_stored_empty_and_starts_absent(self, library_system):
        from haywire.barn.builtin.types import STRING
        from haywire.barn.builtin.wires import CallbackWire
        from haywire.core.types import type as type_dec

        @type_dec(wire_type=CallbackWire, label="Probe Name", default=None)
        class PROBE_NAME(STRING):
            """Probe."""

        assert PROBE_NAME.class_identity.default == {}
        assert PROBE_NAME.create_field().get_value() is None

    def test_a_none_default_off_the_wire_is_still_refused(self, library_system):
        from haywire.barn.builtin.types import STRING
        from haywire.core.types import type as type_dec

        with pytest.raises(TypeError, match="OPTIONAL"):

            @type_dec(label="Probe Text", default=None)
            class PROBE_TEXT(STRING):
                """Probe."""


class TestADataclassOnTheWire:
    def test_a_none_default_starts_and_resets_absent(self, library_system):
        field = _record_type(None).create_field()
        assert field.get_value() is None

        field.reset()

        assert field.get_value() is None
        assert field.accepts_absence()

    def test_a_present_default_is_read_back(self, library_system):
        record = _record_type({"name": "n"})

        assert record.create_field().get_value() == record(name="n")

    def test_a_present_value_is_still_type_checked(self, library_system):
        field = _record_type(None).create_field()

        with pytest.raises(TypeError):
            field.set_value("not a record")

    def test_it_takes_absence_after_a_value(self, library_system):
        record = _record_type(None)
        field = record.create_field()
        field.set_value(record(name="n"))

        field.set_value(None)

        assert field.get_value() is None


class TestWhatIsNotWrapped:
    def test_containers_of_a_callback_keep_their_own_fields(self, library_system):
        from haybale_core.types import ArrayType, PooledType
        from haybale_core.types.array_type import ArrayField
        from haybale_core.types.pooled_type import PooledField

        from haywire.barn.builtin.types import CALLBACK

        assert type(ArrayType[CALLBACK].create_field()) is ArrayField
        assert type(PooledType[CALLBACK].create_field()) is PooledField

    def test_an_optional_callback_is_still_a_wrapper_field(self, library_system):
        from haywire.barn.builtin.types import CALLBACK, OPTIONAL

        field = OPTIONAL[CALLBACK].create_field()

        assert field.accepts_absence()
        assert field.get_stored_type() is CALLBACK

    def test_a_data_type_keeps_its_field_class(self, library_system):
        from haywire.barn.builtin.types import FLOAT
        from haywire.barn.builtin.types.specs import FLOATField

        assert type(FLOAT.create_field()) is FLOATField
```

- [ ] **Step 2: Run them (red)**

Run: `uv run pytest tests/core/test_types/test_wire_holds_absence.py -q -p no:randomly`
Expected: fail with `AttributeError: ... holds_absence`, `accepts_absence()` False, and the `@type(default=None)` refusals. `TestWhatIsNotWrapped` passes already (it guards the change).

- [ ] **Step 3: The wire attribute**

In `wire.py`, add to `WireType`'s class attributes after `arrow_at`:

```python
    holds_absence: ClassVar[bool] = False
```

and to its `Attributes:` docstring:

```
        holds_absence: Fields of types declared on this wire type can hold ``None``,
            meaning "no value", and pools of them drop an absent entry.
```

In `wires.py`, `CallbackWire` gains `holds_absence = True`, and its docstring a line: "A callback port can be absent: `None` is no subscription."

- [ ] **Step 4: `BaseField._default_instance`**

In `fields.py`, `BaseField`:

```python
    _container: BaseType | None = field(init=False, repr=False)

    def __post_init__(self):
        """Initialize complex field with default instance"""
        super().__post_init__()
        self._container = self._default_instance()

    def _default_instance(self) -> BaseType | None:
        """Return the own value this field starts and resets to: the type built from the default kwargs."""
        # type_cls is type[IType] at the base; for BaseField it's always type[BaseType].
        return cast(BaseType, self.type_cls(**self.default_kwargs))

    def _get_own(self) -> BaseType | None:
        """Return the instance, or ``None`` for an absent value."""
        return self._container

    def reset(self) -> None:
        """Reset to default value"""
        self._container = self._default_instance()
        self.is_dirty = True
```

`BaseField.to_dict` gains `assert self._container is not None  # a field holding None is absence-tolerant; see _field_holding_absence` before its `return`. (Task 3 moves it into a hook.) Fix whatever mypy reports from the widened `_container` type.

- [ ] **Step 5: `_field_holding_absence`**

In `base.py`, after `_absence_tolerant_field`:

```python
#: Absence-holding field classes, keyed by the field class they extend.
_FIELDS_HOLDING_ABSENCE: "dict[type, type]" = {}


def _field_holding_absence(base_field_cls: type) -> type:
    """Return *base_field_cls* extended to hold ``None`` as its own value, keeping its stored type.

    For a type whose wire type ``holds_absence``. A ``PrimitiveField`` subclass
    stores ``None`` past its own coercion; a ``BaseField`` subclass does too and
    also starts and resets absent when its default kwargs are empty. Any other
    field class is returned unchanged: it decides for itself what it holds.
    Cached, so one field class yields one extension.
    """
    from .fields import BaseField, PrimitiveField

    cached = _FIELDS_HOLDING_ABSENCE.get(base_field_cls)
    if cached is not None:
        return cached

    if issubclass(base_field_cls, PrimitiveField):

        class _PrimitiveHoldingAbsence(base_field_cls):  # type: ignore[valid-type,misc]
            def _set_own(self, value: Any) -> None:
                if value is None:
                    # Past the subclass's own _set_own, whose coercion rejects None.
                    PrimitiveField._set_own(self, None)
                    return
                super()._set_own(value)

            def accepts_absence(self) -> bool:
                """Always True: a field on a wire that holds absence."""
                return True

        extended: type = _PrimitiveHoldingAbsence
    elif issubclass(base_field_cls, BaseField):

        class _BaseHoldingAbsence(base_field_cls):  # type: ignore[valid-type,misc]
            def _default_instance(self) -> Any:
                # Empty default kwargs mean absent (Q22), not the type built with no arguments.
                return super()._default_instance() if self.default_kwargs else None

            def _set_own(self, value: Any) -> None:
                if value is None:
                    self._container = None
                    return
                super()._set_own(value)

            def accepts_absence(self) -> bool:
                """Always True: a field on a wire that holds absence."""
                return True

        extended = _BaseHoldingAbsence
    else:
        return base_field_cls

    extended.__name__ = f"{base_field_cls.__name__}HoldingAbsence"
    extended.__qualname__ = extended.__name__
    _FIELDS_HOLDING_ABSENCE[base_field_cls] = extended
    return extended
```

- [ ] **Step 6: `create_field` applies it**

In `interface.py`, `create_field`, replace the last line:

```python
        from haywire.core.types.base import _field_holding_absence
        from haywire.core.types.wire import declaring_type_of

        field_class = cls.field_class
        declared = declaring_type_of(cls)
        # Only a type declaring the wire itself: a container or wrapper of one keeps its own field.
        if declared is not None and declared[0] is cls and declared[1].holds_absence:
            field_class = _field_holding_absence(field_class)
        return field_class(type_cls=cls, default_kwargs=default_kwargs)
```

Add to its docstring: "A type that declares a wire type which ``holds_absence`` gets a field that can hold ``None`` (see ``_field_holding_absence``)." Check for an import cycle by importing `haywire.core.types` in a fresh interpreter.

- [ ] **Step 7: `@type(default=None)`**

In `decorator.py`, replace the block from `# Normalize and validate default` through the primitive refusal with:

```python
        wire = identity_dict.get("wire_type")
        holds_absence = wire is not None and wire.holds_absence
        if holds_absence and identity_dict["default"] is None:
            # On a wire that holds absence, no default means a field that starts absent (Q22).
            identity_dict["default"] = {}
        else:
            identity_dict["default"] = normalize_and_validate_default(
                identity_dict["default"], inner_cls, context="@type decorator"
            )
        # A primitive instance cannot hold None, so a missing value only crashes at the first save.
        if (
            issubclass(inner_cls, PrimitiveType)
            and not holds_absence
            and identity_dict["default"].get("value") is None
        ):
            raise TypeError(...)  # message unchanged
```

In its docstring, `default`'s entry becomes: "Dict of constructor kwargs for the default instance. On a wire type that ``holds_absence``, ``None`` means the type's fields start absent." Fix the doc drift the design names: any "DATA, CTRL, or NONE" wording at `decorator.py` and `identity.py` (`grep -n "CTRL" packages/haywire-core/src/haywire/core/types/decorator.py packages/haywire-core/src/haywire/core/types/identity.py`) is replaced by the wire type wording already used in the `wire_type` entries.

- [ ] **Step 8: Green, neighbourhood, commit**

Run: `uv run pytest tests/core/test_types/test_wire_holds_absence.py tests/core/test_types/test_callback_values.py tests/core/test_types/test_wrapper_type.py tests/core/test_types/test_type_rules.py tests/core/test_types/test_primitive_type_default.py -q -p no:randomly`

Expected: all pass except two assertions in `test_callback_values.py` that encode the old storage: `test_a_callback_field_holds_no_absence` and `TestDataclassCallbackField::test_it_keeps_plain_storage`. Delete both (behaviour change 3; Task 4 rewrites the file). Rerun green.

Ruff check and mypy on the touched files, the pre-commit gate, then:

```bash
git add packages/haywire-core/src/haywire/core/types/wire.py packages/haywire-core/src/haywire/barn/builtin/wires.py packages/haywire-core/src/haywire/core/types/fields.py packages/haywire-core/src/haywire/core/types/base.py packages/haywire-core/src/haywire/core/types/interface.py packages/haywire-core/src/haywire/core/types/decorator.py packages/haywire-core/src/haywire/core/types/identity.py tests/core/test_types/test_wire_holds_absence.py tests/core/test_types/test_callback_values.py
git commit -m "feat(types): a wire type that holds absence gives its types fields that hold None

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Serialization as a template method; arrays and maps saved

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/fields.py` (`DataField` serialization block at 254-286; `PrimitiveField` 351-376; `BaseField` 434-455; new module functions)
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/add.py:48-52`
- Modify: `barn/haybale-core/haybale_core/types/array_type.py`
- Modify: `barn/haybale-example/haybale_example/types/maps_string_type.py`
- Modify: `packages/haywire-core/src/haywire/core/types/port.py:994` (`_serialize_value -> dict | None`)
- Modify: `packages/haywire-core/src/haywire/ui/panel/port_default_widget_model.py:76` (`as_default -> dict[str, Any] | None`)
- Create: `tests/core/test_types/test_field_serialization.py`

**Interfaces:**
- Consumes: Task 2's absence-holding fields (`CALLBACK.create_field().accepts_absence()`).
- Produces: `DataField.to_dict() -> dict | None`, `DataField.from_dict(data: dict | None) -> None`, hooks `_own_to_dict() -> dict` and `_own_from_dict(data: dict) -> None`; `element_to_dict(element_type: type[IType], value: Any) -> dict | None`, `element_from_dict(element_type: type[IType], data: dict | None) -> Any` in `haywire.core.types.fields`.

The serialized shape of a container item is whatever a field of its element type writes (`{"value": 5.0}` for a `FLOAT`, the dataclass dict for a `BaseType`, `null` for an absent callback). Port defaults (`default_kwargs`) stay constructor kwargs, a raw list, as today.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_types/test_field_serialization.py`:

```python
"""Field serialization: absence saves as null, a present value through the field's hook (Q14, Q25)."""

import json
from dataclasses import dataclass

import pytest

pytestmark = pytest.mark.integration


def _round_trip(type_cls, value):
    """Save a field of *type_cls* holding *value* through JSON and load it into a fresh field."""
    field = type_cls.create_field()
    field.set_value(value)
    saved = json.loads(json.dumps(field.to_dict()))
    restored = type_cls.create_field()
    restored.from_dict(saved)
    return saved, restored.get_value()


class TestAbsence:
    def test_an_absent_callback_saves_null_and_loads_absent(self, library_system):
        from haywire.barn.builtin.types import CALLBACK

        saved, loaded = _round_trip(CALLBACK, None)

        assert saved is None
        assert loaded is None

    def test_an_absent_dataclass_saves_null_and_loads_absent(self, library_system):
        from haywire.barn.builtin.wires import CallbackWire
        from haywire.core.types import BaseType
        from haywire.core.types import type as type_dec

        @type_dec(wire_type=CallbackWire, label="Probe Record", default=None)
        @dataclass
        class PROBE_RECORD(BaseType):
            name: str = ""

        assert _round_trip(PROBE_RECORD, None) == (None, None)
        assert _round_trip(PROBE_RECORD, PROBE_RECORD(name="n"))[1] == PROBE_RECORD(name="n")

    def test_a_present_callback_round_trips(self, library_system):
        from haywire.barn.builtin.types import CALLBACK

        assert _round_trip(CALLBACK, "tick")[1] == "tick"

    def test_null_into_a_field_that_cannot_hold_absence_raises(self, library_system):
        from haywire.barn.builtin.types import FLOAT

        with pytest.raises(TypeError, match="absence"):
            FLOAT.create_field().from_dict(None)


class TestOptional:
    def test_an_absent_optional_saves_null(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        assert _round_trip(OPTIONAL[INT], None) == (None, None)

    def test_a_saved_null_value_key_still_loads_absent(self, library_system):
        from haywire.barn.builtin.types import INT, OPTIONAL

        field = OPTIONAL[INT].create_field(default_override={"value": 3})

        field.from_dict({"value": None})

        assert field.get_value() is None


class TestContainers:
    def test_an_array_value_survives_save_and_load(self, library_system):
        from haybale_core.types import ArrayType

        from haywire.barn.builtin.types import FLOAT

        assert _round_trip(ArrayType[FLOAT], [5.0, 6.0])[1] == [5.0, 6.0]

    def test_an_array_of_callbacks_keeps_an_absent_item(self, library_system):
        from haybale_core.types import ArrayType

        from haywire.barn.builtin.types import CALLBACK

        assert _round_trip(ArrayType[CALLBACK], ["a", None])[1] == ["a", None]

    def test_a_map_value_survives_save_and_load(self, library_system):
        from haybale_example.types.maps_string_type import MapsStringType

        from haywire.barn.builtin.types import FLOAT

        assert _round_trip(MapsStringType[FLOAT], {"a": 1.0, "b": 2.0})[1] == {"a": 1.0, "b": 2.0}

    def test_an_array_port_value_survives_the_port_block(self, library_system):
        from haybale_core.types import ArrayType

        from haywire.barn.builtin.types import FLOAT
        from haywire.core.types import DataPort, PortType
        from haywire.core.types.enums import StoreStrategy

        array = ArrayType[FLOAT]
        port = DataPort(
            registry_id="a",
            registry_key=array.class_identity.registry_key,
            label="A",
            id="a",
            type_cls=array,
            port_type=PortType.OUTLET,
        )
        port.store_strategy = StoreStrategy.ALWAYS
        port.set_value([5.0, 6.0])
        spec = json.loads(json.dumps(port.to_dict(include_data=True)))
        port.set_value([])

        port._data.from_dict(spec["field_data"])

        assert port.get_value() == [5.0, 6.0]


def test_an_add_slot_still_saves_its_placeholder(library_system):
    from haywire.barn.builtin.types import ADD

    assert ADD.create_field().to_dict() == {"value": None}
```

- [ ] **Step 2: Run them (red)**

Run: `uv run pytest tests/core/test_types/test_field_serialization.py -q -p no:randomly`
Expected: the absence tests fail (`PrimitiveField.to_dict` builds `CALLBACK(value=None)`, which falls back to `""`, so `saved == {"value": ""}`; `BaseField.to_dict` hits the assert), `test_null_into_a_field_that_cannot_hold_absence_raises` fails, the OPTIONAL null test fails (`{"value": None}`), the container tests fail (the stub saves `{"value": []}`). `test_a_saved_null_value_key_still_loads_absent`, `test_a_present_callback_round_trips` and the ADD test pass already.

- [ ] **Step 3: The template in `DataField`**

Replace `DataField`'s `to_dict` and `from_dict` with:

```python
    def to_dict(self) -> dict | None:
        """Return the own value as JSON-ready data, or ``None`` (JSON null) for absence.

        A field that ``accepts_absence()`` and holds no own value saves ``None``;
        any other value goes through ``_own_to_dict``.

        Raises:
            TypeError, ValueError: The own value is not a valid value of the field's type.
        """
        if self.accepts_absence() and self._get_own() is None:
            return None
        return self._own_to_dict()

    def from_dict(self, data: dict | None) -> None:
        """Restore the own value from what ``to_dict`` returned.

        Raises:
            TypeError: *data* is ``None`` and this field cannot hold absence.
        """
        if data is None:
            if not self.accepts_absence():
                raise TypeError(
                    f"{type(self).__name__} of {self.type_cls.__name__} cannot hold absence, got null"
                )
            self._set_own(None)
        else:
            self._own_from_dict(data)
        self.is_dirty = True

    def _own_to_dict(self) -> dict:
        """Serialize a present own value. The default returns the type's declared default."""
        if hasattr(self.type_cls, "class_identity"):
            default_dict = getattr(self.type_cls.class_identity, "default", None)
            if isinstance(default_dict, dict):
                return default_dict
        return {}

    def _own_from_dict(self, data: dict) -> None:
        """Restore a present own value from ``_own_to_dict`` output. The default resets the field."""
        self.reset()
```

Add the module functions after `DataField`:

```python
def element_to_dict(element_type: "type[IType]", value: Any) -> dict | None:
    """Return *value* serialized the way a field of *element_type* serializes its own value.

    For a container field saving its items one by one.
    """
    cell = element_type.create_field()
    cell.set_value(value)
    return cell.to_dict()


def element_from_dict(element_type: "type[IType]", data: dict | None) -> Any:
    """Return the value a field of *element_type* holds after loading *data*; see ``element_to_dict``."""
    cell = element_type.create_field()
    cell.from_dict(data)
    return cell.get_value()
```

- [ ] **Step 4: Move the field overrides to the hooks**

- `PrimitiveField`: rename `to_dict` to `_own_to_dict` (return `dict`) and `from_dict` to `_own_from_dict(self, data: dict)`, whose body is only `self._value = self.type_cls.from_dict(data)` (the base sets `is_dirty`). Docstrings: one line each, "Serialize the present value through the type's ``to_dict``." / "Restore a present value through the type's ``from_dict``."
- `BaseField`: same rename; `_own_to_dict` keeps the Task 2 assert and returns `self._container.to_dict()`; `_own_from_dict` is `self._container = self.type_cls.from_dict(data)`.
- `ADDField` (`add.py`): `to_dict`/`from_dict` become `_own_to_dict` (returns `{"value": None}`) and `_own_from_dict` (returns `None`).

Confirm no other field-level override remains: `grep -rn "def to_dict\|def from_dict" --include='*.py' packages barn | grep -i field` lists none outside these (type classmethods such as `INT.from_dict` are not fields, C4).

- [ ] **Step 5: Array and map hooks**

`ArrayField` (`array_type.py`), with `from haywire.core.types.fields import element_from_dict, element_to_dict`:

```python
    def _own_to_dict(self) -> dict:
        """Return ``{"value": [...]}`` with each item as a field of the element type saves it."""
        element = self.type_cls.element_type_cls
        return {"value": [element_to_dict(element, item) for item in self._items]}

    def _own_from_dict(self, data: dict) -> None:
        """Restore the items from ``_own_to_dict`` output."""
        element = self.type_cls.element_type_cls
        self._items = [element_from_dict(element, item) for item in data.get("value", [])]
```

`MapsStringField` (`maps_string_type.py`) the same with a dict comprehension over `self._items.items()` / `data.get("value", {}).items()`, docstrings saying `{"value": {key: item}}`.

- [ ] **Step 6: Widen the return types**

- `DataPort._serialize_value -> dict | None` (docstring: "Return the field's ``to_dict()``; ``None`` for an absent value.").
- `PortDefaultWidgetModel.as_default -> dict[str, Any] | None` (docstring: "The staged value in the shape ``DataPort.default`` takes; ``None`` when it is absent, which means the type's default.").
- Run mypy on the whole set and fix each new error at its site; widen, never `cast` away a real `None`.

- [ ] **Step 7: Green and the existing serialization tests**

Run: `uv run pytest tests/core/test_types/ tests/core/test_graph/ tests/core/test_undo/ tests/ui/widget/ -q -p no:randomly -n 4`

Expected: all pass, except `test_callback_values.py::TestOptionalKeepsAbsence::test_an_optional_field_saves_absence_as_a_null_value`, which asserted `{"value": None}`: change its expectation to `field.to_dict() is None` (behaviour change 4). If `tests/ui/widget/test_optional_widget.py` or a settings test reads an OPTIONAL port's `field_data` shape, change it the same way and name it in the commit body; anything else red is a bug.

- [ ] **Step 8: Ruff, mypy set, gate, commit (haybale-example and haybale-core are in this repo)**

```bash
git add packages/haywire-core/src/haywire/core/types/fields.py packages/haywire-core/src/haywire/barn/builtin/types/add.py packages/haywire-core/src/haywire/core/types/port.py packages/haywire-core/src/haywire/ui/panel/port_default_widget_model.py barn/haybale-core/haybale_core/types/array_type.py barn/haybale-example/haybale_example/types/maps_string_type.py tests/core/test_types/test_field_serialization.py tests/core/test_types/test_callback_values.py
git commit -m "feat(fields): absence saves as null; array and map port values are saved

DataField.to_dict/from_dict handle absence and hand a present value to
_own_to_dict/_own_from_dict. OPTIONAL saves null; {\"value\": null} still loads.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Callback values can be absent

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/callback.py`
- Modify: `barn/haybale-testing/haybale_testing/types/test_types.py:145-158` (`TEST_RECORD_CALLBACK`)
- Modify: visiongraph `barn/haybale-visiongraph/haybale_visiongraph/types/multiframe_callback_type.py`
- Modify: `barn/haybale-core/haybale_core/types/pooled_type.py`
- Create: `tests/core/test_types/test_callback_absence.py`
- Modify: `tests/core/test_types/test_callback_values.py` (rewritten), `tests/core/test_graph/test_callback_boundary_relay.py:93`, `tests/core/test_edge/test_disconnect_semantics.py:194`

**Interfaces:**
- Consumes: Task 1's guards (the echo guard keeps an absent relay from firing on an absent write), Task 2's fields, Task 3's null serialization.
- Produces: `PooledField.accepts_absence()` true for an element that holds absence; `_drops_default` and `_element_default` gone (deletion 9).

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_types/test_callback_absence.py`:

```python
"""A callback port with no subscription is absent: `None`, saved as null, dropped by pools (Q14, Q22, Q23)."""

from typing import Any, cast

import pytest

from tests.conftest import make_edge, make_node
from tests.core.test_graph.callback_group import EMIT, LISTEN, build_group, subscriptions

pytestmark = pytest.mark.integration


def _split_with_reroute(graph, edge_id: str) -> str:
    """Split *edge_id* with a reroute node the way the canvas does, returning the reroute's id."""
    from haywire.barn.builtin.nodes.reroute import RerouteNode
    from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

    action = SplitEdgeWithRerouteAction(
        graph=cast(Any, graph),
        edge_id=edge_id,
        position=(200.0, 0.0),
        registry_key=RerouteNode.class_identity.registry_key,
    )
    action._execute_impl()
    reroute_id = action.reroute_node_id
    assert reroute_id is not None
    return reroute_id


def _port_block(serialized_node: dict, port_id: str) -> dict:
    """The serialized port *port_id* inside a node as `wrapper.serialize()` or `graph.to_dict()` writes it."""
    return serialized_node.get("node_data", serialized_node)["ports"][port_id]


class TestTypes:
    @pytest.mark.parametrize(
        "path",
        [
            "haywire.barn.builtin.types:CALLBACK",
            "haybale_testing.types:TEST_RECORD_CALLBACK",
        ],
    )
    def test_a_callback_type_starts_absent(self, library_system, path):
        import importlib

        module, name = path.split(":")
        callback = getattr(importlib.import_module(module), name)

        assert callback.class_identity.default == {}
        assert callback.create_field().get_value() is None


class TestPools:
    def test_absence_from_a_source_removes_its_entry(self, library_system):
        from haybale_core.types import PooledType

        from haywire.barn.builtin.types import CALLBACK

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")
        pool.set_value("b", source_id="e2")

        pool.set_value(None, source_id="e1")

        assert pool.get_value() == {"e2": "b"}
        assert pool.accepts_absence()

    def test_an_empty_name_is_a_subscription(self, library_system):
        from haybale_core.types import PooledType

        from haywire.barn.builtin.types import CALLBACK

        pool = PooledType[CALLBACK].create_field()

        pool.set_value("", source_id="e1")

        assert pool.get_value() == {"e1": ""}

    def test_a_dataclass_with_an_empty_name_is_a_subscription(self, library_system):
        from haybale_core.types import PooledType
        from haybale_testing.types import TEST_RECORD_CALLBACK

        pool = PooledType[TEST_RECORD_CALLBACK].create_field()

        pool.set_value(TEST_RECORD_CALLBACK(), source_id="e1")

        assert pool.get_value() == {"e1": TEST_RECORD_CALLBACK()}

    def test_absence_without_a_source_changes_nothing(self, library_system):
        from haybale_core.types import PooledType

        from haywire.barn.builtin.types import CALLBACK

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")

        pool.set_value(None)

        assert pool.get_value() == {"e1": "a"}

    def test_a_pool_of_data_keeps_a_none_entry(self, library_system):
        from haybale_core.types import PooledType

        from haywire.barn.builtin.types import FLOAT

        pool = PooledType[FLOAT].create_field()
        pool.set_value(None, source_id="e1")

        assert not pool.accepts_absence()
        assert pool.get_value() == {"e1": None}


class TestPorts:
    def test_an_unlinked_dataclass_callback_inlet_reads_absent(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.record_callback_nodes import TestRecordEmitNode, TestRecordEventNode

        graph = graph_with_library_system
        event = make_node(graph, TestRecordEventNode.class_identity.registry_key, position=(0, 0))
        emit = make_node(graph, TestRecordEmitNode.class_identity.registry_key, position=(400, 0))
        edge = make_edge(graph, event.node_id, "subscription", emit.node_id, "subscriptions")
        reroute_id = _split_with_reroute(graph, edge.edge_id)
        upstream = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == reroute_id)

        graph.remove_edge_wrapper(upstream.edge_id)

        assert graph.node_wrappers[reroute_id].node.ports["in"].get_value() is None
        assert emit.node.ports["subscriptions"].get_value() == {}


class TestEverySaveGoesThroughTheField:
    """Each path that writes port values writes an absent callback as null and loads it absent."""

    @staticmethod
    def _listener_set_absent(graph):
        listener = make_node(graph, LISTEN, position=(0, 0))
        listener.node.out("listen_callback", None)  # its default is its node id; absence must survive
        return listener

    def test_the_graph_file(self, graph_with_library_system):
        graph = graph_with_library_system
        listener = self._listener_set_absent(graph)
        data = graph.to_dict()
        assert _port_block(data["nodes"][listener.node_id], "listen_callback")["field_data"] is None

        graph.clear()
        graph.load_from_dict(data)

        assert graph.node_wrappers[listener.node_id].node.value("listen_callback") is None

    def test_a_node_copy_and_undo_snapshot(self, graph_with_library_system):
        """Clipboard and the undo actions (Collapse, Expand, Detach, Promote) serialize through `wrapper.serialize`."""
        from haywire.core.graph.clipboard import build_clipboard_payload

        graph = graph_with_library_system
        listener = self._listener_set_absent(graph)
        payload = build_clipboard_payload(graph, [listener.node_id], [], session_id="s")
        node_data = payload["nodes"][listener.node_id]["node_data"]
        assert _port_block(node_data, "listen_callback")["field_data"] is None

        restored = make_node(graph, LISTEN, position=(500, 0))
        restored.node._initialize_from_dict(node_data)

        assert restored.node.value("listen_callback") is None

    def test_a_subgraph_definition(self, graph_with_library_system):
        """`_DropSubgraph` and the clipboard's subgraphs serialize through `definition.to_dict`."""
        group = build_group(graph_with_library_system)
        outlet = group.input_node.node.ports["sub_in"]
        outlet.set_value("a")
        outlet.set_value(None)

        data = group.definition.to_dict(include_data=True)

        assert _port_block(data["nodes"][group.input_node.node_id], "sub_in")["field_data"] is None


class TestOldSaves:
    def test_a_relay_with_something_upstream_takes_its_value_from_upstream_on_load(
        self, graph_with_library_system
    ):
        """Guards Q23's accepted break: only an orphaned relay keeps a stale saved value."""
        graph = graph_with_library_system
        listener = make_node(graph, LISTEN, position=(0, 0))
        emitter = make_node(graph, EMIT, position=(600, 0))
        edge = make_edge(graph, listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
        reroute_id = _split_with_reroute(graph, edge.edge_id)
        data = graph.to_dict()
        for port_id in ("in", "out"):
            _port_block(data["nodes"][reroute_id], port_id)["field_data"] = {"value": "stale"}

        graph.clear()
        graph.load_from_dict(data)

        emitter = graph.node_wrappers[emitter.node_id]
        listener = graph.node_wrappers[listener.node_id]
        assert subscriptions(emitter) == [listener.node.value("listen_callback")]
```

Adjust `_port_block` and the `payload["nodes"][...]` path to the real shapes once (print one payload); keep the assertions.

- [ ] **Step 2: Run them (red)**

Run: `uv run pytest tests/core/test_types/test_callback_absence.py -q -p no:randomly`
Expected: `TestTypes` fails (default `{"value": ""}`), the pool tests fail (`""` and the default dataclass are dropped; `None` is stored), `TestPorts` fails (`""`-named dataclass), `TestEverySaveGoesThroughTheField` passes already for `CALLBACK` (Tasks 2 and 3), and `TestOldSaves` passes (it guards). Record which passed.

- [ ] **Step 3: Declare absence**

- `callback.py`: `default=None`. Docstring:

  ```
      """Callback signal: the name a listener subscribes under.

      It travels like a `STRING`, has no widget, and a port stores it only when its
      node set it. An absent value means no subscription: an emitter's pool drops it.
      """
  ```
- `test_types.py`: `TEST_RECORD_CALLBACK` `default=None`.
- visiongraph `multiframe_callback_type.py`: `default=None`; module docstring gains "An absent value (`None`) means no subscription; the emitter's pool drops it."

- [ ] **Step 4: Pools drop absence (deletion 9)**

In `pooled_type.py`:
- delete `_drops_default`, `_element_default` and their `__post_init__` block;
- add `_element_holds_absence: bool = field(default=False, init=False, repr=False)`, set in `__post_init__`:

  ```python
          # Absence from a source means the source has no value: its entry goes.
          element = getattr(self.type_cls, "element_type_cls", None)
          create = getattr(element, "create_field", None)
          self._element_holds_absence = create is not None and create().accepts_absence()
  ```
- `accepts_absence` returns `self._element_holds_absence` (docstring: "True when the element type's fields hold absence; an absent value then removes its source's entry.");
- `set_value`'s sentinel block becomes:

  ```python
          if value is None and self._element_holds_absence:
              # With no source there is no entry to end.
              if source_id is not None:
                  self.remove_source(source_id)
              return
  ```
  and its docstring's last paragraph: "For an element type that holds absence, `None` removes the source's entry."
- drop the now-unused `wire_type_of` and `WireRole` imports only if nothing else uses them (`_configure_port` still uses `WireRole`).

- [ ] **Step 5: The old-value assertions (behaviour change 3)**

- `tests/core/test_types/test_callback_values.py`: replace the file with the parts still true. Keep `test_a_callback_value_saves_and_loads`, `test_it_still_travels_as_callback`, `test_a_present_value_is_still_type_checked`, the two `TestOptionalKeepsAbsence` tests not about saving, and nothing about pools (now in `test_callback_absence.py`). Its module docstring: "Callback values: present values save and travel as their type; absence lives in `test_callback_absence.py`."
- `test_callback_boundary_relay.py:93`: `assert grown.data.get_own_value() is None`.
- `test_disconnect_semantics.py:194`: `... .ports["out"].get_value() is None`.

Any other test asserting `""` on a callback port or relying on a dropped default is the same change: edit it and name it in the commit body.

- [ ] **Step 6: Green, then the callback neighbourhood and visiongraph**

Run: `uv run pytest tests/core/test_types/ tests/core/test_edge/ tests/core/test_graph/ tests/core/test_macro/ tests/core/test_undo/ tests/barn/ -q -p no:randomly -n 4`, then the visiongraph tests. Expected: green.

- [ ] **Step 7: Saved graphs still load**

Run: `HW_GRAPH_SNAPSHOT=/tmp/graph_snapshot_after_5_3.json uv run pytest tests/core/test_zz_graph_snapshot.py -q -p no:randomly`, then `diff /tmp/graph_snapshot_before_5_3.json /tmp/graph_snapshot_after_5_3.json`.
Expected: no difference. Any node or edge that changed validity is a bug: stop and report it. Delete the scratch test file afterwards.

- [ ] **Step 8: Commit, in both repos**

Commit `barn/haybale-testing` first:

```bash
git add barn/haybale-testing/haybale_testing/types/test_types.py
git commit -m "test(testing): TEST_RECORD_CALLBACK is absent by default

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Run the pre-commit gate, then:

```bash
git add packages/haywire-core/src/haywire/barn/builtin/types/callback.py barn/haybale-core/haybale_core/types/pooled_type.py tests/core/test_types/test_callback_absence.py tests/core/test_types/test_callback_values.py tests/core/test_graph/test_callback_boundary_relay.py tests/core/test_edge/test_disconnect_semantics.py
git commit -m "feat(callbacks): no subscription is absence, and pools drop it

CALLBACK defaults to None; a pool of a callback element drops a None entry in
place of the element-default sentinel, so an empty name is an ordinary value.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

In the visiongraph repo:

```bash
git -C /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph add barn/haybale-visiongraph/haybale_visiongraph/types/multiframe_callback_type.py
git -C /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph commit -m "feat(types): MULTIFRAME_CALLBACK is absent by default

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Live checks (controller with the user)

Callbacks run on hardware threads that no unit test reaches, and visiongraph's tests do not cover the OAK-D callback path.

- [ ] **Step 1:** Start the studio (`haywire-live-studio` skill). Build Tick Emit ← Tick (event) through one reroute, run it, and check that ticks arrive. Delete the edge before the reroute: ticks stop, and the error ledger stays empty.
- [ ] **Step 2:** Wire two callback reroutes into a loop on the canvas: no hang, no traceback.
- [ ] **Step 3:** With the user, open `graphs/oakNwebCam.haywire` and `graphs/webcam.haywire` from visiongraph, run them, and confirm frames reach the event nodes; disconnect and reconnect a subscription edge while running.
- [ ] **Step 4:** Save a graph holding an orphaned callback reroute and reload it: the reroute's outlet is absent and the file shows `"field_data": null`.

Record each result in the ledger. A failure stops the plan.

---

### Task 6: ADR, docs, glossary, generated library docs, status

**Files:**
- Create: `docs/adr/0046-callback-absence-and-immediate-guards.md`
- Modify: `docs/adr/0033-absence-is-a-type.md`, `docs/adr/0039-propagation-mode-replaces-is-lazy.md` (only if it still describes the empty-name sentinel), `docs/architecture/execution/callbacks/callbacks-arch.md`, `docs/components/datatypes/datatype-canon.md`, `docs/reference/glossary.md`, generated `barn/*/docs`, `docs/superpowers/plans/2026-10-02-wire-types.md` (not committed)

- [ ] **Step 1: ADR 0046**, front matter like ADR 0044 (`name: callback-absence-and-immediate-guards`, `status: accepted`, `see-also: ADR-0033, ADR-0039, ADR-0040, ADR-0041, ADR-0042`, `level: architectural`). Sections:
  - **Context:** the empty-name sentinel (step 2) made `""` mean "no subscription" by an in-band value, and a pool dropped any value equal to its element's default, so a dataclass subscription whose fields matched the default vanished. An immediate edge had no equality check and no loop protection: two callback reroutes wired into each other recursed until `RecursionError`.
  - **Decision:** a wire type declares `holds_absence`; the types declared on it get fields that hold `None` (`_field_holding_absence`, primitive and `BaseField` storage; containers and wrappers keep their own); `default=None` means an empty default and a field that starts absent (Q22); `DataField` serializes absence as JSON `null` in the base, a present value in hooks; pools drop absence. On the immediate path, an unchanged value fires nothing (echo guard), and a write reaching an inlet whose `on_change` is running on the same thread is dropped, not stored, and logged (Q13b, Q24).
  - **Consequences:** the accepted break of Q23; `OPTIONAL` saves `null`; array and map values are now saved (Q25); a loop's last hop disagrees with its upstream outlet until the next write; `ControlWire` holds no absence, so a pool of `EXEC` stays refused (F12, C7).
- [ ] **Step 2: ADR 0033**: `status: superseded-in-part by ADR-0046` and, under the title, the note: "> **Absence beyond `PrimitiveField` storage**: on a wire type that `holds_absence`, a `BaseField` type holds absence too ([ADR 0046](0046-callback-absence-and-immediate-guards.md)); `OPTIONAL` itself is unchanged, and saves absence as `null`."
- [ ] **Step 3: callbacks-arch** (`callbacks-arch.md`): rewrite line 66's paragraph: removing any edge on the path shows the next port's own value, which for a callback port is absent; the reroute forwards absence, and the emitter's pool removes the entry keyed by its edge. Add a section "Loops of immediate edges" (echo guard, re-entrancy guard, the warning, Q24), and the Q33 docs addition: "A relay with something upstream takes its value from upstream on load, not from its own saved value; only an orphaned relay keeps what it saved."
- [ ] **Step 4: datatype-canon**: a `holds_absence` paragraph next to the wire-type description (what it does, `default=None`, containers and wrappers keep their fields), and field serialization (`null` for absence; a custom field implements `_own_to_dict`/`_own_from_dict`, not `to_dict`/`from_dict`).
- [ ] **Step 5: Glossary.**
  - **CALLBACK port**: replace "its default, an empty name, which the emitter treats as no subscription and drops" with "absent (`None`), which the emitter's pool drops".
  - **Wire type**: add `holds_absence` to the attributes it lists.
  - **absence**: add a sentence: "On a wire type that `holds_absence` (the callback wire), absence is also the value of a port with no subscription; it saves as JSON `null`."
  - New **Echo guard** and **Re-entrancy guard** rows (or one **Immediate guards** row): "An edge's write to an immediate inlet that leaves the value its node sees unchanged fires nothing; a write that reaches an inlet whose `on_change` is still running on the same thread closes a loop and is dropped, unstored, with a warning. See ADR 0046." Avoid list: "cycle detection" (nothing is detected ahead of time).
- [ ] **Step 6: Generated library docs.** `uv run haywire docs --all` (shell out, never in-process); review the diff (expect `CALLBACK`'s default and docstring, the probe node in haybale-testing, `MULTIFRAME_CALLBACK`). `uv run mkdocs build` passes as before (the known `--strict` failure is a Small item).
- [ ] **Step 7: Commit docs** (commit `barn/haybale-testing/docs` changes in the same commit; visiongraph's generated docs in its repo):

```bash
git add docs/adr/0046-callback-absence-and-immediate-guards.md docs/adr/0033-absence-is-a-type.md docs/architecture/execution/callbacks/callbacks-arch.md docs/components/datatypes/datatype-canon.md docs/reference/glossary.md barn/*/docs barn/*/README.md barn/*/OVERVIEW.md barn/*/QUICKREF.md
git commit -m "docs: callback absence and the immediate guards (ADR 0046)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(`git add` only the generated files that changed; check `git status` first.)

- [ ] **Step 8: Status (not committed).** In the design doc: row 5.3 → **Landed** on `wire-types-5-1`, detail plan link to `landed/2026-10-04-wire-types-5-3-immediate-path.md`, Next "merge"; F12 ticked with the decision ("kept: absence is per wire, `ControlWire` holds none; see C7"); Small items: the array/map entry marked done (Q25); the decision log gains the confirmed corrections. Move this plan to `landed/`. Update the memory file `project_edge_kinds_disconnect_semantics.md`.

---

### Task 7: Verify the plan

- [ ] **Step 1:** Pre-commit gate, browser tier (rerun once on `test_edge_batch_cost` only), visiongraph tests, the mypy set, `uv run ruff check . && uv run ruff format --check .`. Compare the counts with Task 0's and explain every difference by a test this plan added or deleted.
- [ ] **Step 1b: Benchmark.** Run the `haywire-benchmark` skill before Task 1 (in Task 0, as the baseline) and here. `set_value` is on every node's hot path; Task 1 changes it. Expect flat (~) on every graph case; a regression beyond run-to-run noise on a data-only case is a bug in the branch order of `set_value`. The known ~8% `graph_loop` drift (`internals/handoff/graph-loop-benchmark-drift.md`) predates this plan: compare against the Task 0 run, not older rows.
- [ ] **Step 2:** Re-read every intended behaviour change in Global Constraints and name the test that shows it.
- [ ] **Step 3:** `requesting-code-review` over `wire-types-5-1` since the commit before Task 1, against this plan and the design's 5.3 section.

---

## Self-review (done while writing)

- **Spec coverage.** Guards (Q13b, Q24): Task 1. `holds_absence`, `create_field` wrap, `BaseField` absence, `default=None` (Q14, Q22): Task 2. Null serialization in the base, hooks, array and map fix (Q14, Q25), widened return types: Task 3. `default=None` on the three callback types, pools dropping absence, deletion 9, the five test assertions, Q23's heal: Task 4. OAK-D live check: Task 5. ADR, docs additions (callbacks-arch relay-heals, empty-name unsubscribe), glossary, generated docs: Task 6. F12: C7 and Task 6 Step 8. Every verify-first item of the design's 5.3 section maps to a test: looped reroutes and the pool (`test_immediate_guards.py`), Subgraph relay pair (same), unlink upstream of a reroute and a boundary (existing `test_disconnect_semantics.py` and `test_callback_boundary_relay.py`, kept green), absent save/load primitive and dataclass (`test_field_serialization.py`), every serialize path (`TestEverySaveGoesThroughTheField`), arrays and maps (`TestContainers`), unlinked dataclass inlet (`TestPorts`), relay heals (`TestOldSaves`).
- **Placeholders.** Two deliberate "check the real shape" steps (wrapper id attribute in Task 1 Step 4; serialized node shape in Task 4 Step 1), each with the command to check it. Task 4 Step 7 names the 5.1 snapshot script by path rather than repeating it.
- **Names.** `_fire_immediate(store, value)`, `_firing_inlets`, `_field_holding_absence`, `_default_instance`, `_own_to_dict`/`_own_from_dict`, `element_to_dict`/`element_from_dict`, `_element_holds_absence` and `CallbackRelayProbeNode` are spelled the same in every task.

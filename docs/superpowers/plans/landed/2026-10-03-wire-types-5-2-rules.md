# Rule changes (edge-kinds step 5.2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The framework refuses only what breaks, stated by the mechanism that breaks. A port's link count follows a link ceiling the framework derives, which a port can only narrow. A widget refuses edits on a field that holds no own value instead of crashing. Every value type has a wire type. `OPTIONAL[T]` travels on `T`'s wire type. Two bare `ADD` slots no longer link. A `VISUAL` wire is drawn and saved but never executed.

**Architecture:** No new subsystem. Two read-only field predicates, `DataField.keeps_value_per_source()` and `DataField.accepts_own_value()`, carry the storage facts. `DataPort.takes_many_links` computes the link ceiling on every read from the port's role and its field. `single_link` is the one per-port setting. `@type`, `wires_match`, the edge build and the structural validator change where they encode a rule by category. Each behaviour change lands as its own task with a deliberate test edit.

**Tech Stack:** Python 3.12, pytest (+ xdist, Playwright browser tier), uv, ruff, mypy; Vue 3 (`canvas.vue`) for `_wiresMatch`; NiceGUI widgets.

**Settled in:** [2026-10-02-wire-types.md](2026-10-02-wire-types.md), the step 5 design: Q8b, Q8c, Q9a, Q9c, Q9d and Q21. The 2026-10-03 inquisition on this plan settled Q34 to Q47 (logged in the design's decision table). They reverse the design's link model: wire types carry no link defaults. The framework sets a ceiling by mechanism, and a port can only narrow it.

## Global Constraints

- **Two repos.**
  - This repo: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo`.
  - haybale-visiongraph: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph`, linked here as `barn/haybale-visiongraph`. Edit through the symlink; run git for it in the visiongraph repo.
- **Branch.** Continue on `wire-types-5-1` in both repos (5.1 is landed there, unmerged). Never push; the user pushes.
- **Commit trailer.** Every commit message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Never commit:**
  - `docs/superpowers/plans/` (this plan and the design are left for the user to commit);
  - `internals/`, `.superpowers/`, `.claude/settings.json`;
  - the scratch file `tests/core/test_zz_graph_snapshot.py`.

  Always `git add` explicit paths, never `-A` or `.`.
- **Commit `barn/haybale-testing/` first.** Commit every change there before running the full suite: `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing` in its teardown.
- **Intended behaviour changes.** These are the only ones, each with its test edit named in its task. Any other red behavioural test is a bug: stop and report it.
  1. **Link ceiling** (Q35, Q36, Q43, Q45).
     - A port's link count is `DataPort.takes_many_links`. Outlets take many, except a `SEQUENCE` outlet. Inlets take one, except a `SEQUENCE` or `VISUAL` inlet and an inlet whose field `keeps_value_per_source()`.
     - A callback outlet that declared nothing now takes many, and its pin draws the `_multi` glyph: reroute outlets, boundary slots and card mirrors.
     - `allow_multiple_links` is gone. A saved `allow_multiple_links` key is ignored on load.
     - `single_link=True` narrows a port to one.
     - Farmhand reports `takes_many_links`, and `single_link` when set.
  2. **Widgets** (Q37, Q38): a widget on a field that `accepts_own_value()` is false for (pooled, `ADD`) refuses edits and shows the model again, where it raised before.
  3. **`@type`:**
     - A control or callback type may declare or inherit a widget.
     - A value type with no wire type is refused at decoration (Q40).
  4. **`OPTIONAL[T]`** travels on `T`'s wire type (Q21): `OPTIONAL[EXEC]` is a control pin.
  5. **Two bare `ADD` slots** do not link (9c). A saved edge between two is kept and fails validation.
  6. **Containers:** `ArrayType` of a control or callback element and `PooledType` of a control element are allowed, each only if its end-to-end test passes (Q39).
  7. **An empty array or map port** reads `[]`/`{}` and passes its first write on (Q46).
  8. **`VISUAL` wires** (9d, Q41):
     - The edge builds no adapter chain and no pipe and has no propagation.
     - The validator ignores `VISUAL` pins, except on a reroute.
     - They cross Group boundaries.
- **Out of scope:**
  - 5.3: `holds_absence`, the immediate guards.
  - 5.4: `style`, arrows, the graph tier.
  - 5.5: the annotation node.
  - Also out: the NodeType split, and the Small items other than the falsy array (Q34, Q46).
- **Compare wire types by `.id`**, never with `is` or `issubclass` on the class. Comparing `WireRole` members with `is` is fine.
- **Docstrings and comments** follow `.claude/rules/python-docs.md`. Docstrings of registered components (types, nodes, panels) are displayed: Markdown, single backticks, no reST.
- **"Ruff check"** means both `uv run ruff check <paths>` and `uv run ruff format --check <paths>`; line length 109.
- **Pre-commit gate:** `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`, then `grep -E "^FAILED|^ERROR" /tmp/t.log` and `tail -1 /tmp/t.log`. Timeout at least 600000 ms. Baseline before this plan: 6029 passed, 2 xfailed.
- **Browser tier:** `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`. Baseline 137 passed. One known intermittent failure, `test_edge_batch_cost` (a NiceGUI `build_response` race): rerun the tier once before calling it red.
- **visiongraph tests:** from this repo, `uv run pytest ../haybale-visiongraph/tests -q -p no:randomly`. Baseline 29 passed.
- **mypy set:** `uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/`. Baseline clean.
- **Code lookup:** the repo is indexed by CodeGraph. `codegraph explore "<symbols>"` returns verbatim source plus callers.

---

## The link ceiling

`DataPort.takes_many_links` reads two facts about the port, its **role** and its **storage**. A container has no wire type of its own, so its role is its element's.

| Port | Outlet | Inlet |
|---|---|---|
| `DEPENDENT` (data), `IMMEDIATE` (callback): a value wire | many | one, many when the field `keeps_value_per_source()` |
| `SEQUENCE` (control) | one: the VM keeps one transition per outlet | many |
| `VISUAL` | many | many |
| no wire type: bare `ADD` slot | many | one |

So:
- `OPTIONAL[T]`, `ADD[T]` and `ArrayType[T]` behave as `T`.
- `PooledType[T]` behaves as `T` with its inlet lifted to many, because `PooledField` keeps one value per source.
- `single_link=True` lowers any ceiling to one.

Nothing else writes a link count:
- `_configure_port` keeps the colour and the refusals only;
- mirrors, reroute ports and grown slots start at the ceiling (Q42).

## Names this plan introduces

| Name | Where | Task |
|---|---|---|
| `DataField.keeps_value_per_source()`, `DataField.accepts_own_value()` | `haywire.core.types.fields` | 1, 2 |
| `DataPort.single_link`, `DataPort.takes_many_links` | `haywire.core.types.port` | 1 |
| `EdgeWrapper.carries_values`, `EdgeWrapper._build_drawn_only()` | `haywire.core.edge.edge_wrapper` | 6 |
| `TestVisualWire` | `haybale_testing.wires` | 6 |
| `TEST_VISUAL`, `TEST_VISUAL_COUNT` | `haybale_testing.types` | 6 |
| `ArrayExecProbeNode`, `ArrayCallbackProbeNode`, `PooledExecProbeNode` | `haybale_testing/nodes/testbed/container_signal_probes.py` | 5 |
| `VisualProbeNode` | `haybale_testing/nodes/testbed/visual_probe.py` | 6 |

Removed: `DataPort.allow_multiple_links`.

## File structure

| File | Change | Task |
|---|---|---|
| `packages/haywire-core/src/haywire/core/types/fields.py` | the two predicates | 1, 2 |
| `packages/haywire-core/src/haywire/core/types/port.py` | `single_link`, `takes_many_links`, link block removed, legacy key popped; falsy guards; VISUAL pipes skipped | 1, 5, 6 |
| `packages/haywire-core/src/haywire/core/types/interface.py` | port-kwarg docs, `_configure_port` example | 1 |
| `barn/haybale-core/haybale_core/types/pooled_type.py`, `array_type.py` | no link counts; refusals dropped after tests | 1, 2, 5 |
| `packages/haywire-core/src/haywire/ui/skin/pin_icons.py` | reads `takes_many_links` | 1 |
| `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py` | Farmhand keys | 1 |
| four listener nodes | drop `allow_multiple_links=True` | 1 |
| `packages/haywire-core/src/haywire/ui/widget/base.py`, `binding.py` | own-value guard | 2 |
| `packages/haywire-core/src/haywire/barn/builtin/types/add.py` | `ADDField.accepts_own_value`; docstring | 2, 4 |
| `packages/haywire-core/src/haywire/core/types/decorator.py`, `identity.py` | wire type required, widget rule gone | 3 |
| `packages/haywire-core/src/haywire/barn/builtin/types/optional.py` | no own wire type | 3 |
| `packages/haywire-core/src/haywire/core/types/wire.py`, `canvas.vue` | two wildcards don't match | 4 |
| `subgraph_io.py`, `add_port_test.py`, `adapter/factory.py` | dead ADD↔ADD guards | 4 |
| `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` | VISUAL build | 6 |
| `packages/haywire-core/src/haywire/core/validation/structural_validator.py` | VISUAL pins ignored | 6 |
| `barn/haybale-testing/haybale_testing/wires.py`, `types/test_types.py`, `types/__init__.py`, two testbed modules | test-only wire, types, nodes | 5, 6 |
| docs, ADRs 0043 and 0044, glossary, `.codemap`, generated library docs | | 8 |

---

### Task 0: Baseline (controller)

**Files:** none committed.

- [ ] **Step 1: Confirm the branch and a clean tree**

Run: `git branch --show-current && git status --short` in both repos.
Expected: `wire-types-5-1` in both. Nothing staged; only the user's own uncommitted files.

- [ ] **Step 2: Baselines**

Run the ruff check on the whole repo, the mypy set, the pre-commit gate, the browser tier, the visiongraph tests and `uv run pytest -m perf -q`. Record the counts in the ledger. Expected: as in Global Constraints, perf 7 passed.

- [ ] **Step 3: Snapshot every saved graph**

Recreate the scratch test `tests/core/test_zz_graph_snapshot.py` exactly as 5.1's Task 0 wrote it ([2026-10-03-wire-types-5-1-sweep.md](landed/2026-10-03-wire-types-5-1-sweep.md), "Task 0", Step 3). Add a module-level skip when `HW_GRAPH_SNAPSHOT` is unset:

```python
if "HW_GRAPH_SNAPSHOT" not in os.environ:
    pytest.skip("set HW_GRAPH_SNAPSHOT to write the snapshot", allow_module_level=True)
```

Run: `HW_GRAPH_SNAPSHOT=/tmp/graph_snapshot_5_2_before.json uv run pytest tests/core/test_zz_graph_snapshot.py -q -p no:randomly`.
Expected: 1 passed. The file is never committed.

---

### Task 1: The link ceiling

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/types/fields.py` (`DataField`)
  - `barn/haybale-core/haybale_core/types/pooled_type.py`, `barn/haybale-core/haybale_core/types/array_type.py`
  - `packages/haywire-core/src/haywire/core/types/port.py`
  - `packages/haywire-core/src/haywire/core/types/interface.py`
  - `packages/haywire-core/src/haywire/ui/skin/pin_icons.py`
  - `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`
  - `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` (docstring)
  - the four listener nodes: `barn/haybale-core/haybale_core/nodes/events/tick_event.py`, `barn/haybale-example/haybale_example/nodes/emits/custom_callback.py`, `barn/haybale-testing/haybale_testing/nodes/testbed/custom_callback_node.py`, `barn/haybale-testing/haybale_testing/nodes/testbed/record_callback_nodes.py`
- Test:
  - create `tests/core/test_types/test_link_ceiling.py`;
  - modify `tests/core/test_types/test_data_inlet_arity.py`, `tests/core/test_types/test_port_derives_from_wire.py`, `tests/core/test_types/test_array_type_port_config.py`, `tests/core/test_graph/test_edges.py`, `tests/core/test_edge/test_unlink_reveals_own_value.py`, `tests/ui/skin/test_pin_icon_resolver.py`, `tests/ui/skin/test_pin_icon_resolution.py`, `tests/farmhand/test_graph_editor_tools.py`.

**Interfaces:**
- Consumes: 5.1's `DataPort.has_role(role)`, `is_outlet()`, `is_inlet()`, `WireRole`.
- Produces:
  - `DataField.keeps_value_per_source() -> bool`, `False` by default and `True` on `PooledField`.
  - `DataPort.single_link: bool = False`, a serialized dataclass field, saved only when `True`.
  - `DataPort.takes_many_links -> bool`, a read-only property computed on each read.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_types/test_link_ceiling.py`:

```python
"""The link ceiling: how many edges a port may hold, set by the mechanism and narrowed by the port."""

import pytest

from haywire.barn.builtin.types import ADD, CALLBACK, EXEC, FLOAT, INT, OPTIONAL
from haywire.core.types import DataPort, PortType

from tests.conftest import make_edge, make_node

OUTLET, INLET = PortType.OUTLET, PortType.INLET


def _port(type_cls, port_type, **kwargs) -> DataPort:
    return DataPort(
        registry_id="p",
        registry_key=type_cls.class_identity.registry_key,
        label="P",
        id="p",
        type_cls=type_cls,
        port_type=port_type,
        **kwargs,
    )


def _array(element):
    from haybale_core.types import ArrayType

    return ArrayType[element]


def _pooled(element):
    from haybale_core.types import PooledType

    return PooledType[element]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("type_cls", "port_type", "many"),
    [
        (FLOAT, OUTLET, True),
        (FLOAT, INLET, False),
        (EXEC, OUTLET, False),
        (EXEC, INLET, True),
        (CALLBACK, OUTLET, True),
        (CALLBACK, INLET, False),
        (ADD, OUTLET, True),
        (ADD, INLET, False),
        (ADD[EXEC], INLET, True),
        (OPTIONAL[INT], OUTLET, True),
        (OPTIONAL[INT], INLET, False),
    ],
)
def test_the_ceiling_follows_the_mechanism(type_cls, port_type, many):
    assert _port(type_cls, port_type).takes_many_links is many


@pytest.mark.unit
def test_a_container_takes_its_elements_ceiling():
    assert _port(_array(FLOAT), OUTLET).takes_many_links is True
    assert _port(_array(FLOAT), INLET).takes_many_links is False


@pytest.mark.unit
@pytest.mark.parametrize("element", [FLOAT, CALLBACK])
def test_a_pooled_inlet_takes_many(element):
    assert _port(_pooled(element), INLET).takes_many_links is True


@pytest.mark.unit
@pytest.mark.parametrize(("type_cls", "port_type"), [(FLOAT, OUTLET), (EXEC, INLET), (CALLBACK, OUTLET)])
def test_single_link_narrows_a_many_ceiling_to_one(type_cls, port_type):
    assert _port(type_cls, port_type, single_link=True).takes_many_links is False


@pytest.mark.unit
def test_single_link_is_saved_only_when_set():
    assert "single_link" not in _port(FLOAT, OUTLET).to_dict()["kwargs"]
    assert _port(FLOAT, OUTLET, single_link=True).to_dict()["kwargs"]["single_link"] is True


@pytest.mark.integration
def test_a_saved_allow_multiple_links_is_ignored_on_load(graph_with_library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    node = make_node(graph, TestAddFloatNode.class_identity.registry_key)
    data = graph.to_dict()
    for spec in data["nodes"][node.node_id]["node_data"]["ports"].values():
        spec["kwargs"]["allow_multiple_links"] = True

    graph.clear()
    graph.load_from_dict(data)

    assert graph.node_wrappers[node.node_id].node.ports["value_a"].takes_many_links is False


@pytest.mark.integration
def test_a_narrowed_outlet_keeps_one_linked_edge(graph_with_library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    key = TestAddFloatNode.class_identity.registry_key
    source, first, second = (make_node(graph, key) for _ in range(3))
    source.node.ports["result"].single_link = True

    make_edge(graph, source.node_id, "result", first.node_id, "value_a")
    make_edge(graph, source.node_id, "result", second.node_id, "value_a")
    graph.force_validation()

    assert len(source.node.ports["result"]._linked_edges) == 1
```

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/core/test_types/test_link_ceiling.py -q`
Expected: FAIL. `DataPort` has no `takes_many_links` and rejects `single_link=`.

- [ ] **Step 3: `keeps_value_per_source`**

In `packages/haywire-core/src/haywire/core/types/fields.py`, add to `DataField`, after `accepts_absence`:

```python
    def keeps_value_per_source(self) -> bool:
        """Whether this field keeps one value per feeding edge rather than one value in total.

        True for a pooled field. Two edges writing into a field that keeps one value
        would race, so ``DataPort.takes_many_links`` lifts an inlet's link ceiling
        only for a field that answers True.
        """
        return False
```

In `barn/haybale-core/haybale_core/types/pooled_type.py`, add to `PooledField`:

```python
    def keeps_value_per_source(self) -> bool:
        """True: a pooled field keeps one value per source edge."""
        return True
```

- [ ] **Step 4: `DataPort`**

In `packages/haywire-core/src/haywire/core/types/port.py`:

1. **The field.** Replace `allow_multiple_links: bool = False` and its docstring with:

```python
    single_link: bool = False
    """Narrow this port to one link where its link ceiling allows many; see ``takes_many_links``."""
```

2. **`__post_init__`.** Delete the block from the comment `# Link limits by role. …` through the end of the `elif self.has_role(WireRole.SEQUENCE):` branch.

3. **The property.** Add it after `is_dependent`:

```python
    @property
    def takes_many_links(self) -> bool:
        """Whether this port may hold more than one linked edge at a time.

        The link ceiling allows many, except where a second edge would break the
        mechanism: a ``SEQUENCE`` outlet (the VM keeps one transition per outlet),
        and a value inlet whose field keeps one value in total (two edges writing
        into it would race). A ``SEQUENCE`` inlet is entered once per transition and
        a ``VISUAL`` inlet receives no value, so both take many. ``single_link``
        narrows any ceiling to one.
        """
        if self.single_link:
            return False
        if self.is_outlet():
            return not self.has_role(WireRole.SEQUENCE)
        if self.has_role(WireRole.SEQUENCE) or self.has_role(WireRole.VISUAL):
            return True
        return self._data.keeps_value_per_source()
```

4. **Readers.**
   - In `_add_link`: `if not self.allow_multiple_links:` → `if not self.takes_many_links:`.
   - In `_try_reenable`: `if self.allow_multiple_links:` → `if self.takes_many_links:`.
   - Update both docstrings' "single-connection" wording to "a port that takes one link".

5. **`from_spec`.** Replace the two lines `# A key saved before wire types; …` / `kwargs.pop("flow_type", None)` with:

```python
        # Keys saved before wire types and link ceilings; a port derives both.
        kwargs.pop("flow_type", None)
        kwargs.pop("allow_multiple_links", None)
```

- [ ] **Step 5: Containers stop writing a link count**

- **`pooled_type.py`:**
  - Module docstring: item 3 reads `3. _configure_port: takes the element's colour`.
  - Class docstring: replace "It sets the pin to allow multiple connections automatically." with "Its field keeps one value per source, so the inlet takes many edges (see `DataPort.takes_many_links`)."
  - In the class's "Hooks" list: `_configure_port: takes the element's colour and refuses a control element`.
  - In `_configure_port`, delete `port.allow_multiple_links = True`. Its docstring becomes `"""Take the element's colour; refuse a control element."""`.
- **`array_type.py`:**
  - In `_configure_port`, delete the two lines `if port.is_outlet():` / `port.allow_multiple_links = wire.role is WireRole.DEPENDENT`.
  - Its docstring becomes `"""Take the colour of the element that declares the wire type, and refuse a control or callback element."""`.

- [ ] **Step 6: Readers outside the port**

- **`pin_icons.py`:** replace each of the three `pin.allow_multiple_links` with `pin.takes_many_links`.
- **`editor_tools.py`:**
  - In `_port_row`'s detail dict, replace `"allow_multiple_links": port.allow_multiple_links,` with `"takes_many_links": port.takes_many_links,`. After the `row.update({...})`, add:

```python
        if port.single_link:
            row["single_link"] = True
```

  - In the `data == "all"` branch, replace `row["allow_multiple_links"] = port.allow_multiple_links` with:

```python
        row["takes_many_links"] = port.takes_many_links
        if port.single_link:
            row["single_link"] = True
```

  - In the `query_graph` instructions, replace `data_type, allow_multiple_links, is_linked` with `data_type, takes_many_links, single_link when set, is_linked`.
- **`interface.py`:**
  - In `as_inlet`'s docstring, replace the `allow_multiple_links (bool): …` entry with `single_link (bool): Narrow the inlet to one edge where its link ceiling allows many (default: False)`.
  - In `as_outlet`'s docstring: `single_link (bool): Narrow the outlet to one edge where its link ceiling allows many (default: False)`.
  - In `_configure_port`'s docstring example, replace `port.allow_multiple_links = True` with `port.color = "#9c27b0"`. Add the sentence: "A link count is not one of them: ``DataPort.takes_many_links`` derives it."
- **`graph_actions.py`:** near line 759, replace "``allow_multiple_links=True``" with "an inlet that takes many links".
- **The four listener nodes:** delete `allow_multiple_links=True` from each `as_outlet(...)` call. Keep everything else on the line.

Then run: `grep -rn "allow_multiple_links" --include='*.py' packages barn`
Expected: only `port.py`'s `kwargs.pop("allow_multiple_links", None)`.

- [ ] **Step 7: Update the existing tests**

- **`tests/core/test_types/test_data_inlet_arity.py`.**
  - First test: rename it to `test_a_data_inlet_takes_one_link`, delete the `allow_multiple_links=True,` argument, and assert `port.takes_many_links is False`.
  - Second test: `takes_many_links is True`.
  - Module docstring: "A data inlet takes one edge; only a pooled inlet takes several."
- **`test_port_derives_from_wire.py::test_link_limits_follow_the_role`.**
  - Replace every `.allow_multiple_links` with `.takes_many_links`. The expected values stay as they are.
  - Add one assertion for the decided change, a callback outlet that declares nothing:

```python
    from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode

    listener = make_node(graph, TestCustomCallbackNode.class_identity.registry_key).node
    assert listener.ports["listen_callback"].takes_many_links is True
```

- **`test_array_type_port_config.py`.**
  - `.allow_multiple_links` → `.takes_many_links`.
  - Class docstring: "An ArrayType outlet over a data element takes many links, exactly like a scalar data outlet; see `DataPort.takes_many_links`."
  - The pooled-array docstring and comment: "a pooled field keeps one value per source, so the inlet takes many".
- **`tests/core/test_graph/test_edges.py`.**
  - `.allow_multiple_links` → `.takes_many_links` at the four sites.
  - The pooled test's docstring: "All pooled inlets take many links."
- **`tests/core/test_edge/test_unlink_reveals_own_value.py`.** Delete `port.allow_multiple_links = True`. The reveal path reads `_linked_edges`, not the ceiling.
- **`tests/ui/skin/test_pin_icon_resolver.py` and `test_pin_icon_resolution.py`.**
  - In each `_port` helper, replace the comment and the `multi` lines with:

```python
    # A many-link inlet is one whose field keeps a value per source, as a pooled field does.
    pooled = kwargs.pop("pooled", False)
    spec.update(type_cls=type_cls, **kwargs)
    port = DataPort(port_type=port_type, **spec)
    if pooled:
        port._data.keeps_value_per_source = lambda: True  # type: ignore[method-assign]
    return port
```

  - Call sites:
    - `allow_multiple_links=True` → `pooled=True`.
    - `port.allow_multiple_links = False` on the outlet in `test_icon_out_multi_is_ignored_on_a_single_link_outlet` → build the port with `single_link=True`.
    - `assert port.allow_multiple_links is True` → `assert port.takes_many_links is True`.
- **`tests/farmhand/test_graph_editor_tools.py`.** In `detail_keys`, `"allow_multiple_links"` → `"takes_many_links"`.

Then run: `grep -rn "allow_multiple_links" tests`
Expected: only `test_link_ceiling.py`'s legacy-key test.

- [ ] **Step 8: Run, then the gate**

Run: `uv run pytest tests/core/test_types tests/core/test_graph/test_edges.py tests/core/test_edge tests/ui/skin tests/farmhand/test_graph_editor_tools.py -q -n 4`
Expected: PASS.

Commit the haybale-testing edits first (Step 9), then run the ruff check and mypy on the changed files, the pre-commit gate, the browser tier (pin glyphs) and the visiongraph tests. Expected: green.

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/fields.py packages/haywire-core/src/haywire/core/types/port.py packages/haywire-core/src/haywire/core/types/interface.py packages/haywire-core/src/haywire/ui/skin/pin_icons.py packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py barn/haybale-core/haybale_core/types/pooled_type.py barn/haybale-core/haybale_core/types/array_type.py barn/haybale-core/haybale_core/nodes/events/tick_event.py barn/haybale-example/haybale_example/nodes/emits/custom_callback.py barn/haybale-testing/haybale_testing/nodes/testbed/custom_callback_node.py barn/haybale-testing/haybale_testing/nodes/testbed/record_callback_nodes.py barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py tests/core/test_types/test_link_ceiling.py tests/core/test_types/test_data_inlet_arity.py tests/core/test_types/test_port_derives_from_wire.py tests/core/test_types/test_array_type_port_config.py tests/core/test_graph/test_edges.py tests/core/test_edge/test_unlink_reveals_own_value.py tests/ui/skin/test_pin_icon_resolver.py tests/ui/skin/test_pin_icon_resolution.py tests/farmhand/test_graph_editor_tools.py
git commit -m "feat(ports): a link ceiling set by mechanism, narrowed by single_link

A port's link count is DataPort.takes_many_links, read from its role and its
field: a control outlet and a value inlet whose field keeps one value take
one, everything else many. single_link narrows any port to one.
allow_multiple_links is gone and a saved key is ignored; containers no
longer write a link count. A callback outlet that declared nothing now
fans out.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: A widget refuses edits on a field without an own value

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/types/fields.py` (`DataField`)
  - `barn/haybale-core/haybale_core/types/pooled_type.py` (`PooledField`)
  - `packages/haywire-core/src/haywire/barn/builtin/types/add.py` (`ADDField`)
  - `packages/haywire-core/src/haywire/ui/widget/base.py`, `packages/haywire-core/src/haywire/ui/widget/binding.py`
- Test: create `tests/ui/widget/test_widget_without_own_value.py`

**Interfaces:**
- Consumes: Task 1's `keeps_value_per_source` placement in `DataField`.
- Produces: `DataField.accepts_own_value() -> bool`, `True` by default and `False` on `PooledField` and `ADDField`.

- [ ] **Step 1: Write the failing tests**

Create `tests/ui/widget/test_widget_without_own_value.py`:

```python
"""A widget on a field that holds no own value refuses edits instead of raising."""

import pytest

from haywire.barn.builtin.types import ADD, FLOAT
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort

from tests.ui.widget._sync_fixtures import _BaseDefaultFloatWidget

pytestmark = pytest.mark.unit


def _port(type_cls) -> DataPort:
    return DataPort(
        registry_id="p",
        registry_key=type_cls.class_identity.registry_key,
        label="P",
        id="p",
        type_cls=type_cls,
        port_type=PortType.INLET,
    )


def _pooled_port() -> DataPort:
    from haybale_core.types import PooledType

    port = _port(PooledType[FLOAT])
    port.data.set_value(1.5, source_id="e1")
    return port


def test_a_pooled_field_and_an_add_slot_hold_no_own_value():
    assert not _pooled_port().data.accepts_own_value()
    assert not _port(ADD).data.accepts_own_value()
    assert _port(FLOAT).data.accepts_own_value()


def test_a_direct_widget_write_on_a_pooled_port_is_refused():
    port = _pooled_port()
    widget = _BaseDefaultFloatWidget(port)
    widget.render()

    widget.set_value(9.0)

    assert port.get_value() == {"e1": 1.5}


def test_a_view_edit_on_a_pooled_port_is_refused():
    port = _pooled_port()
    widget = _BaseDefaultFloatWidget(port)
    widget.render()

    widget._bindings[0]._sync_to_model(9.0)

    assert port.get_value() == {"e1": 1.5}
```

If `render()` fails because the float stand-in widget cannot show a dict, give the test a widget whose binding uses an identity converter: subclass `BaseWidget` the way `_BaseDefaultFloatWidget` does and pass the converter `_sync_fixtures` uses for the explicit-converter shape. Keep the three assertions unchanged.

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/ui/widget/test_widget_without_own_value.py -q`
Expected:
- FAIL: `accepts_own_value` does not exist.
- The two write tests raise `ValueError: PooledField requires source_id`. That is the crash this task removes.

- [ ] **Step 3: The predicate**

In `fields.py`, add to `DataField`, after `keeps_value_per_source`:

```python
    def accepts_own_value(self) -> bool:
        """Whether a write without a source can store an own value in this field.

        False for a field whose value comes only from its edges (a pooled field)
        and for one that holds nothing (an ``ADD`` slot).
        """
        return True
```

Add `def accepts_own_value(self) -> bool: return False`, with a one-line docstring, to `PooledField` ("A pooled field holds only its sources' values.") and to `ADDField` ("An ``ADD`` slot holds nothing.").

- [ ] **Step 4: The guards**

In `packages/haywire-core/src/haywire/ui/widget/base.py`, `BaseWidget.set_value`:

```python
    def set_value(self, value: Any) -> None:
        """Write *value* to the model, unless the model cannot take it as its own value.

        The write is refused, and the view shows the model's value again, while an
        edge's value stands in front of the own value or the field holds no own
        value (see ``DataField.accepts_own_value``).
        """
        data = self.port.data
        if data.has_linked_value() or not data.accepts_own_value():
            self.on_model_changed(self.port.get_value())
            return
        self.port.set_value(value)
```

In `packages/haywire-core/src/haywire/ui/widget/binding.py`, `_sync_to_model`, make the guard `if self._element.data.has_linked_value() or not self._element.data.accepts_own_value():`. The comment becomes `# An edge's value stands in front of the own value, or there is no own value to write; show the model again.`

- [ ] **Step 5: Run, then the gate**

Run: `uv run pytest tests/ui/widget -q -n 4`. Expected: PASS.

Run the ruff check and mypy on the changed files, then the pre-commit gate. Expected: green.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/fields.py barn/haybale-core/haybale_core/types/pooled_type.py packages/haywire-core/src/haywire/barn/builtin/types/add.py packages/haywire-core/src/haywire/ui/widget/base.py packages/haywire-core/src/haywire/ui/widget/binding.py tests/ui/widget/test_widget_without_own_value.py
git commit -m "fix(widgets): refuse an edit on a field that holds no own value

A widget on a pooled port raised on its first edit. DataField gains
accepts_own_value() (False for pooled fields and ADD slots), and the widget
guard that refuses an edit on a linked inlet now refuses this too, showing
the model's value again.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `@type` rules: a wire type is required, a widget is the author's call, `OPTIONAL[T]` takes `T`'s

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/types/decorator.py`
  - `packages/haywire-core/src/haywire/core/types/identity.py` (docs)
  - `packages/haywire-core/src/haywire/barn/builtin/types/optional.py`
- Test:
  - create `tests/core/test_types/test_type_rules.py`;
  - modify `tests/barn/builtin/test_type_default_widget.py`, `tests/core/types/test_primitive_type_default.py`.

**Interfaces:**
- Consumes: 5.1's `DataTypeIdentity.wire_type`, `wire_type_of`.
- Produces:
  - `@type` raises `TypeError` ("needs a wire type") for a type that is neither a `CompoundType`, a `WrapperType` nor `_is_any` and has no wire type, declared or inherited.
  - `OPTIONAL` declares no wire type.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_types/test_type_rules.py`:

```python
"""What @type refuses, by the mechanism that breaks: a type needs a wire type; a widget is the author's call."""

import pytest

from haywire.core.types.base import PrimitiveType
from haywire.core.types.decorator import type as type_dec

pytestmark = pytest.mark.unit


def test_a_value_type_without_a_wire_type_is_refused():
    with pytest.raises(TypeError, match="needs a wire type"):

        @type_dec(label="NoWire", default={"value": ""})
        class NoWire(PrimitiveType[str]):
            pass


@pytest.mark.parametrize("wire_name", ["ControlWire", "CallbackWire"])
def test_a_signal_type_may_declare_a_widget(wire_name):
    from haywire.barn.builtin import wires

    @type_dec(
        wire_type=getattr(wires, wire_name),
        label="WidgetSignal",
        default={"value": ""},
        widget_key="haywire-core:widget:TextWidget",
    )
    class WidgetSignal(PrimitiveType[str]):
        pass

    assert WidgetSignal.class_identity.widget_key == "haywire-core:widget:TextWidget"


def test_a_signal_type_may_inherit_a_widget():
    from haywire.barn.builtin.types import STRING
    from haywire.barn.builtin.wires import CallbackWire

    @type_dec(wire_type=CallbackWire, label="InheritsWidget")
    class InheritsWidget(STRING):
        pass

    assert InheritsWidget.class_identity.widget_key == STRING.class_identity.widget_key


@pytest.mark.parametrize(
    ("element", "wire_name"),
    [("INT", "DataWire"), ("EXEC", "ControlWire"), ("CALLBACK", "CallbackWire")],
)
def test_optional_travels_on_its_elements_wire_type(element, wire_name):
    from haywire.barn.builtin import types, wires
    from haywire.core.types.wire import wire_type_of

    wire = wire_type_of(types.OPTIONAL[getattr(types, element)])

    assert wire is not None
    assert wire.id == getattr(wires, wire_name).id
```

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/core/test_types/test_type_rules.py -q`
Expected:
- `test_a_value_type_without_a_wire_type_is_refused` FAILS (no error is raised);
- both widget tests FAIL with "cannot have a widget_key";
- `OPTIONAL[EXEC]` and `OPTIONAL[CALLBACK]` FAIL, answering `DataWire`.

`OPTIONAL[INT]` passes already.

- [ ] **Step 3: `decorator.py`**

1. Delete the widget rule: the comment `# A control or callback type is a signal, …` and the `wire = …` / `if (…)` / `raise TypeError(…)` block under it.
2. After the primitive-default check (the `if issubclass(inner_cls, PrimitiveType) and …` block), add:

```python
        # A pin with no wire type matches no other pin, so its edges could never link.
        # A container or wrapper takes its element's; a bare ADD is the wildcard.
        if identity_dict.get("wire_type") is None and not (
            issubclass(inner_cls, (CompoundType, WrapperType)) or getattr(inner_cls, "_is_any", False)
        ):
            raise TypeError(
                f"@type decorator for {inner_cls.__name__}: a value type needs a wire type. Pass "
                f"wire_type=DataWire (or the wire type its values travel on, from "
                f"haywire.barn.builtin.wires or your library), or derive from a type that has one."
            )
```

3. Delete `from .wire import WireRole` if nothing else in the file uses it.
4. In the docstring:
   - the `wire_type` entry: `wire_type (type[WireType]): The wire type values travel on; inherited by derived types. Required unless the type is a container, a wrapper or ADD.`;
   - add under `Raises:`: `TypeError: If the type has no wire type and is not a container, a wrapper or ADD`.

- [ ] **Step 4: `OPTIONAL` and the identity docs**

- **`optional.py`:**
  - Delete `wire_type=DataWire,` and the import `from ..wires import DataWire`.
  - In the class docstring, after the "**Promotion is ordinary.**" paragraph, add the paragraph: `**Wire type.** \`OPTIONAL[T]\` travels on \`T\`'s wire type, so \`OPTIONAL[EXEC]\` is a control pin and \`OPTIONAL[CALLBACK]\` a callback pin.`
- **`identity.py`:** in both docs of `wire_type` (the class `Attributes:` entry and the field docstring), say: "``None`` for a container or wrapper, which take their element's, and for a bare ``ADD``, the wildcard; ``@type`` refuses ``None`` for any other type. See ``wire_type_of``."

- [ ] **Step 5: Update the existing tests**

- **`tests/barn/builtin/test_type_default_widget.py`:**
  - Delete `test_control_and_callback_wire_types_reject_widget_key` and `test_inherited_widget_key_on_signal_type_is_rejected`; `test_type_rules.py` replaces them.
  - In `test_callback_type_has_no_widget_key`, the docstring becomes: "CALLBACK declares no widget of its own; it would otherwise inherit STRING's TextWidget."
  - Drop imports the file no longer uses.
- **`tests/core/types/test_primitive_type_default.py`:** add `wire_type=DataWire` to the `NoValue`, `NoneValue` and `HasValue` decorators, and `from haywire.barn.builtin.wires import DataWire` to the imports. `Derived(STRING)` inherits one.

Then run: `grep -rn "OPTIONAL" tests --include='*.py' | grep -i "wire"`. Any assertion that `OPTIONAL` itself answers `DataWire` changes with this task: name it in the report and make it read the element's wire type.

- [ ] **Step 6: Run, then the gate**

Run: `uv run pytest tests/core/test_types tests/core/types tests/barn/builtin tests/ui/widget/test_optional_widget.py -q -n 4`. Expected: PASS.

Run the ruff check and mypy on the changed files, the pre-commit gate and the visiongraph tests. Expected: green. Every library type declares or inherits a wire type, so nothing in tree trips the new refusal. A library that does surfaces as an import error naming the fix.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/decorator.py packages/haywire-core/src/haywire/core/types/identity.py packages/haywire-core/src/haywire/barn/builtin/types/optional.py tests/core/test_types/test_type_rules.py tests/barn/builtin/test_type_default_widget.py tests/core/types/test_primitive_type_default.py
git commit -m "feat(types): a value type needs a wire type; a widget is the author's call

@type refuses a type with no wire type unless it is a container, a wrapper
or ADD: its pins could never link. The rule refusing a widget on control
and callback types goes. OPTIONAL declares no wire type, so OPTIONAL[T]
travels on T's.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Two bare `ADD` slots do not link

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/types/wire.py` (`wires_match`)
  - `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` (`_wiresMatch`)
  - `packages/haywire-core/src/haywire/barn/builtin/types/add.py` (docstring)
  - `packages/haywire-core/src/haywire/barn/builtin/nodes/subgraph_io.py` (`hb_grow`)
  - `barn/haybale-testing/haybale_testing/nodes/testbed/add_port_test.py` (`hb_resolve`)
  - `packages/haywire-core/src/haywire/core/adapter/factory.py` (comment)
- Test: modify `tests/core/test_types/test_wire.py`, `tests/core/test_types/test_add_type.py`

**Interfaces:**
- Produces: `wires_match("*", "*") is False`, with the JS mirror the same.

- [ ] **Step 1: The failing tests**

- **`tests/core/test_types/test_wire.py`:** in `test_wires_match`'s table, `(WILDCARD, WILDCARD, True)` becomes `(WILDCARD, WILDCARD, False)`.
- **`tests/core/test_types/test_add_type.py`:** replace `test_any_to_any_leaves_both_ends_undecided` with:

```python
    def test_two_bare_slots_do_not_link(self, graph_with_library_system: BaseGraph, library_system):
        """Neither end has a wire type for the edge to take, so the edge fails formal validation."""
        graph = graph_with_library_system
        source = _make_add_node(graph, (100, 100))
        target = _make_add_node(graph, (300, 100))

        edge = graph.create_edge_wrapper(source.node_id, "add_out_0", target.node_id, "add_in_0")
        assert edge is not None
        graph._validation.force_immediate_validation()

        assert not edge.state.is_formally_validated
        error = edge.state.get_error()
        assert error is not None and "Wire type mismatch" in error.message  # noqa: PT018
        assert target.node.ports["add_in_0"].type_cls is ADD
        assert source.node.ports["add_out_0"].type_cls is ADD
```

  In `test_any_to_any_passes_through` (the adapter-factory test), the docstring becomes: "The factory answers a pass-through; `wires_match` refuses the edge before a chain is asked for."

Run: `uv run pytest tests/core/test_types/test_wire.py tests/core/test_types/test_add_type.py -q`
Expected: the two changed tests FAIL.

- [ ] **Step 2: `wires_match` and its mirror**

In `wire.py`:

```python
def wires_match(a: str | None, b: str | None) -> bool:
    """Return whether two pins with wire keys *a* and *b* may be linked.

    True for equal wire type ids, and when exactly one key is ``WILDCARD`` (a bare
    ``ADD`` slot). Two wildcards do not match: the edge would have no wire type
    to take. A key of ``None`` (a port without a wire type) matches nothing.
    """
    if a is None or b is None:
        return False
    if a == WILDCARD and b == WILDCARD:
        return False
    return a == b or a == WILDCARD or b == WILDCARD
```

In `canvas.vue`:

```js
        /** Mirror of wires_match (core/types/wire.py): equal wire keys, or exactly one '*' wildcard. */
        _wiresMatch(a, b) {
            if (!a || !b) return false;
            if (a === '*' && b === '*') return false;
            return a === b || a === '*' || b === '*';
        },
```

- [ ] **Step 3: The guards that are now dead, and the prose**

- **`subgraph_io.py`, `hb_grow`:** delete the lines `if incoming._is_any:` / `# Both ends undecided: nothing to adopt.` / `return`.
- **`add_port_test.py`, `hb_resolve`:** delete the lines `if incoming._is_any:` / `# Both ends undecided: nothing to adopt, and no new slot.` / `return`.
- **`add.py`, the `ADD` docstring:**
  - In the `_resolve` example, delete the two lines `if incoming._is_any:` / `return  # the other end is undecided too — nothing to adopt`.
  - Replace the paragraph "An edge between two bare `ADD` pins is valid and does nothing: neither end has a type to give. Both resolve once either connects to something concrete." with "Two bare `ADD` pins do not connect: neither end has a wire type for the edge to take."
- **`factory.py`:** the comment's last sentence becomes "ADD -> ADD never reaches here: `wires_match` refuses it."

- [ ] **Step 4: Run, then the gate**

Run: `uv run pytest tests/core/test_types tests/core/test_graph -q -n 4`. Expected: PASS.

Commit (haybale-testing is touched), then run the ruff check and mypy on the changed Python files, the pre-commit gate and the browser tier. Expected: green.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/wire.py packages/haywire-core/src/haywire/ui/components/graph/canvas.vue packages/haywire-core/src/haywire/barn/builtin/types/add.py packages/haywire-core/src/haywire/barn/builtin/nodes/subgraph_io.py barn/haybale-testing/haybale_testing/nodes/testbed/add_port_test.py packages/haywire-core/src/haywire/core/adapter/factory.py tests/core/test_types/test_wire.py tests/core/test_types/test_add_type.py
git commit -m "feat(wires): two bare ADD slots do not link

An edge between two bare ADD slots had no wire type to take and did
nothing. wires_match and the canvas refuse it; a saved one loads as an
invalid edge. The guards for it in hb_grow and the ADD test node go.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: The empty-array fix, then containers of control and callback elements (verify first)

**Files:**
- Modify:
  - `packages/haywire-core/src/haywire/core/types/port.py` (`get_value`, `set_value`)
  - `barn/haybale-core/haybale_core/types/array_type.py`, `barn/haybale-core/haybale_core/types/pooled_type.py`
- Create:
  - `barn/haybale-testing/haybale_testing/nodes/testbed/container_signal_probes.py`
- Test:
  - create `tests/core/test_types/test_empty_array_port.py`, `tests/core/test_types/test_container_signal_elements.py`

**Interfaces:**
- Consumes: Task 1's `takes_many_links` (a pooled control inlet takes many through its field, with no container write).
- Produces: the three probe nodes, whose knobs are set by tests:
  - `ArrayExecProbeNode`: `emit` (a list or `None`), `received`;
  - `ArrayCallbackProbeNode`: `heard` (a list of lists);
  - `PooledExecProbeNode`: `received` (a list of pools).

**The rule of this task (Q39).** Each of the three refusals goes only if its test passes. If a test fails for a reason inside the combination (the VM, a pipe, an adapter), do this:
1. Restore that refusal, reworded to name the mechanism that broke.
2. Turn its test into a test of the refusal.
3. Report the failure and stop: status `DONE_WITH_CONCERNS`, naming the combination and the failure.

- [ ] **Step 1: The falsy-array fix, test first**

Create `tests/core/test_types/test_empty_array_port.py`:

```python
"""An array port holding [] is a port with a value, not a port without data."""

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, PortType

pytestmark = pytest.mark.unit


def _array_port(port_type: PortType) -> DataPort:
    from haybale_core.types import ArrayType

    array = ArrayType[FLOAT]
    return DataPort(
        registry_id="a",
        registry_key=array.class_identity.registry_key,
        label="A",
        id="a",
        type_cls=array,
        port_type=port_type,
    )


def test_an_empty_array_reads_as_an_empty_list():
    assert _array_port(PortType.INLET).get_value() == []


def test_the_first_write_to_an_empty_array_is_kept():
    port = _array_port(PortType.OUTLET)

    port.set_value([1.0, 2.0])

    assert port.get_value() == [1.0, 2.0]
```

Run: `uv run pytest tests/core/test_types/test_empty_array_port.py -q`. Expected: both FAIL. An empty `ArrayField` is falsy, so `get_value` returns `None` and `set_value` returns early.

In `port.py`, `get_value` and `set_value` each open with `if not self._data:`. Make both `if self._data is None:`. Run again. Expected: PASS.

Run the ruff check, mypy and the pre-commit gate. A test whose expectation encodes the dropped write or the `None` read is a test of the bug: name it in the report and update it.

```bash
git add packages/haywire-core/src/haywire/core/types/port.py tests/core/test_types/test_empty_array_port.py
git commit -m "fix(ports): an empty array port is not a port without data

DataPort.get_value/set_value guarded with 'if not self._data', and an
empty ArrayField (or map) is falsy, so an empty array port read None and
dropped its first write. Guard on 'is None'.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 2: The probe nodes**

Create `barn/haybale-testing/haybale_testing/nodes/testbed/container_signal_probes.py`:

```python
"""Test-only nodes carrying containers of control and callback elements."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node


@node(
    label="Array Exec Probe",
    description="Test-only: an array-of-EXEC outlet and inlet on a control node.",
    menu="testing/testbed",
    search_tags=["test", "array", "exec", "container"],
    node_type=NodeType.CONTROL,
)
class ArrayExecProbeNode(BaseNode):
    """Control node with an `ArrayType[EXEC]` outlet and inlet.

    Set `emit` to a list and the worker writes it to `exec_list_out` and fires
    that outlet. The worker stores what arrived on `exec_list_in` in `received`.
    """

    emit = None
    received = None

    def init(self):
        from haybale_core.types import ArrayType

        from haywire.barn.builtin.types import EXEC

        self.add(EXEC.as_inlet("exec_in"))
        self.add(ArrayType[EXEC].as_inlet("exec_list_in"))
        self.add(ArrayType[EXEC].as_outlet("exec_list_out"))

    def worker(self, context: ExecutionContext) -> str | None:
        self.received = self.value("exec_list_in")
        if self.emit is None:
            return None
        self.out("exec_list_out", self.emit)
        return "exec_list_out"


@node(
    label="Array Callback Probe",
    description="Test-only: an array-of-CALLBACK outlet and inlet.",
    menu="testing/testbed",
    search_tags=["test", "array", "callback", "container"],
    node_type=NodeType.CONTROL,
)
class ArrayCallbackProbeNode(BaseNode):
    """Node with an `ArrayType[CALLBACK]` outlet and inlet; `heard` records each list the inlet receives."""

    def init(self):
        from haybale_core.types import ArrayType

        from haywire.barn.builtin.types import CALLBACK

        self.add(ArrayType[CALLBACK].as_outlet("names_out"))
        self.add(ArrayType[CALLBACK].as_inlet("names_in", on_change="_on_names"))

    def post_init(self):
        self.heard = []

    def _on_names(self, value) -> None:
        self.heard.append(value)

    def worker(self, context: ExecutionContext) -> str | None:
        return None


@node(
    label="Pooled Exec Probe",
    description="Test-only: a pooled EXEC inlet on a control node.",
    menu="testing/testbed",
    search_tags=["test", "pooled", "exec", "container"],
    node_type=NodeType.CONTROL,
)
class PooledExecProbeNode(BaseNode):
    """Control node with a `PooledType[EXEC]` inlet; `received` records the pool each run sees."""

    def init(self):
        from haybale_core.types import PooledType

        from haywire.barn.builtin.types import EXEC

        self.add(PooledType[EXEC].as_inlet("pooled_exec_in"))

    def post_init(self):
        self.received = []

    def worker(self, context: ExecutionContext) -> str | None:
        self.received.append(self.value("pooled_exec_in"))
        return None
```

Check the `on_change` handler's signature against an existing one (`TestEmitCallbackNode`'s `printout`), and match it.

- [ ] **Step 3: The end-to-end tests**

Create `tests/core/test_types/test_container_signal_elements.py`:

```python
"""Containers of control and callback elements run end to end (decision Q39)."""

import pytest

from haywire.core.execution.event_source import SystemEventType
from haywire.core.execution.interpreter import Interpreter
from haywire.core.types import WireRole

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


def _run(graph) -> None:
    interpreter = Interpreter()
    interpreter.load_graph(graph)
    try:
        interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        interpreter.wait_all(timeout=5.0)
    finally:
        interpreter.shutdown()


def test_an_array_of_exec_fires_its_transition_with_the_list(graph_with_library_system):
    from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
    from haybale_testing.nodes.testbed.container_signal_probes import ArrayExecProbeNode

    graph = graph_with_library_system
    begin = make_node(graph, TestBeginPlayNode.class_identity.registry_key, position=(0, 0))
    source = make_node(graph, ArrayExecProbeNode.class_identity.registry_key, position=(200, 0))
    sink = make_node(graph, ArrayExecProbeNode.class_identity.registry_key, position=(400, 0))
    make_edge(graph, begin.node_id, "exec", source.node_id, "exec_in")
    edge = make_edge(graph, source.node_id, "exec_list_out", sink.node_id, "exec_list_in")
    source.node.emit = [{"n": 1}, {"n": 2}]
    graph.force_validation()

    assert edge.state.is_valid()
    assert edge.wire_type is not None and edge.wire_type.role is WireRole.SEQUENCE  # noqa: PT018

    _run(graph)

    assert sink.node.received == [{"n": 1}, {"n": 2}]


def test_an_array_of_callbacks_reaches_its_inlet_on_write(graph_with_library_system):
    from haybale_testing.nodes.testbed.container_signal_probes import ArrayCallbackProbeNode

    graph = graph_with_library_system
    key = ArrayCallbackProbeNode.class_identity.registry_key
    source = make_node(graph, key, position=(0, 0))
    sink = make_node(graph, key, position=(300, 0))
    edge = make_edge(graph, source.node_id, "names_out", sink.node_id, "names_in")
    graph.force_validation()

    assert edge.state.is_valid()

    source.node.ports["names_out"].set_value(["a", "b"])

    assert sink.node.heard[-1] == ["a", "b"]


def test_a_pool_of_exec_takes_many_edges_and_runs_with_the_pool(graph_with_library_system):
    from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
    from haybale_testing.nodes.testbed.container_signal_probes import PooledExecProbeNode
    from haybale_testing.nodes.testbed.control_payload_node import ControlPayloadTestNode

    graph = graph_with_library_system
    begin = make_node(graph, TestBeginPlayNode.class_identity.registry_key, position=(0, 0))
    first = make_node(graph, ControlPayloadTestNode.class_identity.registry_key, position=(200, 0))
    second = make_node(graph, ControlPayloadTestNode.class_identity.registry_key, position=(200, 200))
    sink = make_node(graph, PooledExecProbeNode.class_identity.registry_key, position=(400, 0))
    make_edge(graph, begin.node_id, "exec", first.node_id, "exec_in")
    from_first = make_edge(graph, first.node_id, "exec_out", sink.node_id, "pooled_exec_in")
    from_second = make_edge(graph, second.node_id, "exec_out", sink.node_id, "pooled_exec_in")
    first.node.emit_payload = {"from": "first"}
    graph.force_validation()

    inlet = sink.node.ports["pooled_exec_in"]
    assert from_first.state.is_valid() and from_second.state.is_valid()  # noqa: PT018
    assert len(inlet._linked_edges) == 2

    _run(graph)

    assert sink.node.received[-1] == {from_first.edge_id: {"from": "first"}}

    second.node.ports["exec_out"].set_value({"from": "second"})

    assert inlet.get_value() == {
        from_first.edge_id: {"from": "first"},
        from_second.edge_id: {"from": "second"},
    }
```

- [ ] **Step 4: Run them (red)**

Commit nothing yet. Run: `uv run pytest tests/core/test_types/test_container_signal_elements.py -q -p no:randomly`.
Expected: all three FAIL. Each probe's construction hits a container refusal ("ArrayType cannot have a control element type", "… callback element type", "PooledType cannot have a control element type").

- [ ] **Step 5: Drop the refusals**

`array_type.py`, `_configure_port`:

```python
    @classmethod
    def _configure_port(cls, port, **context) -> None:
        """Take the colour of the element that declares the wire type."""
        current_type = port.type_cls.element_type_cls
        while current_type is not None:
            identity = getattr(current_type, "class_identity", None)
            if identity is not None and getattr(identity, "wire_type", None) is not None:
                port.color = identity.color
                return
            current_type = getattr(current_type, "element_type_cls", None)
```

Its class docstring's hook line: `_configure_port: takes the element's colour`. Drop the `WireRole` import if unused.

`pooled_type.py`, `_configure_port`: the same loop, with docstring `"""Take the colour of the element that declares the wire type."""`. Its "Hooks" entry: `_configure_port: takes the element's colour`. Keep `_validate_port_type` (a pool has no own value, so it refuses an outlet).

- [ ] **Step 6: Run them (green), each on its own**

Run each of the three tests by node id. A pass frees its combination. For a failure, apply "The rule of this task" above, and stop and report after finishing the other two.

- [ ] **Step 7: The gate**

Commit the haybale-testing module first (Step 8, the first commit). Then run the ruff check and mypy on the changed files, the pre-commit gate and the visiongraph tests. Expected: green.

- [ ] **Step 8: Commit**

```bash
git add barn/haybale-testing/haybale_testing/nodes/testbed/container_signal_probes.py
git commit -m "test(testing): probe nodes carrying containers of control and callback elements

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git add barn/haybale-core/haybale_core/types/array_type.py barn/haybale-core/haybale_core/types/pooled_type.py tests/core/test_types/test_container_signal_elements.py
git commit -m "feat(types): arrays of control and callback elements, pools of control

Each refusal went once a test showed its combination running end to end:
an array of EXEC fires its transition with the list, an array of CALLBACK
reaches its inlet on write, and a pool of EXEC takes many edges and runs
with the pool. PooledType still refuses an outlet: a pool has no own value.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

If a refusal stayed, the second commit message names what went and what stayed, and why.

---

### Task 6: The `VISUAL` wire: drawn and saved, never executed

**Files:**
- Create:
  - `barn/haybale-testing/haybale_testing/wires.py`
  - `barn/haybale-testing/haybale_testing/nodes/testbed/visual_probe.py`
- Modify:
  - `barn/haybale-testing/haybale_testing/types/test_types.py`, `barn/haybale-testing/haybale_testing/types/__init__.py`
  - `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py`
  - `packages/haywire-core/src/haywire/core/types/port.py` (`_refresh_pipes`)
  - `packages/haywire-core/src/haywire/core/validation/structural_validator.py`
- Test: create `tests/core/test_edge/test_visual_wire.py`, `tests/core/test_validation/test_visual_pins.py` (create the directory with an `__init__.py` only if sibling test directories have one)

**Interfaces:**
- Consumes:
  - Task 1's ceiling (a `VISUAL` inlet takes many);
  - 5.1's `EdgeWrapper.wire_type` and `propagation` (`None` for a wire type with `propagation = ()`).
- Produces:
  - `haybale_testing.wires.TestVisualWire` (`role = WireRole.VISUAL`, `propagation = ()`, `pin_kind = "test_visual"`);
  - `TEST_VISUAL` (derives from `STRING`) and `TEST_VISUAL_COUNT` (derives from `INT`), both on it;
  - `VisualProbeNode`, a DATA node with ports `note_in`, `count_in`, `note_out` and `value` (float outlet);
  - `EdgeWrapper.carries_values -> bool`.

- [ ] **Step 1: The test-only wire, types and node**

Create `barn/haybale-testing/haybale_testing/wires.py`:

```python
"""Test-only wire types."""

from haywire.core.types import WireRole, WireType


class TestVisualWire(WireType):
    """A drawn-only wire for tests: saved and drawn, never executed."""

    role = WireRole.VISUAL
    propagation = ()
    pin_kind = "test_visual"
```

In `types/test_types.py`, add `from haybale_testing.wires import TestVisualWire` and `from haywire.barn.builtin.types import INT, STRING`. Import the wire by its module path; ADR 0042's authoring rule says the reload cascade needs that. Then append:

```python
@type(
    wire_type=TestVisualWire,
    label="Test Visual",
    description="Test-only: a text value on a drawn-only wire",
    color="#8e8e8e",
)
class TEST_VISUAL(STRING):
    """Test-only type on `TestVisualWire`, with `STRING`'s text widget."""


@type(
    wire_type=TestVisualWire,
    label="Test Visual Count",
    description="Test-only: a number on a drawn-only wire",
    color="#8e8e8e",
)
class TEST_VISUAL_COUNT(INT):
    """Test-only type on `TestVisualWire` whose payload differs from `TEST_VISUAL`'s."""
```

Export both from `types/__init__.py` (import and `__all__`).

Create `barn/haybale-testing/haybale_testing/nodes/testbed/visual_probe.py`:

```python
"""Test-only node with pins on a drawn-only wire."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node


@node(
    label="Visual Probe",
    description="Test-only: a data node with pins on a drawn-only wire.",
    menu="testing/testbed",
    search_tags=["test", "visual", "wire"],
    node_type=NodeType.DATA,
)
class VisualProbeNode(BaseNode):
    """Data node with `TEST_VISUAL` pins `note_in` and `note_out`, a `TEST_VISUAL_COUNT` inlet `count_in`,
    and a float outlet `value`."""

    def init(self):
        from haybale_testing.types import TEST_VISUAL, TEST_VISUAL_COUNT

        from haywire.barn.builtin.types import FLOAT

        self.add(TEST_VISUAL.as_inlet("note_in"))
        self.add(TEST_VISUAL_COUNT.as_inlet("count_in"))
        self.add(TEST_VISUAL.as_outlet("note_out"))
        self.add(FLOAT.as_outlet("value"))

    def worker(self, context: ExecutionContext) -> str | None:
        self.out("value", 1.0)
        return None
```

Commit these four haybale-testing files now. The suite's teardown reverts uncommitted ones.

```bash
git add barn/haybale-testing/haybale_testing/wires.py barn/haybale-testing/haybale_testing/types/test_types.py barn/haybale-testing/haybale_testing/types/__init__.py barn/haybale-testing/haybale_testing/nodes/testbed/visual_probe.py
git commit -m "test(testing): a drawn-only wire type, two types on it and a probe node

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 2: Write the failing tests**

Create `tests/core/test_edge/test_visual_wire.py`:

```python
"""A VISUAL edge is drawn and saved but never executed: no adapter chain, no pipe, no propagation."""

import pytest

from haywire.core.types import WireRole

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


def _probes(graph, count: int = 2):
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    key = VisualProbeNode.class_identity.registry_key
    return [make_node(graph, key, position=(300 * i, 0)) for i in range(count)]


def test_a_visual_edge_validates_without_an_adapter_chain(graph_with_library_system):
    graph = graph_with_library_system
    source, sink = _probes(graph)
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()

    assert edge.state.is_valid()
    assert edge.wire_type is not None and edge.wire_type.role is WireRole.VISUAL  # noqa: PT018
    assert edge.first_adapter is None
    assert edge.edge.chain_adapter_keys == []
    assert edge.propagation is None


def test_the_data_types_at_its_ends_need_not_match(graph_with_library_system):
    graph = graph_with_library_system
    source, sink = _probes(graph)
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "count_in")
    graph.force_validation()

    assert edge.state.is_valid()


def test_nothing_travels_and_the_inlet_keeps_its_own_value(graph_with_library_system):
    graph = graph_with_library_system
    source, sink = _probes(graph)
    make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()
    inlet = sink.node.ports["note_in"]

    source.node.ports["note_out"].set_value("hello")

    assert not inlet.data.has_linked_value()
    inlet.set_value("own")
    assert inlet.get_value() == "own"


def test_a_visual_inlet_takes_many_edges(graph_with_library_system):
    graph = graph_with_library_system
    first, second, sink = _probes(graph, 3)
    make_edge(graph, first.node_id, "note_out", sink.node_id, "note_in")
    make_edge(graph, second.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()

    assert len(sink.node.ports["note_in"]._linked_edges) == 2


def test_visual_pins_never_make_a_data_node_invalid(graph_with_library_system):
    graph = graph_with_library_system
    source, sink = _probes(graph)
    make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()

    assert source.is_valid()
    assert sink.is_valid()


def test_a_visual_edge_survives_save_and_reload(graph_with_library_system):
    graph = graph_with_library_system
    source, sink = _probes(graph)
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()
    data = graph.to_dict()
    assert "propagation" not in data["edges"][edge.edge_id]

    graph.clear()
    graph.load_from_dict(data)
    graph.force_validation()

    reloaded = graph.get_edge_wrapper(edge.edge_id)
    assert reloaded is not None
    assert reloaded.state.is_valid()


def test_deleting_a_visual_edge_is_undoable(graph_with_library_system, library_system):
    from haywire.core.graph.editor import Editor

    graph = graph_with_library_system
    editor = Editor(graph, library_system.get_node_factory())
    source, sink = _probes(graph)
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()

    assert editor.remove_elements([], [edge.edge_id])
    assert graph.get_edge_wrapper(edge.edge_id) is None

    assert editor.undo()
    graph.force_validation()
    restored = graph.get_edge_wrapper(edge.edge_id)
    assert restored is not None and restored.state.is_valid()  # noqa: PT018


def test_a_reroute_splits_a_visual_edge(graph_with_library_system, library_system):
    from haywire.core.graph.editor import Editor

    graph = graph_with_library_system
    editor = Editor(graph, library_system.get_node_factory())
    source, sink = _probes(graph)
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()

    reroute_id = editor.split_edge_with_reroute(edge.edge_id, (150.0, 0.0), "haywire-core:node:RerouteNode")
    graph.force_validation()

    assert reroute_id is not None
    reroute = graph.get_node_wrapper(reroute_id)
    assert reroute is not None and reroute.is_valid()  # noqa: PT018
    assert all(e.state.is_valid() for e in graph.edge_wrappers.values())
```

Check `Editor.remove_elements` / `undo` / `split_edge_with_reroute` against `editor.py` (lines 206, 488, 293) and adapt calls only, never assertions. If `split_edge_with_reroute` refuses a non-data edge by design (its docstring says "Split a data edge"), name that in the report and stop: whether a reroute may split a visual edge is a decision.

Create `tests/core/test_validation/test_visual_pins.py`:

```python
"""The structural validator ignores VISUAL pins, except on a reroute."""

import pytest

from haywire.core.types.enums import PortType
from haywire.core.types.wire import WireRole

pytestmark = pytest.mark.unit


class _Port:
    def __init__(self, port_id, port_type, role):
        self.id = port_id
        self.port_type = port_type
        self._role = role
        self.wire_key = f"lib:wire:{role.name}"
        self.is_dependent = role is WireRole.DEPENDENT

    def has_pin(self):
        return True

    def has_role(self, role):
        return self._role is role


class _Node:
    def __init__(self, node_type, ports, subscription=None):
        from haywire.core.node.behavior import NodeBehaviorFlags

        self.behavior = NodeBehaviorFlags(node_type=node_type)
        self.ports = {p.id: p for p in ports}
        self.event_subscription = subscription
        self.identity = type(
            "_Identity", (), {"_is_subgraph_input": True, "_is_subgraph_output": False, "_is_graph_node": False}
        )()

    def get_ports(self, is_port_type=None, has_pin=None, is_role=None, is_not_role=None, **_):
        return [
            p
            for p in self.ports.values()
            if (is_port_type is None or p.port_type == is_port_type)
            and (is_role is None or p.has_role(is_role))
            and (is_not_role is None or not p.has_role(is_not_role))
        ]


def _validate(node):
    from haywire.core.validation.structural_validator import StructuralValidator

    validator = StructuralValidator.__new__(StructuralValidator)
    wrapper = type("_Wrapper", (), {"node": node, "graph": None})()
    return validator.validate_node(wrapper)


def test_an_event_node_may_carry_a_visual_inlet():
    from haywire.core.node.behavior import NodeType

    node = _Node(
        NodeType.EVENT,
        [_Port("note", PortType.INLET, WireRole.VISUAL), _Port("exec", PortType.OUTLET, WireRole.SEQUENCE)],
        subscription=object(),
    )
    assert _validate(node)[0]


def test_a_data_node_may_carry_visual_pins():
    from haywire.core.node.behavior import NodeType

    node = _Node(
        NodeType.DATA,
        [_Port("note", PortType.INLET, WireRole.VISUAL), _Port("value", PortType.OUTLET, WireRole.DEPENDENT)],
    )
    assert _validate(node)[0]


def test_a_boundary_node_ignores_a_visual_pin_against_its_direction():
    from haywire.core.node.behavior import NodeType

    node = _Node(
        NodeType.BOUNDARY,
        [_Port("note", PortType.INLET, WireRole.VISUAL), _Port("out", PortType.OUTLET, WireRole.DEPENDENT)],
    )
    assert _validate(node)[0]
```

Adapt the fakes to the real `validate_node` dispatch if a check reads another attribute. The assertions stay as they are. If `NodeBehaviorFlags` has no `node_type=` keyword, mirror how `tests/core/test_undo/test_split_edge_reroute.py::_reroute_validator_with_ports` builds one.

Run: `uv run pytest tests/core/test_edge/test_visual_wire.py tests/core/test_validation/test_visual_pins.py -q`
Expected: FAIL. The edge build looks for an adapter chain between `TEST_VISUAL` and `TEST_VISUAL_COUNT` (none exists, so that test fails), a pipe is built for the visual edge, and the validator counts the visual pins.

- [ ] **Step 3: The edge**

In `edge_wrapper.py`:

1. Import `WireRole` with the other `..types.wire` names.
2. Add the property after `wire_type`:

```python
    @property
    def carries_values(self) -> bool:
        """False for an edge on a ``VISUAL`` wire, which is drawn and saved but builds no adapter chain and no pipe."""
        wire = self.wire_type
        return wire is None or wire.role is not WireRole.VISUAL
```

3. In `build`:

```python
        if self._formal_validation():
            self._fit_propagation()
            if not self.carries_values:
                self._build_drawn_only()
                logger.debug(".. drawn-only edge built.")
                return
            if self._build_adapter_chain():
                if self._test():
                    logger.debug(".. rebuilding edge done.")
                    return
```

4. Add after `_fit_propagation`:

```python
    def _build_drawn_only(self) -> None:
        """Mark a ``VISUAL`` edge built: it has no adapter chain to build or test."""
        self._first_adapter = None
        self._edge.chain_adapter_keys = []
        self._state.is_built = True
        self._state.has_test_passed = True
```

In `port.py`, `_refresh_pipes`, the loop becomes:

```python
                for wrapper in self.get_valid_edges():
                    # A VISUAL edge gets no pipe: nothing travels on it.
                    if wrapper.carries_values:
                        self._pipes.add_pipe(wrapper)
```

Then check the readers of `first_adapter` and `chain_adapter_keys`: the edge menu's chain rows, the inspector, Farmhand's edge detail and the connection-info popup. Each must render an empty chain without raising. Any that raises: make it treat an empty chain as "no adapters", and name it in the report.

- [ ] **Step 4: The validator**

In `structural_validator.py`, add above the class:

```python
def _executing(ports: list) -> list:
    """*ports* without those on a ``VISUAL`` wire, which never take part in execution."""
    return [p for p in ports if not p.has_role(WireRole.VISUAL)]
```

Wrap the three rule sites, and leave the reroute rule unwrapped (a visual reroute's pins are its only ports):
- `_validate_event_node`: `inlets = _executing(node.get_ports(is_port_type=PortType.INLET, has_pin=True))`;
- `_validate_data_node`: `ports = _executing(node.get_ports(is_not_role=WireRole.DEPENDENT, has_pin=True))`;
- `_validate_boundary_node`: both `inlets` and `outlets` wrapped the same way.

Add a module docstring bullet: "- Pins on a ``VISUAL`` wire never make a node invalid, except on a reroute".

- [ ] **Step 5: Run, then the gate**

Run the two test files, then `uv run pytest tests/core/test_edge tests/core/test_graph tests/core/test_undo -q -n 4`. Expected: PASS.

Run the ruff check and mypy on the changed files, the pre-commit gate and the browser tier. Expected: green.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/edge/edge_wrapper.py packages/haywire-core/src/haywire/core/types/port.py packages/haywire-core/src/haywire/core/validation/structural_validator.py tests/core/test_edge/test_visual_wire.py tests/core/test_validation/
git commit -m "feat(edges): a VISUAL edge is drawn and saved, never executed

An edge on a VISUAL wire validates by wire key, builds no adapter chain and
no pipe, and has no propagation, so the data types at its ends need not
match. The structural validator ignores VISUAL pins except on a reroute.
The edge links, saves, reloads, undoes and splits like any other.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

Check `git status --short tests/core/test_validation/` first. Add only the new test file, plus `__init__.py` if you created one.

---

### Task 7: `VISUAL` across Group boundaries (Q41)

**Files:**
- Test: create `tests/core/test_graph/test_visual_wire_group.py`
- Modify: only if a test shows a break. Then refuse by mechanism (Q41) and stop and report.

**Interfaces:**
- Consumes: Task 6's `VisualProbeNode` and `TEST_VISUAL`; the collapse action as `tests/core/test_undo/test_collapse_expand.py` drives it.

- [ ] **Step 1: Write the tests**

Create `tests/core/test_graph/test_visual_wire_group.py`:

```python
"""A VISUAL wire crosses a Group boundary like any other wire type (decision Q41)."""

import pytest

from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.types import WireRole
from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_CARD = "haywire-core:node:GraphNode"


def _probe_key():
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    return VisualProbeNode.class_identity.registry_key


def _chain(graph):
    """outer_a → inner_a → inner_b → outer_b, every edge on the visual wire."""
    nodes = [make_node(graph, _probe_key(), position=(300 * i, 0)) for i in range(4)]
    for left, right in zip(nodes, nodes[1:]):
        make_edge(graph, left.node_id, "note_out", right.node_id, "note_in")
    graph.force_validation()
    return nodes


def _collapse(graph, node_ids):
    action = CollapseToGraphNodeAction(
        graph=graph,
        node_ids=list(node_ids),
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
        label="Group",
    )
    action.execute()
    return action


def test_collapsing_across_a_visual_edge_keeps_every_edge_valid(graph_with_library_system):
    graph = graph_with_library_system
    _outer_a, inner_a, inner_b, _outer_b = _chain(graph)

    action = _collapse(graph, [inner_a.node_id, inner_b.node_id])
    graph.force_validation()

    assert all(w.is_valid() for w in graph.node_wrappers.values())
    assert all(e.state.is_valid() for e in graph.edge_wrappers.values())
    roles = {e.wire_type.role for e in graph.edge_wrappers.values() if e.wire_type is not None}
    assert roles == {WireRole.VISUAL}

    data = graph.to_dict()
    graph.clear()
    graph.load_from_dict(data)
    graph.force_validation()
    assert all(e.state.is_valid() for e in graph.edge_wrappers.values())
    assert action is not None


def test_undoing_the_collapse_restores_the_visual_chain(graph_with_library_system):
    graph = graph_with_library_system
    nodes = _chain(graph)
    before = {(e.source_node_id, e.sink_node_id) for e in graph.edge_wrappers.values()}

    action = _collapse(graph, [nodes[1].node_id, nodes[2].node_id])
    action.undo()
    graph.force_validation()

    after = {(e.source_node_id, e.sink_node_id) for e in graph.edge_wrappers.values()}
    assert after == before
    assert all(e.state.is_valid() for e in graph.edge_wrappers.values())


def test_a_visual_wire_grows_a_boundary_slot(graph_with_library_system):
    graph = graph_with_library_system
    definition = graph.add_subgraph(SubgraphDefinition(key="sg_visual", label="G"))
    output = make_node(definition, _OUTPUT)
    probe = make_node(definition, _probe_key())
    slot = next(p for p in output.node.ports.values() if p.id.startswith("slot_"))

    edge = definition.create_edge_wrapper(probe.node_id, "note_out", output.node_id, slot.id)
    definition.force_validation()

    assert edge is not None
    grown = output.node.ports[slot.id]
    assert grown.wire_type is not None and grown.wire_type.role is WireRole.VISUAL  # noqa: PT018
    assert edge.state.is_valid()
```

Check the slot-port prefix and `add_subgraph`'s signature against `tests/core/test_graph/test_any_flow_slot.py`. Adapt calls only.

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/core/test_graph/test_visual_wire_group.py -q -p no:randomly`.
Expected: PASS. Nothing breaks by construction:
- the boundary nodes copy a visual port's value, which is harmless with no pipe downstream;
- assembly ignores the role;
- the card's validator checks only its binding.

If one fails: find the mechanism that broke, refuse exactly that (the bare `ADD` wildcard declining a `VISUAL` wire, or collapse refusing a selection crossed by one) with an error that names it, change the test to assert the refusal, and stop and report.

- [ ] **Step 3: Ruff check and commit**

```bash
git add tests/core/test_graph/test_visual_wire_group.py
git commit -m "test(groups): a VISUAL wire crosses a Group boundary

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: ADRs, glossary, docs and the generated library docs

The glossary and ADR edits land with the code (they were collected during the inquisition as candidates, not written inline).

**Files:**
- Create: `docs/adr/0043-refuse-only-what-breaks.md`, `docs/adr/0044-link-ceiling.md`
- Modify:
  - `docs/adr/0003-show-widget-strategy.md`, `docs/adr/0034-add-is-a-type.md`, `docs/adr/0042-wire-types-replace-flowtype.md` (superseded marks)
  - `docs/reference/glossary.md`
  - `docs/components/datatypes/datatype-canon.md:50`
  - `docs/architecture/execution/edges/edges-arch.md:293`
  - `docs/architecture/execution/callbacks/callbacks-arch.md:32-37`
  - `docs/architecture/graph/graph-arch.md:107`
  - `docs/guides/node-roles.md:92`, `docs/guides/ports.md`
  - `.codemap/modules/haywire-core-engine.md:83`
  - generated library docs (both repos)

- [ ] **Step 1: ADR 0043**

Read `docs/reference/doc-authoring.md` and ADR 0042 for the frontmatter shape. Create `docs/adr/0043-refuse-only-what-breaks.md`:

```markdown
---
name: refuse-only-what-breaks
description: The framework refuses a configuration only where a mechanism breaks, and states the rule by that mechanism, not by a category of type or wire; it defuses the breaking path where it can
status: accepted
see-also: ADR-0003, ADR-0034, ADR-0042, ADR-0044
level: architectural
---

# Refuse only what breaks

**Context.** Several rules refused configurations by category: `@type` refused a widget on any control or callback type, `ArrayType` refused control and callback elements, `PooledType` refused a control element, and nothing refused a value type without a wire type, whose pins then silently matched nothing. Two bare `ADD` slots linked and did nothing. Rules by category hide what they guard and block what works.

**Decision.** The framework refuses a configuration only where something breaks — a crash, unbounded recursion, a value that depends on write order, an edge that can never work — and states the rule by that mechanism. Where the breaking path can be made harmless, it is defused instead of refused. Applied in edge-kinds step 5.2:

- A widget may sit on any type. It writes only to a field that can hold an own value (`DataField.accepts_own_value()`); on a pooled field or an `ADD` slot it refuses the edit and shows the model again, as it already did on a linked inlet.
- Containers of control and callback elements are allowed: each combination runs end to end under test. `PooledType` still refuses an outlet, because a pool holds no own value to write.
- `@type` refuses a value type with no wire type, unless it is a container or wrapper (which takes its element's) or a bare `ADD` (the wildcard): its pins could never link.
- Two bare `ADD` slots do not link: the edge has no wire type to take.
- Pins on a `VISUAL` wire never make a node invalid, except on a reroute: they never take part in execution.
- How many edges a port takes follows the same principle; see ADR 0044.

**Alternatives.** *Keep category rules and add exceptions* — each exception is another category, and the rule still does not say what it protects. *Refuse nothing and document* — a pin that can never link, or a widget that crashes on first edit, fails silently or late.

**Consequences.** A rule's error message names the mechanism and the fix. A configuration nobody anticipated is allowed until something breaks, and the test that finds the break names the rule to add.
```

- [ ] **Step 2: ADR 0044**

Create `docs/adr/0044-link-ceiling.md`:

```markdown
---
name: link-ceiling
description: A port's link count is a ceiling the framework derives from the port's role and its field's storage; a port can only narrow it (single_link); allow_multiple_links is gone
status: accepted
see-also: ADR-0003, ADR-0042, ADR-0043
level: architectural
---

# The link ceiling

**Context.** `DataPort.allow_multiple_links` was one flag with two writers: `__post_init__` overwrote it by flow (later by wire role), and a container's `_configure_port` overwrote it again (`PooledType` set it, `ArrayType` set an outlet's). A port saved it whenever it was true, so a derived value came back as if declared. A port author's own value survived only on callback ports.

**Decision.** The framework derives a **link ceiling** from two facts about the port, read on every call of `DataPort.takes_many_links`:

| | Outlet | Inlet |
|---|---|---|
| value wire (`DEPENDENT`, `IMMEDIATE`) | many | one, many when the field `keeps_value_per_source()` |
| `SEQUENCE` | one — the VM keeps one transition per outlet | many |
| `VISUAL` | many | many |

A container's role is its element's, so `ArrayType[T]`, `OPTIONAL[T]` and `ADD[T]` behave as `T`; `PooledType[T]` lifts its inlet because its field keeps one value per source. A port can only narrow the ceiling, with `single_link=True`, saved only when set. Nothing else writes a link count: `_configure_port` keeps colour and refusals, and mirrors, reroute ports and grown slots start at the ceiling.

**Alternatives.** *Wire types declare per-direction defaults (`outlet_links`, `inlet_links`) and a port overrides them within the limits* — two concepts where one suffices; no wire type in tree needs a ceiling below the mechanism's, and a ClassVar can be added later without breaking anything. *One bool resolved at construction* — its derived value is saved as if declared, and a container's later write skips the limits. *Let a type narrow through `_configure_port`* — reintroduces a second writer.

**Consequences.** A saved `allow_multiple_links` key is ignored on load and dropped at the next save. A callback outlet fans out without declaring anything. Narrowing a port does not narrow the card that mirrors it in a Group.
```

- [ ] **Step 3: Superseded marks**

Follow ADR 0039's form: a `status:` line, a `see-also` entry, and a blockquote under the title.

- **ADR 0003:**
  - `status: superseded-in-part by ADR-0043, ADR-0044`, with `ADR-0043, ADR-0044` added to `see-also`.
  - Blockquote: "> **Link counts are superseded by [ADR 0044](0044-link-ceiling.md)**: `allow_multiple_links` is gone, and a port's link count is a ceiling the framework derives. **Editing a pooled port's widget is refused, not crashed, per [ADR 0043](0043-refuse-only-what-breaks.md)**: showing it is still the author's call."
- **ADR 0034:**
  - `status: superseded-in-part by ADR-0043`.
  - Blockquote: "> **Two bare `ADD` slots no longer connect ([ADR 0043](0043-refuse-only-what-breaks.md)).** The edge would have no wire type to take. A bare `ADD` connects to any other port."
- **ADR 0042:** `status: superseded-in-part by ADR-0043`. Blockquote: "> **The wildcard matches any wire key except another wildcard ([ADR 0043](0043-refuse-only-what-breaks.md)).**"

- [ ] **Step 4: Glossary**

In `docs/reference/glossary.md`:
1. Add a row next to **Pooled inlet**:

```markdown
| **Link ceiling** | How many edges a port may hold at once, derived by the framework from the port's wire role and its field's storage: outlets take many except a control outlet; inlets take one except a control or visual inlet and a **Pooled inlet**. A port can only narrow it, with `single_link`. Read as `DataPort.takes_many_links`. See [ADR 0044](../adr/0044-link-ceiling.md) | allow_multiple_links (removed), connection limit |
```

2. Reword these rows:
   - **DATA port**: "outlets fan-out, inlets accept a single source" → "outlets fan out; an inlet takes one edge unless it is a **Pooled inlet** (see **Link ceiling**)".
   - **CALLBACK port**: "no hardcoded multiplicity rules" → "its outlet fans out, and its inlet takes one edge unless pooled (see **Link ceiling**)".
   - **Pooled inlet**: append "; its field keeps one value per source, which lifts the inlet's **Link ceiling** to many".
   - **Wire key**: "which matches any" → "which matches any wire key except another `*`".

- [ ] **Step 5: Docs**

- **`datatype-canon.md:50`:**
  - Delete "A type on a control or callback wire type gets no widget (5.2 lifts this)."
  - After the container sentence, add: "`@type` refuses a type that has none and is not a container, a wrapper or `ADD`: its pins could never link. Whether a type has a widget is the author's call; a widget writes only to a field that can hold an own value."
- **`edges-arch.md:293`:** the row becomes `| \`DataPort.takes_many_links\` / \`single_link\` | The port's link ceiling, and the setting that narrows it (ADR 0044) |`. Fix any other `allow_multiple_links` mention in the file the same way.
- **`callbacks-arch.md:32-37`:** replace "They have no hardcoded connection rules:" and the `allow_multiple` table with:

```markdown
They follow the link ceiling (ADR 0044):

| Direction | Ceiling |
|---|---|
| Outlet | many: one listener can subscribe to several emitters |
| Inlet | one; emitters use a `PooledType[...]` inlet, whose field keeps one value per source and so takes many, keyed by edge id |
```

- **`graph-arch.md:107`:** before "Deferred values cross when the boundary nodes execute", add: "Every pinned interface port that is not immediate is copied when the boundary nodes execute, a `VISUAL` port included; with no pipe downstream, that copy is harmless."
- **`node-roles.md:92`:** the bullet becomes: "**One listener, many emitters:** a `CALLBACK` outlet fans out by its link ceiling, so a listener needs no flag to target several emitters."
- **`ports.md`:** in the port-flags material (section 3 or the quick reference), add a `single_link=True` entry: "narrows a port to one edge where its link ceiling allows many (ADR 0044)". Check the file for other `allow_multiple_links` mentions and replace them.
- **`.codemap/modules/haywire-core-engine.md:83`:** replace the line with: "- A widget writes only to a field that can hold an own value (`DataField.accepts_own_value()`); `@type` refuses a value type without a wire type, except containers, wrappers and `ADD` (ADR 0043)."

Then run: `grep -rn "allow_multiple_links\|cannot have a widget\|lifts this" docs .insights .codemap CLAUDE.md --include='*.md' | grep -v "docs/superpowers\|docs/archive\|docs/adr/00[0-3]"`
Expected: no hits outside ADRs 0000-0039 and ADR 0003's historical text.

- [ ] **Step 6: Regenerate the library docs**

Run: `uv run haywire docs --all`, then `uv run haywire docs barn/haybale-visiongraph`.
Expected:
- `query_graph.md` shows `takes_many_links`;
- `OPTIONAL`'s type doc loses its `wire_type` line;
- the new testing types and probe nodes get docs.

Use `git status --short` in both repos to see the real changed paths.

- [ ] **Step 7: Docs build**

Run: `uv run mkdocs build --strict > /tmp/mk.log 2>&1; echo "exit=$?"; grep -n "WARNING" /tmp/mk.log`
Expected: only the known warning (`guides/panels.md` links into `.insights/`). Fix any warning that names a file this task touched.

- [ ] **Step 8: Commit both repos**

Commit the haybale-testing generated docs first, within the main-repo commit, by adding every changed docs path explicitly. Unstage anything under `docs/superpowers/` or `internals/`.

```bash
git add docs/adr/0043-refuse-only-what-breaks.md docs/adr/0044-link-ceiling.md docs/adr/0003-show-widget-strategy.md docs/adr/0034-add-is-a-type.md docs/adr/0042-wire-types-replace-flowtype.md docs/reference/glossary.md docs/components/datatypes/datatype-canon.md docs/architecture/execution/edges/edges-arch.md docs/architecture/execution/callbacks/callbacks-arch.md docs/architecture/graph/graph-arch.md docs/guides/node-roles.md docs/guides/ports.md .codemap/modules/haywire-core-engine.md <generated docs paths from git status>
git status --short
git commit -m "docs: refuse only what breaks; the link ceiling

ADR 0043 states the principle and its 5.2 applications; ADR 0044 the link
ceiling. ADRs 0003, 0034 and 0042 are marked superseded in part. Glossary:
Link ceiling, and the DATA port, CALLBACK port, Pooled inlet and Wire key
rows. Canons, guides, architecture docs and the generated library docs
follow.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

In the visiongraph repo, commit its regenerated docs if any changed (`docs: regenerate for the link ceiling` with the trailer).

---

### Task 9: Verify the plan

**Files:**
- Delete (never committed): `tests/core/test_zz_graph_snapshot.py`
- Modify (uncommitted, for the user): `docs/superpowers/plans/2026-10-02-wire-types.md` (status)

- [ ] **Step 1: Saved graphs**

Run: `HW_GRAPH_SNAPSHOT=/tmp/graph_snapshot_5_2_after.json uv run pytest tests/core/test_zz_graph_snapshot.py -q -p no:randomly`, then the comparison script from 5.1's Task 12 Step 1, with the two new file names.

Expected: `IDENTICAL`. An edge between two bare `ADD` slots in a saved graph would now be invalid, which is intended change 5: report it with the graph and edge id. Any other difference is a bug: stop and report it.

Then `rm tests/core/test_zz_graph_snapshot.py`.

- [ ] **Step 2: Full checks**

Run:
- the ruff check on the whole repo and the mypy set;
- the pre-commit gate, the browser tier, the visiongraph tests and `uv run pytest -m perf -q`.

Report the counts against Task 0's.

Then: `grep -rn "allow_multiple_links" --include='*.py' --include='*.vue' --include='*.js' packages barn tests`
Expected: only `port.py`'s `kwargs.pop("allow_multiple_links", None)` and `test_link_ceiling.py`'s legacy-key test.

- [ ] **Step 3: The running studio, step by step with the user**

Unit tests do not see the canvas. Hand the user these checks one at a time, waiting for each result:

1. **Two bare slots.** In `graphs/loop.haywire`, collapse ForLoop + MathOP + ControlSwitch into a Group, then enter it. Dragging from the Subgraph Input's free `add` slot onto the Subgraph Output's free `add` slot is refused.
2. **Listener fan-out.** Add a second TickEmitNode. Drag TickEvent's `listen_callback` to its `callback_names`. Both callback edges stay valid, and the outlet's glyph is the multi variant.
3. **Callback reroute fan-out.** Split the callback edge with a reroute, then drag from the reroute's outlet to the second emitter. Both stay valid. Before 5.2 the second edge displaced the first.
4. **Data inlet stays single.** Drag a second float outlet onto MathOP `value_a`. The new edge replaces the old.
5. **Glyphs.** Data, control and callback pins look as before, except the multi glyph on callback outlets (2, 3).
6. **Reload.** Save to a new file and reload. Every edge is where it was, and the file holds no `allow_multiple_links`.

Report each as passed or failed. A failure is a bug: stop and report.

- [ ] **Step 4: Status**

In `docs/superpowers/plans/2026-10-02-wire-types.md`, set the 5.2 row to:

```markdown
| 5.2 | Rule changes | **Landed** on branch `wire-types-5-1` (both repos), not merged | [2026-10-03-wire-types-5-2-rules.md](2026-10-03-wire-types-5-2-rules.md) | merge; design round D and the 5.3 detail plan |
```

Leave both plan files uncommitted for the user. Report both repos' branch state and the commits made.

---

## Self-review (done while writing)

- **Spec coverage.**
  - Each 5.2 item maps to a task:
    - 8c widget rule: Task 3.
    - 8c read-only guard: Task 2 (Q37, Q38).
    - 8c container refusals: Task 5 (Q39).
    - 8b: Task 3 (Q40).
    - 9a: Task 1 (Q35, Q36, Q42, Q43, Q45).
    - 9c: Task 4.
    - Q21: Task 3.
    - 9d: Tasks 6 and 7 (Q41).
    - Falsy array: Task 5 (Q46).
    - Docs and ADRs (Q44, Q47): Task 8.
  - The design's "`outlet_links` / `inlet_links`" ClassVars and "a port's own `allow_multiple_links=` is honoured" are replaced by Q35/Q36: no wire-type link attributes, and `single_link` narrows only.
- **Behaviour guards.** Every intended change has a test that would have failed before. The snapshot (Tasks 0 and 9) guards the saved graphs, and the gate guards the rest.
- **Names.** `takes_many_links`, `single_link`, `keeps_value_per_source`, `accepts_own_value` and `carries_values` are spelled the same in every task. `allow_multiple_links` survives only as the legacy key popped in `from_spec`.

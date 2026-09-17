# Step 2 — SubgraphDefinition, the Graph-node, and the file format

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `.haywire` file can hold Subgraph definitions in a keyed table, a
`GraphNode` can bind one, and each Graph-node instantiates its own live node set.
Also completes ADR 0035's rename, which rides this step's format bump.

**Architecture:** A Subgraph definition is a `BaseGraph` subclass, so it gets
`props`, `meta`, Variables and validation for free — and gives inner nodes the
`framework < subgraph < node` settings chain through the existing
`settings_bag_for` seam. Instantiation is the paste primitive: mint root-unique
ids, remap edges through an `old → new` map. Design record:
[graph-nodes.md](../2026-09-14-graph-nodes.md), decisions 3, 9, 11, 15, 16, 25.

**Tech Stack:** Python 3.12, pytest.

## Global Constraints

- Line length 109 (`ruff`). CI runs BOTH `ruff check .` and `ruff format --check .`.
- Definitions live in a **keyed table** on the host graph, referenced by key from
  the Graph-node — never inlined into the node's own `node_data`. Inlining would
  permanently foreclose Abstraction (decision 3) and Slice 2's promotion path.
- Ids minted at instantiation are unique **in the root graph's id space**, so the
  whole tree is collision-free and step 3's flat view is a pure lookup shim.
- A pre-feature `.haywire` file must still load. `graphs/` holds real fixtures.

## Pre-Flight Baseline

```sh
uv run ruff check packages/haywire-core/src/haywire/core/graph/ packages/haywire-core/src/haywire/core/types/
uv run mypy packages/haywire-core/src/haywire/core/graph/ packages/haywire-core/src/haywire/core/types/
uv run pytest tests/core/test_graph/ -q
```

## File Structure

| File | Responsibility |
|---|---|
| `packages/haywire-core/src/haywire/core/graph/subgraph.py` | **New.** `SubgraphDefinition` + `instantiate()`. |
| `packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py` | **New.** The `GraphNode` class. |
| `packages/haywire-core/src/haywire/core/graph/base.py` | `to_dict` / `load_from_dict` gain the `subgraphs` table. |
| `packages/haywire-core/src/haywire/core/graph/prehydration/` | Format bump + the fold-key migration. |
| `packages/haywire-core/src/haywire/core/types/port.py` | `parent_group`/`is_group` → `parent_fold`/`is_fold`. |

---

### Task 1: Extract the id-remap helper from paste

**Files:** Modify `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py:527-566`

`PasteClipboardAction` already does exactly what instantiation needs: assign a
fresh `node_id` per node via `generate_unique_node_id()`, build `old_id → new_id`,
rewrite both endpoints of every edge through it, recompute each `edge_id`.

Extract it as a reusable function (suggested home:
`packages/haywire-core/src/haywire/core/graph/utils/`), and have paste call it.
**Do not duplicate the logic** — a second copy will drift.

- [ ] Paste behaviour unchanged; `tests/core/test_undo/` green.

### Task 2: `SubgraphDefinition`

**Files:** Create `packages/haywire-core/src/haywire/core/graph/subgraph.py`

- `SubgraphDefinition(BaseGraph)` plus a stable `key`.
- `instantiate(root_graph, graph_node) -> dict[str, NodeWrapper]` — builds the
  live node set for one Graph-node using Task 1's helper, minting ids from
  **`root_graph`** so the whole tree shares one id space.
- Inner `NodeWrapper`s are constructed with `graph=<this SubgraphDefinition>`.
  That single argument is what delivers decision 16: a node field's `graph()`
  mirror walks `node → wrapper → graph → settings_bag_for(...)`
  (`base.py:686`, ADR 0022), so inner nodes resolve the graph tier from their own
  Subgraph rather than the host.

⚠️ Building a `BaseGraph` is **not inert** — `BaseGraph.__init__` calls
`get_settings_registry()` unconditionally (ADR 0022). A `SubgraphDefinition`
constructed without DI configured raises. See `.insights/project_settings_registry_construction_side_effects.md`.

- [ ] Three Graph-nodes bound to one definition produce three disjoint node sets.
- [ ] Every minted id is unique across host + all instantiations.

### Task 3: `GraphNode`

**Files:** Create `packages/haywire-core/src/haywire/barn/builtin/nodes/graph_node.py`

- `@node(..., hidden=True, is_mutable=True)`. `hidden` means "excluded from
  author-facing selection UIs, still registered and usable"
  (`registry/identity.py:16`) — correct here, because a bare Graph-node is never
  placed from the menu. It is created by the collapse action, or (Slice 2+) by
  placing a Macro, which is its own registry entry.
- `node_data` holds the **subgraph key** into the host's definition table.
- Ports **mirror the boundary nodes' ports** (decision 11): the Subgraph Input's
  outlets become this node's inlets, the Subgraph Output's inlets its outlets.
  Mint them with `self.rejig(...)` — the existing dynamic-port API, used by
  `ControlSwitch` (`barn/haybale-core/haybale_core/nodes/switch.py:64-66`).
- The Graph-node owns the port **values**; the definition owns the **shape**.
  An unconnected inlet's widget value lives here, per instance.
- Node type is **derived**: no EXEC crossings → `DATA`; otherwise `CONTROL`.

- [ ] Adding a port to a boundary node reconciles every bound Graph-node.
- [ ] Removing one drops exactly the edges that lost a port.

### Task 4: Serialization

**Files:** Modify `packages/haywire-core/src/haywire/core/graph/base.py:709-731,781-798`

- `to_dict()` gains `"subgraphs": {key: <serialized definition>}`.
- `load_from_dict()` restores the table **before** the nodes loop, so a
  `GraphNode` can instantiate during `wrapper.build()`.

- [ ] A graph containing a Group round-trips through `to_dict`/`load_from_dict`.

### Task 5: Format bump, and finish ADR 0035

**Files:** Modify `packages/haywire-core/src/haywire/core/graph/prehydration/`, `core/types/port.py`, and the 26 call sites

Bump `CURRENT_FORMAT_VERSION`. The migration for pre-feature files is a no-op for
`subgraphs` (absent restores nothing) — but the bump is the vehicle for the
rename below, and for a later Macro migration that must recurse into definitions.

**The rename** (decision 25). ADR 0035 replaced `group()`/`GROUP` with `fold()`/`FOLD`
but left two internals behind, and they mean *fold membership*:

- `DataPort.parent_group` → `parent_fold`, `DataPort.is_group` → `is_fold`
  (`core/types/port.py:134,140`).
- 26 call sites across `core/node/data.py`, `barn/haybale-studio/.../stacked_skin.py`,
  and `barn/haybale-graph-editor/.../panels/properties/introspect/node_ports.py`.
- **They are serialized** — `graphs/any_and_nonde.haywire` carries both keys today.
  So the migration must rename them in loaded files. This is why the rename rides
  this bump rather than earning a version of its own later.

After this, "group" has exactly one meaning in the codebase: a Graph-node variant.

- [ ] A `.haywire` file written before the bump loads with its folds intact.
- [ ] `grep -rn "parent_group\|is_group" packages/ barn/` returns nothing.

---

## Verification

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ barn/ tests/
uv run pytest tests/core/test_graph/ tests/core/test_undo/ tests/ui/skin/ -q
```

New tests:

- Round-trip: a graph containing a Group survives `to_dict`/`load_from_dict`.
- Pre-feature file loads; `graphs/any_and_nonde.haywire` keeps its folds after the
  key rename.
- Instancing: three Graph-nodes on one definition → three disjoint node sets, no
  id collisions anywhere in the tree.
- Settings: an inner node's `graph()` mirror resolves from its own Subgraph, not
  the host graph.

## Depends on / unblocks

- Depends on: step 1 (boundary node classes must exist to be mirrored).
- Unblocks: step 3 (the flat view walks instantiations), step 4 (the action
  creates definitions).

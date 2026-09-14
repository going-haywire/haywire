# Step 1 — NodeType.BOUNDARY and the boundary nodes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Haywire the two node classes that define a Subgraph's interface —
`SubgraphInputNode` and `SubgraphOutputNode` — plus the node type and validator
rules they need. Nothing consumes them yet; step 4 is what creates them.

**Architecture:** These are structural nodes, not authored ones: born port-less,
minted by an action, never offered in the add-node menu, and elided at assembly.
`RerouteNode` is already exactly that shape, so this step copies its pattern
point for point rather than inventing one. See the design record:
[2026-09-14-graph-nodes.md](2026-09-14-graph-nodes.md), decisions 4, 6, 7, 8, 19.

**Tech Stack:** Python 3.12, pytest.

## Global Constraints

- Line length 109 (`ruff`). CI runs BOTH `ruff check .` and `ruff format --check .`.
- Type checking via `mypy` over the package list in `CLAUDE.md`.
- Boundary nodes must load **headless** — they live in `haywire.barn.builtin` and
  bind their skin by registry-key *string*, never by importing the skin class.
  Importing it would pull `haywire.ui` + NiceGUI onto the execution path.
- `NodeType` is an `IntFlag`. `BOUNDARY` carries neither the DATA nor the CONTROL
  bit, exactly like `REROUTE = 32`.

## Pre-Flight Baseline

```sh
uv run ruff check packages/haywire-core/src/haywire/core/node/ packages/haywire-core/src/haywire/barn/builtin/
uv run mypy packages/haywire-core/src/haywire/core/node/ packages/haywire-core/src/haywire/barn/builtin/
uv run pytest tests/core/node/ tests/core/test_validation/ -q
```

All three must be clean. If not, stop and raise it with the user.

## File Structure

| File | Responsibility |
|---|---|
| `packages/haywire-core/src/haywire/core/node/behavior.py` | `NodeType`. Gains `BOUNDARY`; its docstring is corrected. |
| `packages/haywire-core/src/haywire/barn/builtin/nodes/subgraph_io.py` | **New.** The two boundary node classes. |
| `packages/haywire-core/src/haywire/core/node/registry.py` | Gains two singleton slots beside `_reroute_node`. |
| `packages/haywire-core/src/haywire/core/validation/structural_validator.py` | Gains `_validate_boundary_node` and the Subgraph-level rule. |
| `packages/haywire-core/src/haywire/barn/builtin/skins/subgraph_io_skin.py` | **New.** Rail-style card for boundary nodes. |

---

### Task 1: Correct the `NodeType` docstring

**Files:** Modify `packages/haywire-core/src/haywire/core/node/behavior.py:10-34`

The docstring claims the types "each follow from a control port configuration":
`CONTROL: 1 ctrl inlet / 1 ctrl outlet`, `LOOPBACK: 1 ctrl inlet / 2+ ctrl outlets`.
Both halves are false.

- `ControlSwitch` is `NodeType.CONTROL` with **two** EXEC outlets
  (`barn/haybale-core/haybale_core/nodes/switch.py:28,53-54`).
- `_validate_loopback_node` (`structural_validator.py:234-262`) distinguishes
  LOOPBACK by *outlet flags* — at least one `is_loopback_outlet=True` and one
  `False` — and has never checked counts.

Rewrite to the enforced rule: CONTROL = ≥1 control inlet and ≥1 control outlet;
LOOPBACK = a CONTROL node carrying at least one loopback and one non-loopback
outlet. **No code change.**

- [ ] Docstring corrected; `uv run pytest tests/core/node/ -q` still green.

### Task 2: Add `NodeType.BOUNDARY`

**Files:** Modify `packages/haywire-core/src/haywire/core/node/behavior.py`

- `BOUNDARY = 64` — standalone, no DATA or CONTROL bit.
- Add `is_boundary_node` beside `is_reroute_node` in the computed properties.
- Document it in the class docstring the way `REROUTE` is documented.

- [ ] `NodeType.BOUNDARY` exists; `NodeType.BOUNDARY & NodeType.CONTROL == 0`.

### Task 3: The two boundary node classes

**Files:** Create `packages/haywire-core/src/haywire/barn/builtin/nodes/subgraph_io.py`

Model on `packages/haywire-core/src/haywire/barn/builtin/nodes/reroute.py` in full:

- `@node(label=..., node_type=NodeType.BOUNDARY, hidden=True, _is_subgraph_input=True)`
  (and `_is_subgraph_output=True` for the other).
- `init()` declares **no ports** — step 4's collapse action stamps them.
- `class props(BaseNode.props)` overriding `skin` as a plain `setting[CHOICES]`
  bound by registry-key string, so the graph's default skin cannot reach them
  (`reroute.py:56-76`).
- `post_init()` hides the chrome categories, as `reroute.py:83-87` does.
- `worker()` is never called under inlining — both nodes are elided at assembly
  (step 3). Leave it returning `None` with a docstring saying so.

**Direction rule:** the Input node carries only **outlets**, the Output node only
**inlets**. They are named for the side they represent on the Graph-node card,
not for their own ports. State this in both class docstrings — it is the single
most common misreading of this pattern.

- [ ] Both classes register; `hidden=True` keeps them out of `list_visible_names()`.
- [ ] Importing the module does not import `haywire.ui` or `nicegui`.

### Task 4: Registry singleton slots

**Files:** Modify `packages/haywire-core/src/haywire/core/node/registry.py`

Mirror `_reroute_node` (`registry.py:20-21,68-75,89-91,99-101`):

- `_subgraph_input_node` / `_subgraph_output_node` fields.
- `_register_class` sets each from its `_is_subgraph_input` / `_is_subgraph_output`
  marker, warning on override.
- `_unregister_class` clears the slot with a warning.
- `_get_subgraph_input_node()` / `_get_subgraph_output_node()` accessors.

This is what lets step 4 find the classes without hardcoding a registry key.

- [ ] Both slots populate on library load and clear on unregister.

### Task 5: Validator rules

**Files:** Modify `packages/haywire-core/src/haywire/core/validation/structural_validator.py`

Add `_validate_boundary_node`, dispatched **before** the DATA/CONTROL rules the
way `_validate_reroute_node` is (`structural_validator.py:89`, `:195-232`):

- Port-less is valid (latent, awaiting the collapse action).
- Every port faces one direction — Input outlets only, Output inlets only.
- No loopback outlet may cross the boundary.

Add the **Subgraph-level** rule (decision 6): a Subgraph contains exactly one
Input and one Output boundary node, and **no EVENT or OUTPUT node**. An EVENT
node inside would be rooted as a spurious flow by `_identify_event_nodes`
(`flow_assembly_manager.py:97-103`); an OUTPUT node would end the host flow.

Return `(is_valid, error_message, suggestions)` like the siblings.

- [ ] A boundary node with mixed-direction ports fails with a named reason.
- [ ] A Subgraph containing an EVENT node fails validation.

### Task 6: Skin

**Files:** Create `packages/haywire-core/src/haywire/barn/builtin/skins/subgraph_io_skin.py`

A rail-style card — the boundary nodes read as edges of the canvas, not as
ordinary nodes. Follow `docs/reference/design-guide.md` for tokens; follow
`reroute_skin.py` for registration shape.

- [ ] Skin registers; boundary nodes render with it and ignore the graph default.

---

## Verification

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ tests/
uv run pytest tests/core/node/ tests/core/test_validation/ -q
```

New tests under `tests/core/node/test_boundary_nodes.py`:

- Both classes are registered and **absent** from `list_visible_names()`.
- The registry's two singleton slots resolve to them.
- A boundary node accepts a port-less state.
- Mixed-direction ports fail validation with a named reason.
- A Subgraph with two Input nodes, or with an EVENT node, fails validation.

## Depends on / unblocks

- Depends on: nothing.
- Unblocks: step 2 (the definition holds these), step 4 (the action creates them).

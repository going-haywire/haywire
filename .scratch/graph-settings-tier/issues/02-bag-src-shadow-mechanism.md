# 02 — Bag-src shadow: descriptor address type, cell sync, fallback

**What to build:** A node author can declare a field that shadows a graph-bag field with the exact same syntax used for framework shadows, and get the full chained behaviour: unset tracks the graph value live, a local set wins, reset falls back to the *current* graph value, and a bag with no reachable graph behaves byte-for-byte like today's direct framework shadow. This is the heart of the feature; it is built and verified against a test node class — the builtin skin field is NOT re-sourced here (that is ticket 03).

The declaration surface is fixed by the design interview (from the author's sketch):

```python
skin = shadow(src=GraphProperties.default_skin, ...)
```

Spec: `.scratch/issues/graph-settings-tier.md`. Key decisions binding this ticket:

- `shadow()` learns a second address type: when the given src descriptor carries no registry key (it lives on a per-instance flavour), record the *descriptor object* itself instead of a mirror key. The field-name hook additionally records the descriptor's owner class. The "is this a mirror" predicate covers both address types. IType inherits from src transitively per existing mirror rules; `widget_config` must be re-supplied, as today.
- Bag-to-bag cell sync: at bag construction, wiring resolves the recorded descriptor to the owning graph's bag instance (node → wrapper → graph → the `settings_bag_for` seam from ticket 01), seeds this field's own cell from the src field's cell, and subscribes an adapter to the src cell's change event applying the per-hop rule: *if this field is not locally set, write the new value into this field's cell*. The node bag keeps its **own** cell and listens — it never borrows the graph's cell (a locally-set node value must be able to diverge).
- Transitive composition must hold end to end: a framework change flows registry → graph bag cell → node cell → node subscribers, stopping at the first tier that holds an opinion.
- Fallback: a bag whose node is absent, whose node is in no graph, or whose graph lacks the src bag falls back by walking the src-descriptor chain to the terminal registry key — preserving every existing headless/standalone-bag usage unchanged.
- Cleanup: the node bag's `cleanup()` detaches its adapters from graph-owned cells (mandatory — those cells outlive node bags, same rule as registry-owned cells).
- No changes to `SettingsRegistry.resolve()` or the workspace/global tiers.

Testing (one seam): public Settings/Graph API with a test node class carrying a bag-src shadow. Assert values, subscribe/subscribe_field notifications, and reset order — never private sync internals. Prior art: mirror-cell-authoritative and cell-subscription settings tests.

**Blocked by:** 01 — GraphSettings flavour + GraphProperties bag.

**Status:** ready-for-agent

- [ ] A test node's bag-src shadow field reads the graph's current value when unset and follows graph-bag changes live (both bag-level and per-field subscribe fire)
- [ ] A locally-set node value wins over graph changes; node `reset()` returns to the graph's *current* value and resumes tracking
- [ ] Framework → graph → node propagation composes transitively; a graph-level opinion stops framework changes from reaching tracking nodes until the graph resets
- [ ] A standalone bag (no node/graph) resolves and tracks exactly as a direct framework shadow does today
- [ ] After node removal/cleanup, graph-bag changes no longer fire the removed node's callbacks
- [ ] Promotion of a bag-src shadow field to a port still works (rides the same cell)
- [ ] Full test suite, ruff (check + format), and mypy pass with no new findings

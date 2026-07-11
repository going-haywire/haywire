# 03 — Re-source NodeProperties.skin: the chain live in the app

**What to build:** The user-facing payoff. A graph author changes the graph's default skin and every node without its own skin opinion restyles immediately; a node with a local skin keeps it; resetting falls back one tier at a time (node → graph → framework). Old saved graphs load unchanged, and pasting nodes between graphs re-tracks the destination graph's default for unset fields while keeping local overrides.

Spec: `.scratch/issues/graph-settings-tier.md`. Key decisions binding this ticket:

- NodeProperties' `skin` field changes its shadow src from the framework studio-skin setting to `GraphProperties.default_skin` (the ticket-02 mechanism). The serialized attribute name and bare-value shape are unchanged — previously saved graphs must load as-is.
- Import-order constraint: the graph-properties module must be importable from the node-properties module without a cycle (it depends only on skin settings and the settings core).
- The node's skin row in the properties panel renders and behaves exactly as before (same widget, same choices) — the interposed tier is invisible unless used.
- Skin rendering reacts to graph-tier changes through the existing cell-event machinery — no renderer changes expected; verify, don't rebuild.

Testing (one seam): public Settings/Graph API plus graph dict round-trips with real builtin nodes. Regression fixtures per spec: a pre-feature saved graph (no props block) loads with default graph settings and unchanged node skins; a node bag constructed headless resolves the skin exactly as before this feature.

**Blocked by:** 02 — Bag-src shadow mechanism.

**Status:** ready-for-agent

- [ ] With nodes in a graph: setting `graph.props.default_skin` changes the skin of every node whose `props.skin` is unset; nodes with a local skin are unaffected
- [ ] Node skin `reset()` falls back to the graph default; graph `reset()` falls back to the framework default, tracking nodes following each time
- [ ] A pre-feature graph fixture loads unchanged (default graph settings, node skin values preserved, no warnings)
- [ ] Save/load round-trip of a graph with a graph-level skin opinion and a mix of overridden/tracking nodes restores all three tiers correctly
- [ ] Nodes pasted into another graph keep locally-set skins; unset skins re-track the destination graph's default
- [ ] Skin promotion on the node field still works
- [ ] Verified in the running app (change graph skin → canvas restyles)
- [ ] Full test suite, ruff (check + format), and mypy pass with no new findings

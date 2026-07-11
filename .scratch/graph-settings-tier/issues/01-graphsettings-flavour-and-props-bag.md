# 01 — GraphSettings flavour + GraphProperties bag, serialized with the graph

**What to build:** A graph owns its own settings bag. After this ticket, a graph author (programmatically) can set a graph-level default node skin on `graph.props`, watch it track the framework studio-skin setting live while unset, override it per graph, reset it back, and have the opinion survive a save/load round-trip of the graph — with old graph files (no settings block) loading unchanged.

Spec: `.scratch/issues/graph-settings-tier.md`. Key decisions binding this ticket:

- New `GraphSettings` base class — a fourth Settings flavour parallel to NodeSettings: per-instance cells, never registered with the SettingsRegistry, a graph backref instead of a node backref, no port promotion (promote must fail loudly or no-op, as it does for node-less bags today).
- One framework bag `GraphProperties` accessed as `graph.props`, instantiated by the graph at construction with the registry acquired the same way node bags acquire it. Initial field: `default_skin`, a `shadow()` of the framework studio-skin setting (this hop uses the **existing** registry-key mirror — no new mirror machinery in this ticket), with the skin-choices widget config re-supplied per existing mirror rules.
- The graph exposes a single lookup seam — `settings_bag_for(owner_cls)` — answering "which of my bags is an instance of this class." Plain class matching (haywire-core never hot-reloads). This is the extension seam for ticket 02 and any future library graph bags; mirror code must go through it, never through a hardcoded attribute.
- Graph dict serialization gains a `props` block emitted by the bag's existing to_dict (locally-set values only; empty opinion serializes without noise). On load it restores immediately after graph metadata and **before** nodes. An absent block is valid and restores nothing.
- Graph teardown (clear/close) cleans up the bag, releasing its registry mirror subscriptions — no leaked registry handlers after a graph is closed.

Testing (per spec, one seam): public Settings/Graph API only — descriptor reads/writes, subscribe callbacks, reset, graph dict round-trips. Prior art: the mirror-cell-authoritative settings tests and the graph base-serialization tests.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] `graph.props.default_skin` reads the resolved framework studio skin when unset, and follows a framework/workspace change live (subscribe fires)
- [ ] Setting `graph.props.default_skin` wins over the framework value; `reset()` returns to the current framework resolution and resumes tracking
- [ ] Graph dict round-trip preserves a locally-set `default_skin`; an opinion-less graph emits an empty/no-noise props block; a dict without the block loads with defaults
- [ ] Props block restores before nodes during graph load
- [ ] `settings_bag_for()` resolves the props bag by owner class and returns nothing for unknown classes
- [ ] Promotion is unavailable on GraphSettings bags
- [ ] After graph teardown, registry changes no longer reach the dead bag (no stale handlers)
- [ ] Full test suite, ruff (check + format), and mypy pass with no new findings

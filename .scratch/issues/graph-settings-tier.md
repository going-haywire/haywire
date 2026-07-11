---
title: Graph-level Settings tier (chained shadows)
labels: [ready-for-agent, enhancement]
status: open
created: 2026-07-10
---

# Graph-level Settings tier (chained shadows)

## Problem Statement

Settings today come in three flavours — FrameworkSettings and LibrarySettings (persistent, resolved through the registry's workspace/global tiers) and NodeSettings (per-node-instance, serialized with the graph). A graph author who wants every node in one graph to use a particular skin has no graph-scoped place to say so: they must either change the framework default (which affects every graph) or override the skin on each node individually. The settings architecture doc has long listed a "per-graph settings tier" as an open question — portable graphs cannot bring their own configuration along.

## Solution

Graphs gain their own Settings flavour. A graph holds a framework-provided settings bag (accessed as `graph.props`) whose fields shadow framework settings; node fields in turn shadow the graph bag's fields. The resolution chain for interposed fields becomes:

**framework default < graph opinion < node opinion**

Realized as *chained shadows*: the graph bag's `default_skin` is a `shadow()` of the framework's studio-skin setting (existing registry-key mirror), and the node's `props.skin` is a `shadow()` of the graph bag's `default_skin` (new bag-to-bag cell mirror). At every hop the existing sync rule applies: *unset tracks, set ignores*. Graph opinions serialize inside the graph file, so a shared graph carries its configuration.

## User Stories

1. As a graph author, I want to set a default node skin on my graph, so that every node without its own skin opinion renders with that skin.
2. As a graph author, I want nodes without a local skin override to follow the graph default live, so that changing the graph skin restyles the whole graph immediately.
3. As a graph author, I want a node's locally-set skin to win over the graph default, so that I can visually single out individual nodes.
4. As a graph author, I want resetting a node's skin to fall back to the *current graph default* (not the framework default), so that the chain is predictable.
5. As a graph author, I want resetting the graph's default skin to fall back to the framework default, with all tracking nodes following, so that clearing an opinion restores the tier below.
6. As a graph author, I want workspace/global changes to the framework skin to propagate through to nodes when neither the graph nor the node holds an opinion, so that the full chain stays live end to end.
7. As a graph author, I want the graph's settings opinions saved inside the graph file, so that a graph shared with someone else brings its own configuration.
8. As a graph author, I want a graph with no opinions to serialize without noise, so that diffs of graph files stay clean.
9. As a graph author, I want existing saved graphs (created before this feature) to load unchanged, so that nothing breaks on upgrade.
10. As a graph author, I want nodes pasted into a different graph to keep their locally-set values while unset fields re-track the destination graph's defaults, so that copy/paste behaves predictably across graphs.
11. As a node author, I want to declare a shadow of a graph-bag field with the same `shadow(src=...)` syntax I already use for framework settings, so that there is no new declaration concept to learn.
12. As a node author, I want the mirror's IType and default widget inherited from the src field per existing mirror rules (with `widget_config` re-supplied), so that chained mirrors behave like existing mirrors.
13. As a node author, I want a bag constructed without a node or graph (unit tests, headless use) to fall back transitively to the framework resolution, so that my existing tests keep passing without constructing graphs.
14. As a node author, I want `subscribe()`/`subscribe_field()` on my bag to fire when a field's value changes because the graph tier changed, so that widgets and workers react uniformly regardless of which tier moved.
15. As a node author, I want promotion of a chained-shadow field to a port to keep working, so that graph-tier interposition does not restrict existing capabilities.
16. As a framework developer, I want a GraphSettings flavour parallel to NodeSettings, so that panels and scope labeling can distinguish graph bags from node bags by class hierarchy, as they do today.
17. As a framework developer, I want the graph-bag lookup behind a single seam on the graph, so that a future extension to library-registered graph bags does not rework mirror code.
18. As a framework developer, I want graph-bag fields excluded from port promotion (a graph has no ports), so that the shared settings-row machinery cannot offer a meaningless action.
19. As a framework developer, I want node-bag cleanup to detach its adapters from graph-owned cells, so that removed nodes leave no stale subscriptions behind.
20. As a framework developer, I want graph teardown to release the graph bag's registry subscriptions, so that closed graphs do not leak registry handlers.
21. As a framework developer, I want the graph's settings block restored before its nodes load, so that node mirrors seed from the correct graph value on load.
22. As a studio user, I want the properties panel to show the graph's settings when nothing is selected (graph scope, parallel to node/library scopes), so that I can edit the graph default skin in place.
23. As a studio user, I want the node's skin row to render and behave exactly as before (same widget, same options), so that the interposed tier is invisible unless I use it.

## Implementation Decisions

- **New flavour `GraphSettings`** — a fourth Settings base class parallel to NodeSettings: per-instance DataField cells, never registered with the SettingsRegistry, a graph backref instead of a node backref, and no port promotion. Lives in the settings package alongside the other flavours.
- **One framework bag: `GraphProperties`** — the graph-side analogue of NodeProperties, owned and instantiated by the graph at construction (registry acquired via the same DI accessor node bags use), accessed as `graph.props`. Initial field: `default_skin`, a `shadow()` of the framework studio-skin setting, with the skin-choices widget config.
- **Node skin re-sourced** — NodeProperties' `skin` field changes its shadow src from the framework studio-skin setting to `GraphProperties.default_skin`. The serialized attribute name and bare-value shape are unchanged, so previously saved graphs load as-is.
- **`shadow()` learns a second address type** — when the given src descriptor carries no registry key (i.e. it lives on a per-instance flavour), `shadow()` records the *descriptor object* itself (`_mirror_src`) instead of a mirror key. `__set_name__` additionally records the descriptor's owner class. `is_mirror` covers both address types. Nothing about the author-facing call syntax changes.
- **Bag-to-bag cell sync (the new mirror hop)** — at bag construction, wiring resolves `_mirror_src` to the owning graph's bag instance (node → wrapper → graph → lookup seam), seeds the field's own cell from the src field's cell, and subscribes an adapter to the src cell's change event: *if this field is not locally set, write the new value into this field's cell*. The node keeps its **own** cell and listens — it does not borrow the graph's cell — because a locally-set node value must be able to diverge. "Unset tracks, set ignores," applied per hop, composes transitively across the chain; all propagation rides the existing cell-event machinery (ADR 0013). No changes to `SettingsRegistry.resolve()` or the workspace/global tiers.
- **Fallback for unreachable graphs** — a bag-src shadow whose bag has no node, whose node is in no graph, or whose graph lacks the src bag falls back by walking the src-descriptor chain to the terminal registry key, behaving byte-for-byte like today's direct framework shadow. This preserves every existing headless/standalone-bag usage.
- **Single lookup seam** — the graph exposes one method (`settings_bag_for(owner_cls)`) that answers "which of my bags is an instance of this descriptor's owner class." Matching is by plain class (haywire-core never hot-reloads, so class-object identity is safe here). This is deliberately a seam, not a mechanism: library-registered graph bags were considered and **rejected for now** because the hot-reload lifecycle (rebinding live graph bags and every node's cell subscriptions into them on library reload) carries edge cases judged not worth the risk; the seam contains any future extension to one method plus a registration path.
- **Serialization** — the graph's dict representation gains a `props` block emitted by the bag's existing `to_dict()` (locally-set values only; the promoted block is always empty for graph bags). On load it is restored immediately after graph metadata and **before** nodes, so node mirrors seed correctly. Absence of the block (older graphs) is valid and restores nothing.
- **Lifecycle** — node-bag `cleanup()` detaches its adapters from graph-owned cells (mandatory: those cells outlive node bags, same rule as registry-owned cells). Graph close/clear cleans up the graph bag, releasing its registry subscriptions.
- **Promotion exclusion** — graph-bag fields are not promotable (no node, no ports); the shared settings-row menu must not offer promote actions for GraphSettings bags.
- **UI (second milestone)** — the properties editor gains a *graph* scope section rendering `graph.props` via the existing generic bag renderer when no node is selected. The mechanism + serialization land first and are settable programmatically.
- **An ADR should accompany the implementation** — a new settings flavour plus a new mirror address type is an architecture decision of the same weight as ADRs 0013/0014; the settings architecture doc's "per-graph settings tier" open question should be resolved by it, and the settings canon doc extended with the authoring surface.

## Testing Decisions

- **One seam: the public Settings/Graph API.** Tests drive `graph.props` / `node.props` descriptor reads and writes, `subscribe()`/`subscribe_field()` callbacks, `reset()`, and graph dict round-trips (`to_dict`/`load_from_dict`). The chain (framework < graph < node) is asserted purely through observable values and change events — never through private sync internals (`_mirror_src`, adapter lists, `_set_keys` contents).
- **No test-only hooks.** The one new public method (`settings_bag_for`) is exercised implicitly: a working mirror hookup proves it.
- **What makes a good test here:** set/reset at one tier, observe reads and notifications at the tiers above; assert fallback order on reset; assert serialization emits only opinions and that load-order seeds mirrors correctly; assert cleanup detaches (a change after node removal must not fire the removed node's callbacks).
- **Prior art:** the mirror-cell-authoritative and cell-subscription test modules under the core settings tests (registry-key mirror sync, "unset tracks / set ignores", cleanup contracts) and the graph base-serialization tests under the core graph tests (dict round-trips, load-order behavior). Registry wiring via the existing isolated-registry test utilities; standard unit markers.
- **Regression coverage:** an existing saved-graph fixture without a `props` block must load with default graph settings and unchanged node values; a bag constructed with no node/graph must resolve exactly as the pre-change direct framework shadow did.
- **UI milestone tests** ride the existing settings UI harness (data-field/data-value DOM contract) once the graph scope section is built.

## Out of Scope

- **Library-registered graph bags** — explicitly rejected for this iteration due to hot-reload lifecycle risk (live-bag rebinding). Libraries continue to use LibrarySettings (global, hot-reload-safe). The lookup seam keeps the door open.
- Per-graph opinions on arbitrary registry keys — only fields explicitly declared in a graph bag participate.
- Any change to the SettingsRegistry tiers, resolution chain, or JSON persistence.
- Migration of haybale-haystack's `GraphRunSettings` (persisted in the haystack TOML, a different home) — it may adopt the new flavour later but is untouched here.
- UI beyond the graph-scope properties panel section (no dedicated graph-settings dialog, no provenance display).

## Further Notes

- The settings architecture doc anticipated this feature ("per-graph settings tier" under open questions); this spec resolves that question in the "portable graphs bring their own configuration" direction.
- The declaration surface was fixed by the design interview and matches the author's sketch exactly: node fields declare `shadow(src=GraphProperties.default_skin, ...)`; the graph bag declares `shadow(src=<framework setting>, ...)`. No new author-facing concept — only a new address type inside the existing one.
- Import-order constraint: the graph-properties module must be importable from the node-properties module without a cycle (it only depends on skin settings and the settings core).
- Design decisions were settled interactively: bag-to-bag cell sync over registry-key registration of graph bags; a new GraphSettings base over reusing NodeSettings; one framework bag over day-one extensibility; properties-panel graph scope for the UI.

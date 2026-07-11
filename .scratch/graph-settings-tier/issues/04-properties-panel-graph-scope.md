# 04 — Properties panel graph scope

**What to build:** A studio user clicks empty canvas (nothing selected) and the properties editor shows the graph's settings — a *graph* scope section parallel to the existing node/library scopes — rendering `graph.props` through the existing generic bag renderer, editable live. The settings-row menu offers no promote actions for GraphSettings bags (a graph has no ports).

Spec: `.scratch/issues/graph-settings-tier.md`. Key decisions binding this ticket:

- Reuse the generic bag renderer; the graph scope is a placement/wiring change, not a new rendering path. Scope labeling keys off the class hierarchy as it does today for node/library bags.
- Promote actions hidden (not disabled-with-tooltip, hidden) for fields on GraphSettings bags — the shared settings-row menu must not offer a meaningless action.
- Editing `default_skin` in the panel writes the graph bag like any bag write; live propagation to nodes is ticket 02/03's machinery and needs no panel-side plumbing.
- Follow the design-guide rules for any new chrome (no hardcoded colors, design tokens).

Testing: UI harness (data-field / data-value DOM contract) for row rendering and edit round-trip, following the existing harness patterns; a non-UI test asserting promote eligibility is absent for GraphSettings fields.

**Blocked by:** 01 — GraphSettings flavour + GraphProperties bag. (Fully demoable with skin restyling once 03 lands, but nothing in 03 gates the panel work.)

**Status:** ready-for-agent

- [ ] With no node selected, the properties editor shows a graph scope section rendering the graph bag's fields with their stamped widgets
- [ ] Editing the graph default skin in the panel updates the bag (and, once 03 is in, restyles tracking nodes live)
- [ ] Reset affordance on the row returns the field to the framework-tracked value
- [ ] No promote action is offered on any GraphSettings row
- [ ] Selecting a node returns the panel to the node scope unchanged
- [ ] Full test suite, ruff (check + format), and mypy pass with no new findings

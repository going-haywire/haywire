# 05 — ADR + documentation

**What to build:** The paper trail that makes the feature maintainable. A future contributor (or agent) reading the docs finds the fourth flavour, the chained-shadow model, and the reasons for the road not taken — without excavating this design session.

Spec: `.scratch/issues/graph-settings-tier.md`. Deliverables:

- **ADR** (next free number, weight comparable to the cell-authoritative and promotion ADRs): the GraphSettings flavour and the descriptor-src mirror address type. Must record the decisive rejections with their reasons — library-registered graph bags (hot-reload live-bag rebinding risk; the `settings_bag_for` seam is the deliberate containment), registry-key registration of graph bags (per-graph key pollution, class-level declarations can't name per-instance keys), and borrowing the graph's cell (a locally-set node value must diverge).
- **Settings architecture doc**: resolve the "per-graph settings tier" open question by pointing at the ADR; add the new flavour to the schema-class table (registration: never — graph-owned instances) and the chained-shadow hop to the change-notification section; document the fallback walk.
- **Settings canon (authoring guide)**: the author-facing surface — declaring a graph-bag shadow from a node bag, what tracks/wins/resets at each tier, headless behaviour, and the graph scope panel location.
- **Glossary**: entries or amendments for the graph settings flavour and chained shadows, consistent with existing tier vocabulary.
- If a new trap was hit during implementation (tickets 01–04), add the `.insights/` entry per repo policy.

**Blocked by:** 03 — chain live in the app, and 04 — properties panel graph scope (documents both the mechanism and the UI surface as actually landed).

**Status:** ready-for-agent

- [ ] ADR written and cross-linked from the settings architecture doc; open question §10 resolved
- [ ] Architecture doc's flavour table, notification flow, and serialization sections reflect the graph tier
- [ ] Canon doc shows a complete author example of a chained shadow with tier semantics
- [ ] Glossary updated
- [ ] `uv run mkdocs serve` renders the changed pages without warnings
- [ ] Doc statements verified against the landed implementation (no aspirational claims)

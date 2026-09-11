# trim-docs run manifest

Durable state for the docstring-trimming campaign. One row per module.
The `/trim-batch` skill reads this file, claims the next wave of `pending`
rows, and writes back `done` with the commit SHA.

**Edit this file freely between waves** — re-point a module at a different
model, mark one `skip`, or reorder. The skill only ever touches the rows it
claims.

## Status values

- `pending` — not yet attempted
- `running` — claimed by an in-flight wave (if this is stale, a wave died; reset to `pending`)
- `done` — landed and committed, SHA recorded
- `failed` — agent finished but a gate failed; see the notes section
- `skip` — deliberately excluded

## Model assignment

From the 2026-09-11 four-way benchmark on `core/marketstall` (see
`docs/trim-docs-benchmark.md`):

- **opus** — public API and type/graph core, where a false docstring is
  most expensive. Opus was the only tier that audited docstrings *against*
  the code, finding four real contradictions.
- **sonnet** — everything else. Best cut discipline per token; kept every
  contract sentence the trap file hid.
- **haiku** — not used. Passed all mechanical gates but deleted contract
  (a safety invariant, protected examples) in ways only a full diff review
  catches.

## Rules

- One commit per module: `docs: trim docstrings in <module>`.
- A nonzero residual scan count does NOT mean a module is incomplete —
  most findings are false positives (domain acronyms, present-tense
  "no longer"). `core/marketstall` is `done` with 28 residual.
- Modules are processed in wave order: `done` first (history), then opus
  tier by finding count, then sonnet tier by finding count.

| Module | Findings | Model | Status | Commit |
|---|---|---|---|---|
| `packages/haywire-core/src/haywire/core/types` | 71 | opus | done | 151d2ebf |
| `packages/haywire-core/src/haywire/core/registry` | 13 | opus | done | 6deb7776 |
| `packages/haywire-core/src/haywire/ui/panel` | 56 | sonnet | done | dde749c5 |
| `packages/haywire-core/src/haywire/ui/elements` | 32 | sonnet | done | 17a42200 |
| `packages/haywire-core/src/haywire/core/marketstall` | 28 | sonnet | done | 5c88190e |
| `packages/haywire-core/src/haywire/core/signals` | 21 | sonnet | done | f5518ea0 |
| `packages/haywire-core/src/haywire/core/farmhand` | 19 | sonnet | done | 0400cb54 |
| `packages/haywire-core/src/haywire/core/settings` | 75 | opus | done | 21491cc3 |
| `packages/haywire-core/src/haywire/core/node` | 61 | opus | done | 0bd4d594 |
| `packages/haywire-core/src/haywire/core/library` | 61 | opus | done | b2d24854 |
| `packages/haywire-core/src/haywire/core/graph` | 36 | opus | done | c058fabe |
| `packages/haywire-core/src/haywire/core/di` | 29 | opus | pending | — |
| `packages/haywire-core/src/haywire/core/errors` | 27 | opus | pending | — |
| `packages/haywire-core/src/haywire/core/adapter` | 19 | opus | pending | — |
| `packages/haywire-core/src/haywire/core/state` | 18 | opus | pending | — |
| `packages/haywire-core/src/haywire/core/edge` | 14 | opus | pending | — |
| `barn/haybale-core/haybale_core/types` | 13 | opus | pending | — |
| `packages/haywire-core/src/haywire/ui/skin` | 10 | opus | pending | — |
| `packages/haywire-core/src/haywire/core/validation` | 10 | opus | pending | — |
| `packages/haywire-core/src/haywire/core/execution` | 9 | opus | pending | — |
| `packages/haywire-core/src/haywire/core/undo/actions` | 8 | opus | pending | — |
| `packages/haywire-core/src/haywire/core/assembly` | 8 | opus | pending | — |
| `packages/haywire-core/src/haywire/core/undo` | 7 | opus | pending | — |
| `packages/haywire-core/src/haywire/core/graph/prehydration` | 6 | opus | pending | — |
| `barn/haybale-core/haybale_core/nodes` | 2 | opus | pending | — |
| `packages/haywire-core/src/haywire/core/graph/utils` | 1 | opus | pending | — |
| `barn/haybale-studio/haybale_studio/editors` | 54 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/app` | 49 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/publishing/pipeline/steps` | 47 | sonnet | pending | — |
| `barn/haybale-studio/haybale_studio/skins` | 46 | sonnet | pending | — |
| `barn/haybale-marketplace/haybale_marketplace/editors` | 43 | sonnet | pending | — |
| `barn/haybale-marketplace/haybale_marketplace` | 42 | sonnet | pending | — |
| `barn/haybale-share/haybale_share/_flow` | 36 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers` | 36 | sonnet | pending | — |
| `packages/haywire-studio/src/haywire_studio/network` | 35 | sonnet | pending | — |
| `packages/haywire-studio/src/haywire_studio` | 35 | sonnet | pending | — |
| `packages/haywire-studio/src/haywire_studio/security` | 31 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/publishing` | 29 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas` | 27 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/publishing/pipeline` | 24 | sonnet | pending | — |
| `packages/haywire-studio/src/haywire_studio/auth` | 23 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/farmhands` | 23 | sonnet | pending | — |
| `packages/haywire-studio/src/haywire_studio/cli` | 21 | sonnet | pending | — |
| `packages/haywire-studio/src/haywire_studio/packaging/rename` | 18 | sonnet | pending | — |
| `packages/haywire-studio/src/haywire_studio/farmhand` | 18 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/widget` | 17 | sonnet | pending | — |
| `barn/haybale-marketplace/haybale_marketplace/editors/_refresh_flow` | 16 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/editor` | 15 | sonnet | pending | — |
| `barn/haybale-haystack/haybale_haystack/state` | 15 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/session` | 14 | sonnet | pending | — |
| `barn/haybale-marketplace/haybale_marketplace/editors/_add_source_flow` | 13 | sonnet | pending | — |
| `barn/haybale-haystack/haybale_haystack` | 13 | sonnet | pending | — |
| `packages/haywire-studio/src/haywire_studio/packaging/docs` | 12 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/barn/builtin/widgets` | 12 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/components/graph` | 11 | sonnet | pending | — |
| `barn/haybale-haystack/haybale_haystack/editors` | 11 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/update` | 10 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/selection` | 10 | sonnet | pending | — |
| `packages/haywire-studio/src/haywire_studio/packaging` | 9 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/publishing/manifest` | 9 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/surfaces` | 9 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port` | 9 | sonnet | pending | — |
| `barn/haybale-example/haybale_example/widgets` | 9 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/themes` | 8 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/publishing/drift` | 8 | sonnet | pending | — |
| `barn/haybale-marketplace/haybale_marketplace/editors/_uninstall_flow` | 8 | sonnet | pending | — |
| `barn/haybale-marketplace/haybale_marketplace/editors/_install_flow` | 8 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar` | 8 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/components/zoom` | 7 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/barn/builtin/nodes` | 7 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect` | 7 | sonnet | pending | — |
| `barn/haybale-example/haybale_example/types` | 7 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/modals` | 6 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/components/stepper` | 6 | sonnet | pending | — |
| `barn/haybale-testing/haybale_testing/nodes/testbed` | 6 | sonnet | pending | — |
| `barn/haybale-studio/haybale_studio/farmhands` | 6 | sonnet | pending | — |
| `barn/haybale-marketplace/haybale_marketplace/state` | 6 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/editors` | 6 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/extends/codemirror` | 5 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/docs` | 5 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/barn/builtin/skins` | 5 | sonnet | pending | — |
| `barn/haybale-studio/haybale_studio/panels/properties/setting` | 5 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu` | 5 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/panels` | 5 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/components/debug_overlay` | 4 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui` | 4 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/marketstall/host_providers` | 4 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/access` | 4 | sonnet | pending | — |
| `barn/haybale-studio/haybale_studio/panels/account` | 4 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/components/popup` | 3 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/debug` | 3 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core` | 3 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/barn/builtin/types` | 3 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/barn/builtin` | 3 | sonnet | pending | — |
| `barn/haybale-testing/haybale_testing/nodes/benchmark` | 3 | sonnet | pending | — |
| `barn/haybale-studio/haybale_studio/themes` | 3 | sonnet | pending | — |
| `barn/haybale-studio/haybale_studio/settings` | 3 | sonnet | pending | — |
| `barn/haybale-studio/haybale_studio` | 3 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/surface` | 2 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/components/cull` | 2 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/skin` | 2 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/host` | 2 | sonnet | pending | — |
| `barn/haybale-testing/haybale_testing` | 2 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/graph` | 2 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge` | 2 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor` | 2 | sonnet | pending | — |
| `barn/haybale-example/haybale_example/nodes` | 2 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/errors` | 1 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/ui/components/minimap` | 1 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/tooling` | 1 | sonnet | pending | — |
| `packages/haywire-core/src/haywire/core/session/workspace` | 1 | sonnet | pending | — |
| `barn/haybale-testing/haybale_testing/widgets` | 1 | sonnet | pending | — |
| `barn/haybale-testing/haybale_testing/themes` | 1 | sonnet | pending | — |
| `barn/haybale-studio/haybale_studio/state` | 1 | sonnet | pending | — |
| `barn/haybale-studio/haybale_studio/editors/file_browser_menu` | 1 | sonnet | pending | — |
| `barn/haybale-share/haybale_share` | 1 | sonnet | pending | — |
| `barn/haybale-haystack/haybale_haystack/settings` | 1 | sonnet | pending | — |
| `barn/haybale-haystack/haybale_haystack/panels/file_browser/menu` | 1 | sonnet | pending | — |
| `barn/haybale-haystack/haybale_haystack/farmhands` | 1 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/state` | 1 | sonnet | pending | — |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting` | 1 | sonnet | pending | — |

## Failure notes

Append one bullet per `failed` row: module, which gate failed, and the
agent's explanation. Clear the note when the module is retried and lands.

_(none yet)_

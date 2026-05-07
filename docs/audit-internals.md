# Internals Audit — Heuristic Report

Heuristic-only audit of every Markdown file in `internals/`. Git history was used as the truth source — rename-only commits were filtered out so that `last_content_commit` reflects real content edits.

This is the **input** to the triage decision (current / outdated-fixable / obsolete / historical) — it does not check accuracy against the codebase.

Click any path to open the doc in the IDE. Use the three checkbox columns to triage:

- **good** — content is correct and current; carry into the new structure as-is
- **check** — confirm against codebase and update before carrying forward
- **drop** — discard or send to `internals/archive/`

## Status definitions

| Status           | Rule                                     | Reading                                           |
| ---------------- | ---------------------------------------- | ------------------------------------------------- |
| **active**       | last edit ≤30 days, ≥3 commits           | being actively maintained                         |
| **mature**       | last edit ≤60 days, ≥2 commits           | kept up but not churning                          |
| **cold**         | last edit ≤120 days                      | might be done or forgotten — needs accuracy check |
| **touched-once** | only 1 commit ever                       | write-and-forget, likely speculative              |
| **stale**        | last edit >120 days                      | high risk of being out of date                    |
| **rename-only**  | no content commits, only the bulk rename | newly added, no prior history                     |

## Summary

- Total files: **76**
- active: **26**
- mature: **13**
- cold: **20**
- touched-once: **17**

## All files, sorted by maintenance status

| good | check | drop | Status       | Last edit  | Days since | Days old | Commits | Cmt/mo | Lines | Path                                                                                                                                                                |
|:----:|:-----:|:----:| ------------ | ---------- | ----------:| --------:| -------:| ------:| -----:| ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 0          | 66       | 13      | 5.93   | 1757  | [documentation/architecture/app_ui/haywire-ui-architecture-spec_details.md](../internals/documentation/architecture/app_ui/haywire-ui-architecture-spec_details.md) |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 0          | 1        | 4       | 8.00   | 697   | [documentation/architecture/library_state.md](../internals/documentation/architecture/library_state.md)                                                             |
| [ ]  | [x]   | [ ]  | active       | 2026-05-07 | 0          | 1        | 6       | 12.00  | 780   | [documentation/architecture/session_state.md](../internals/documentation/architecture/session_state.md)                                                             |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 0          | 66       | 12      | 5.47   | 644   | [documentation/build_editors.md](../internals/documentation/build_editors.md)                                                                                       |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 0          | 66       | 9       | 4.10   | 972   | [documentation/build_panels.md](../internals/documentation/build_panels.md)                                                                                         |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 0          | 10       | 7       | 14.00  | 1067  | [speculative/archive/context_events_simplification.md](../internals/speculative/archive/context_events_simplification.md)                                           |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 0          | 3        | 3       | 6.00   | 3009  | [superpowers/plans/2026-05-04-panel-contract-phase-1-5.md](../internals/superpowers/plans/2026-05-04-panel-contract-phase-1-5.md)                                   |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 1          | 180      | 6       | 1.01   | 954   | [documentation/Library_System_Developer_Guide.md](../internals/documentation/Library_System_Developer_Guide.md)                                                     |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 1          | 158      | 6       | 1.15   | 742   | [documentation/WIDGET_ADAPTER_GUIDE.md](../internals/documentation/WIDGET_ADAPTER_GUIDE.md)                                                                         |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 1          | 94       | 12      | 3.85   | 233   | [documentation/settings.md/01-overview.md](../internals/documentation/settings.md/01-overview.md)                                                                   |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 1          | 94       | 14      | 4.50   | 350   | [documentation/settings.md/02-node-development.md](../internals/documentation/settings.md/02-node-development.md)                                                   |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 1          | 94       | 12      | 3.85   | 201   | [documentation/settings.md/03-library-development.md](../internals/documentation/settings.md/03-library-development.md)                                             |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 1          | 94       | 7       | 2.25   | 101   | [documentation/settings.md/04-ui-integration.md](../internals/documentation/settings.md/04-ui-integration.md)                                                       |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 1          | 94       | 15      | 4.82   | 355   | [documentation/settings.md/05-reference.md](../internals/documentation/settings.md/05-reference.md)                                                                 |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 1          | 94       | 10      | 3.21   | 412   | [documentation/settings.md/06-testing.md](../internals/documentation/settings.md/06-testing.md)                                                                     |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 1          | 96       | 13      | 4.10   | 97    | [documentation/settings.md/README.md](../internals/documentation/settings.md/README.md)                                                                             |
| [ ]  | [x]   | [ ]  | active       | 2026-05-06 | 1          | 4        | 3       | 6.00   | 787   | [speculative/archive/spec_panel_contract.md](../internals/speculative/archive/spec_panel_contract.md)                                                               |
| [ ]  | [ ]   | [x]  | active       | 2026-05-06 | 1          | 4        | 3       | 6.00   | 344   | [speculative/archive/spec_panel_migration.md](../internals/speculative/archive/spec_panel_migration.md)                                                             |
| [ ]  | [x]   | [ ]  | active       | 2026-05-04 | 3          | 66       | 10      | 4.56   | 500   | [documentation/architecture/haywire_app.md](../internals/documentation/architecture/haywire_app.md)                                                                 |
| [ ]  | [x]   | [ ]  | active       | 2026-05-04 | 3          | 59       | 4       | 2.04   | 191   | [documentation/themes.md/02-workbench-themes.md](../internals/documentation/themes.md/02-workbench-themes.md)                                                       |
| [ ]  | [x]   | [ ]  | active       | 2026-05-04 | 3          | 59       | 4       | 2.04   | 160   | [documentation/themes.md/03-node-themes.md](../internals/documentation/themes.md/03-node-themes.md)                                                                 |
| [ ]  | [x]   | [ ]  | active       | 2026-05-04 | 3          | 59       | 5       | 2.55   | 96    | [documentation/themes.md/README.md](../internals/documentation/themes.md/README.md)                                                                                 |
| [x]  | [ ]   | [ ]  | active       | 2026-04-25 | 11         | 42       | 11      | 7.80   | 265   | [UBIQUITOUS_LANGUAGE.md](../internals/UBIQUITOUS_LANGUAGE.md)                                                                                                       |
| [ ]  | [x]   | [ ]  | active       | 2026-04-13 | 23         | 144      | 5       | 1.05   | 387   | [Architecture/DataFieldsAndPorts/ARCHITECTURE_SUMMARY.md](../internals/Architecture/DataFieldsAndPorts/ARCHITECTURE_SUMMARY.md)                                     |
| [ ]  | [x]   | [ ]  | active       | 2026-04-13 | 23         | 59       | 3       | 1.53   | 206   | [documentation/themes.md/04-library-themes.md](../internals/documentation/themes.md/04-library-themes.md)                                                           |
| [ ]  | [x]   | [ ]  | active       | 2026-04-12 | 25         | 32       | 11      | 10.28  | 1315  | [documentation/design/haywire-ui-design-guide.md](../internals/documentation/design/haywire-ui-design-guide.md)                                                     |
| [ ]  | [x]   | [ ]  | mature       | 2026-05-06 | 1          | 4        | 2       | 4.00   | 2646  | [superpowers/plans/2026-05-03-panel-contract-phase-1.md](../internals/superpowers/plans/2026-05-03-panel-contract-phase-1.md)                                       |
| [ ]  | [x]   | [ ]  | mature       | 2026-05-03 | 4          | 9        | 2       | 4.00   | 224   | [speculative/archive/context_events_simplification_implementation.md](../internals/speculative/archive/context_events_simplification_implementation.md)             |
| [x]  | [ ]   | [ ]  | mature       | 2026-05-03 | 4          | 6        | 2       | 4.00   | 798   | [speculative/archive/panels_and_hosts.md](../internals/speculative/archive/panels_and_hosts.md)                                                                     |
| [ ]  | [x]   | [ ]  | mature       | 2026-05-03 | 4          | 6        | 2       | 4.00   | 1498  | [speculative/archive/spec_panel_A_plus.md](../internals/speculative/archive/spec_panel_A_plus.md)                                                                   |
| [ ]  | [ ]   | [x]  | mature       | 2026-05-03 | 4          | 6        | 2       | 4.00   | 20    | [speculative/archive/spec_panel_A_plus_inspiration.md](../internals/speculative/archive/spec_panel_A_plus_inspiration.md)                                           |
| [x]  | [ ]   | [ ]  | mature       | 2026-04-13 | 23         | 82       | 2       | .73    | 776   | [documentation/Defining_DataTypes.md](../internals/documentation/Defining_DataTypes.md)                                                                             |
| [ ]  | [ ]   | [x]  | mature       | 2026-04-13 | 24         | 32       | 2       | 1.90   | 138   | [superpowers/plans/2026-04-05-hui-icon-registry.md](../internals/superpowers/plans/2026-04-05-hui-icon-registry.md)                                                 |
| [ ]  | [ ]   | [x]  | mature       | 2026-04-13 | 24         | 32       | 2       | 1.90   | 132   | [superpowers/specs/2026-04-05-hui-icon-registry-design.md](../internals/superpowers/specs/2026-04-05-hui-icon-registry-design.md)                                   |
| [ ]  | [ ]   | [x]  | mature       | 2026-04-01 | 36         | 44       | 3       | 2.04   | 135   | [prd/unify-descriptor-hierarchy.md](../internals/prd/unify-descriptor-hierarchy.md)                                                                                 |
| [ ]  | [x]   | [ ]  | mature       | 2026-03-25 | 42         | 178      | 3       | .51    | 223   | [Architecture/Hot_Reload/Hot_Reload_Diagrams.md](../internals/Architecture/Hot_Reload/Hot_Reload_Diagrams.md)                                                       |
| [ ]  | [x]   | [ ]  | mature       | 2026-03-25 | 42         | 180      | 3       | .50    | 567   | [documentation/architecture/Library_System_Technical_Reference.md](../internals/documentation/architecture/Library_System_Technical_Reference.md)                   |
| [x]  | [ ]   | [ ]  | mature       | 2026-03-15 | 53         | 73       | 3       | 1.23   | 774   | [documentation/architecture/library_management.md](../internals/documentation/architecture/library_management.md)                                                   |
| [ ]  | [x]   | [ ]  | mature       | 2026-03-14 | 53         | 59       | 3       | 1.53   | 115   | [documentation/themes.md/01-overview.md](../internals/documentation/themes.md/01-overview.md)                                                                       |
| [ ]  | [x]   | [ ]  | cold         | 2026-03-03 | 65         | 136      | 4       | .89    | 476   | [Architecture/edge/Edge_EdgeWrapper_Implementation_Specification.md](../internals/Architecture/edge/Edge_EdgeWrapper_Implementation_Specification.md)               |
| [ ]  | [ ]   | [x]  | cold         | 2026-03-03 | 65         | 275      | 3       | .33    | 184   | [Architecture/history/node_API/haywire_library_system.md](../internals/Architecture/history/node_API/haywire_library_system.md)                                     |
| [ ]  | [ ]   | [x]  | cold         | 2026-03-03 | 65         | 278      | 3       | .32    | 516   | [Architecture/history/node_API/haywire_node_design.md](../internals/Architecture/history/node_API/haywire_node_design.md)                                           |
| [ ]  | [x]   | [ ]  | cold         | 2026-03-03 | 65         | 80       | 7       | 2.64   | 412   | [documentation/architecture/Edge_connections.md](../internals/documentation/architecture/Edge_connections.md)                                                       |
| [x]  | [ ]   | [ ]  | cold         | 2026-02-22 | 73         | 289      | 23      | 2.42   | 1006  | [documentation/Haywire_design.md](../internals/documentation/Haywire_design.md)                                                                                     |
| [x]  | [ ]   | [ ]  | cold         | 2026-02-17 | 78         | 99       | 10      | 3.07   | 347   | [documentation/Creating_Nodes.md](../internals/documentation/Creating_Nodes.md)                                                                                     |
| [x]  | [ ]   | [ ]  | cold         | 2026-02-17 | 78         | 144      | 4       | .84    | 695   | [documentation/Defining_DataPorts_inside_Nodes.md](../internals/documentation/Defining_DataPorts_inside_Nodes.md)                                                   |
| [ ]  | [ ]   | [x]  | cold         | 2026-02-13 | 82         | 136      | 2       | .44    | 26    | [Architecture/Adapters/ARCHITECTURE.md](../internals/Architecture/Adapters/ARCHITECTURE.md)                                                                         |
| [ ]  | [ ]   | [x]  | cold         | 2026-02-13 | 82         | 158      | 5       | .95    | 228   | [Architecture/DataFieldsAndPorts/README.md](../internals/Architecture/DataFieldsAndPorts/README.md)                                                                 |
| [ ]  | [x]   | [ ]  | cold         | 2026-02-13 | 82         | 99       | 3       | .91    | 290   | [Architecture/Flow_execution_edge_callbacks/CALLBACK_QUICK_REFERENCE.md](../internals/Architecture/Flow_execution_edge_callbacks/CALLBACK_QUICK_REFERENCE.md)       |
| [ ]  | [x]   | [ ]  | cold         | 2026-02-13 | 82         | 99       | 3       | .91    | 459   | [Architecture/Flow_execution_edge_callbacks/callbacks_between_two_flows.md](../internals/Architecture/Flow_execution_edge_callbacks/callbacks_between_two_flows.md) |
| [ ]  | [x]   | [ ]  | cold         | 2026-02-13 | 82         | 104      | 2       | .58    | 441   | [Architecture/assemblyAndEvaluation/FirstSketch.md](../internals/Architecture/assemblyAndEvaluation/FirstSketch.md)                                                 |
| [ ]  | [x]   | [ ]  | cold         | 2026-02-13 | 82         | 104      | 2       | .58    | 456   | [Architecture/assemblyAndEvaluation/IMPLEMENTATION_README.md](../internals/Architecture/assemblyAndEvaluation/IMPLEMENTATION_README.md)                             |
| [ ]  | [x]   | [ ]  | cold         | 2026-02-13 | 82         | 104      | 2       | .58    | 350   | [Architecture/assemblyAndEvaluation/IMPLEMENTATION_SUMMARY.md](../internals/Architecture/assemblyAndEvaluation/IMPLEMENTATION_SUMMARY.md)                           |
| [x]  | [ ]   | [ ]  | cold         | 2026-02-13 | 82         | 82       | 2       | .73    | 98    | [diagrams.md](../internals/diagrams.md) THIS DOCUMENT SHOWS NICE DIAGRAMS - DESIGN REFERENCE ONLY!!                                                                 |
| [ ]  | [x]   | [ ]  | cold         | 2026-02-13 | 82         | 99       | 3       | .92    | 202   | [documentation/Assembly_Execution_System.md](../internals/documentation/Assembly_Execution_System.md)                                                               |
| [ ]  | [ ]   | [x]  | cold         | 2026-02-13 | 82         | 267      | 2       | .22    | 628   | [documentation/architecture/Undo:Redo_System_architecture_sketch.md](../internals/documentation/architecture/Undo:Redo_System_architecture_sketch.md)               |
| [ ]  | [ ]   | [x]  | cold         | 2026-02-13 | 82         | 278      | 3       | .32    | 326   | [documentation/widgets/Haywire_datatypes.md](../internals/documentation/widgets/Haywire_datatypes.md)                                                               |
| [ ]  | [ ]   | [x]  | cold         | 2026-02-13 | 82         | 158      | 2       | .38    | 336   | [documentation/widgets/architecture.md](../internals/documentation/widgets/architecture.md)                                                                         |
| [ ]  | [ ]   | [x]  | cold         | 2026-02-14 | 82         | 82       | 2       | .73    | 34    | [testing.md](../internals/testing.md)                                                                                                                               |
| [ ]  | [ ]   | [x]  | touched-once | 2026-05-06 | 0          | 0        | 1       | 2.00   | 580   | [prd/v1.2-edit-state-migration.md](../internals/prd/v1.2-edit-state-migration.md)                                                                                   |
| [ ]  | [ ]   | [x]  | touched-once | 2026-05-06 | 1          | 1        | 1       | 2.00   | 2347  | [superpowers/plans/2026-05-06-library-state-v1.md](../internals/superpowers/plans/2026-05-06-library-state-v1.md)                                                   |
| [ ]  | [ ]   | [x]  | touched-once | 2026-05-06 | 1          | 1        | 1       | 2.00   | 2398  | [superpowers/plans/2026-05-06-session-state-v1.md](../internals/superpowers/plans/2026-05-06-session-state-v1.md)                                                   |
| [x]  | [ ]   | [ ]  | touched-once | 2026-05-03 | 4          | 4        | 1       | 2.00   | 756   | [speculative/spec_panel_reactivity.md](../internals/speculative/spec_panel_reactivity.md)                                                                           |
| [ ]  | [ ]   | [x]  | touched-once | 2026-04-26 | 11         | 11       | 1       | 2.00   | 1691  | [superpowers/plans/2026-04-25-close-consent-and-event-cleanup.md](../internals/superpowers/plans/2026-04-25-close-consent-and-event-cleanup.md)                     |
| [ ]  | [ ]   | [x]  | touched-once | 2026-04-26 | 11         | 11       | 1       | 2.00   | 2382  | [superpowers/plans/2026-04-25-editor-wrapper-refactor.md](../internals/superpowers/plans/2026-04-25-editor-wrapper-refactor.md)                                     |
| [ ]  | [ ]   | [x]  | touched-once | 2026-04-24 | 12         | 12       | 1       | 2.00   | 1206  | [superpowers/plans/2026-04-24-workspace-manager-simplification.md](../internals/superpowers/plans/2026-04-24-workspace-manager-simplification.md)                   |
| [ ]  | [ ]   | [x]  | touched-once | 2026-04-24 | 13         | 13       | 1       | 2.00   | 2798  | [superpowers/plans/2026-04-23-slot-hierarchy-refactor.md](../internals/superpowers/plans/2026-04-23-slot-hierarchy-refactor.md)                                     |
| [ ]  | [ ]   | [x]  | touched-once | 2026-04-23 | 14         | 14       | 1       | 2.00   | 1591  | [superpowers/plans/2026-04-22-on-focus-hook.md](../internals/superpowers/plans/2026-04-22-on-focus-hook.md)                                                         |
| [ ]  | [ ]   | [x]  | touched-once | 2026-04-22 | 15         | 15       | 1       | 2.00   | 1536  | [superpowers/plans/2026-04-15-cross-session-event-channel.md](../internals/superpowers/plans/2026-04-15-cross-session-event-channel.md)                             |
| [ ]  | [ ]   | [x]  | touched-once | 2026-04-22 | 15         | 15       | 1       | 2.00   | 1723  | [superpowers/plans/2026-04-15-haystack-entry-ownership.md](../internals/superpowers/plans/2026-04-15-haystack-entry-ownership.md)                                   |
| [ ]  | [ ]   | [x]  | touched-once | 2026-04-22 | 15         | 15       | 1       | 2.00   | 2045  | [superpowers/plans/2026-04-21-editor-opens-behavior.md](../internals/superpowers/plans/2026-04-21-editor-opens-behavior.md)                                         |
| [ ]  | [ ]   | [x]  | touched-once | 2026-04-22 | 15         | 15       | 1       | 2.00   | 285   | [superpowers/specs/2026-04-15-cross-session-event-channel-design.md](../internals/superpowers/specs/2026-04-15-cross-session-event-channel-design.md)               |
| [ ]  | [ ]   | [x]  | touched-once | 2026-04-22 | 15         | 15       | 1       | 2.00   | 443   | [superpowers/specs/2026-04-15-haystack-entry-ownership-design.md](../internals/superpowers/specs/2026-04-15-haystack-entry-ownership-design.md)                     |
| [ ]  | [ ]   | [x]  | touched-once | 2026-02-13 | 82         | 82       | 1       | .36    | 6     | [functionality.md](../internals/functionality.md)                                                                                                                   |
| [ ]  | [ ]   | [x]  | touched-once | 2025-07-27 | 284        | 284      | 1       | .10    | 163   | [whitepaper/Impl_ComfyUI.md](../internals/whitepaper/Impl_ComfyUI.md)                                                                                               |
| [ ]  | [ ]   | [x]  | touched-once | 2025-07-26 | 284        | 284      | 1       | .10    | 267   | [whitepaper/research/comfyui_node_lifecycle.md](../internals/whitepaper/research/comfyui_node_lifecycle.md)                                                         |


## Reading the data

**On its own, this report cannot tell you accuracy.** A `stale` doc may still be 100 % correct if the system it describes hasn't changed; an `active` doc may still describe an outdated implementation if the recent edits were cosmetic. Use this as the *prioritisation layer* — pick which docs deserve the more expensive accuracy check, and skip the obvious cases (e.g. `internals/superpowers/plans/*` are by definition historical artefacts).

Suggested triage:

- **active / mature** → likely current; quick spot-check, then map to new structure.
- **cold / stale with high commit count** → was once cared about; worth an accuracy check before deciding.
- **cold / stale with 1–2 commits** → low ROI; consider archive unless title clearly maps to a needed story.
- **touched-once** → almost always speculative or one-shot. Default to `internals/archive/` unless a survey says otherwise.
- **rename-only** (none expected, listed for completeness) — newly authored without prior history.

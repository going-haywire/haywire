# Haywire Documentation — Structure Plan

This document describes the planned layout of `docs/`. It is the agreed
output of a structured design interview. Once the migration is complete,
this file becomes the contributor guide for adding/editing docs.

Status: **plan, not yet implemented.** All current documentation has been
moved to `internals/` and `docs/` is pristine apart from this file.

---

## 1. Goals

- Replace today's two parallel doc trees (`internals/Architecture/` and
  `internals/documentation/architecture/`, plus `whitepaper/`, `speculative/`,
  `superpowers/`, `prd/`) with a single coherent structure.
- Organise content by **perspective**: node-author, advanced
  (workbench-extension) developer, core/system architect.
- Use **stories** (folders of chapters) as the unit of explanation.
- Be **open for growth** — add new architecture concepts without
  restructuring the whole tree.
- **Audit before move.** Triage every existing doc as
  current / outdated-fixable / obsolete / historical, then carry only
  survivors forward. Outdated docs get fixed or deleted.

## 2. Toolchain

- **MkDocs + Material theme** today. Docs are written for it now.
- **Zensical-ready tomorrow.** Zensical advertises MkDocs compatibility;
  when it stabilises, the build tool can swap with minimal content
  churn. Don't adopt it now — it's at v0.0.40.
- `mkdocs.yml` lives at repo root. `docs_dir: internals/`.

## 3. Top-level layout

```
haywire-repo/
  docs/                     ← published documentation (MkDocs source)
  internals/                ← working & internal artefacts; not published
    archive/                ← internal historical noise
    prd/                    ← product requirements
    speculative/            ← in-progress design exploration
    superpowers/            ← plans & specs
    Architecture/           ← (legacy, will be drained as part of audit)
    documentation/          ← (legacy, will be drained as part of audit)
  mkdocs.yml
```

Rule: `docs/` is the public face. `internals/` is the workshop.
PRDs, plans, archives, and superseded specs do **not** live in `docs/`.

## 4. `docs/` layout

```
docs/
  index.md                              ← landing page; "Pick a perspective."
  STRUCTURE.md                          ← this file (becomes contributor guide)

  welcome/                              ← per-perspective entry points
    user/index.md                       ← curated reading order for node authors
    advanced/index.md                   ← curated reading order for workbench extenders
    core/index.md                       ← curated reading order for system architects

  components/                           ← extension points: things authored against haywire
    nodes/                              ← node classes, lifecycle, worker function
    datatypes/                          ← IType subclasses, type registry
    ports/                              ← port flags, pin configurations, dynamic ports
    adapters/                           ← type-pair adapters, adapter registry
    settings/                           ← @setting on nodes / libraries / framework
    widgets/                            ← UI widgets bound to types
    skins/                              ← node skins (visual variants)
    themes/                             ← WorkbenchTheme & NodeTheme authoring
    editors/                            ← editor classes plugged into the workspace
    panels/                             ← panel classes used inside editors/canvas
    states/                             ← @state decorator: app/session-lifecycle state
                                          owned by editors/panels for metadata throughout
                                          the lifecycle of the app and its browser sessions
    libraries/                          ← BaseLibrary, @library, register_components()
    haybale-package/                    ← packaging a Haybale: pyproject entry_points, layout

  architecture/                         ← system internals: how the framework is built
    overview/                           ← short end-to-end tour with links into folders
    design/                             ← UI design guide, naming, hui rules

    graph/                              ← the Graph as data structure
      01-overview.md
      02-variables.md
      03-validation-pipeline.md
      04-graph-nodes-subgraphs-abstractions-modules.md
      05-haystacks.md
      06-serialization.md               ← JSON load/save, recipe format, version migration

    execution/                          ← how a Graph becomes runtime behaviour
      assembly/                         ← graph→flow pipeline
      edges/                            ← edge wrapper, adapter chains, hooks vs pipes
      flow/                             ← Flow as runtime structure, control vs data
      virtual-machine/                  ← VM, stacks, execution context, pause/resume
      lazy-evaluation/                  ← EVAL_MASK / LAZY_MASK algorithm
      callbacks/                        ← callback system, cross-flow triggers

    library-system/                     ← LibraryRegistry, LibraryDiscovery, LibraryIdentity
    library-manager/                    ← studio's package-manager UI internals
    hot-reload/                         ← cross-cutting reload mechanics
    settings/                           ← resolution chain, registries, three-tier model
    session-and-state/                  ← session lifecycle, undo/redo, persistence
    studio/                             ← the studio as a product
      01-overview.md                    ← AppShell + Workspace + Sessions + canvas
      app-shell/                        ← top chrome, menus, command palette
      workspace/                        ← Sessions, multi-editor, layout
      canvas/                           ← graph canvas, minimap, zoom/pan
      rendering/                        ← NiceGUI integration, hui, slot stacks

  reference/                            ← shared truth layer
    index.md
    glossary.md                         ← from internals/UBIQUITOUS_LANGUAGE.md
    design-guide.md                     ← from haywire-ui-design-guide.md
    api/                                ← future: mkdocstrings auto-generated

  archive/                              ← foundational, citable historical material
    whitepaper/                         ← the original Haywire_design.md spec
```

## 5. Perspective → folder routing

Perspectives are **navigational**, not structural. Each perspective's
`index.md` curates a reading order through `components/` and
`architecture/`. The same folder can appear in multiple perspectives'
reading orders.

| Perspective | Primary folders | Secondary folders |
|---|---|---|
| **User** (node author) | `components/{nodes,datatypes,ports,adapters,settings,widgets}` | `components/libraries` (consuming), `reference/glossary` |
| **Advanced** (workbench extender) | `components/{editors,panels,themes,skins,states,libraries,haybale-package}` | `architecture/studio/`, `reference/design-guide` |
| **Core** (system architect) | `architecture/*` (all) | `components/*` for context |

## 6. Story format

A **story** is a folder. Inside:

- `01-overview.md` — what the system is, why it exists
- `02-…md`, `03-…md`, … — chapters in reading order
- final chapter is usually `NN-reference.md` for API/mechanics

Single-page topics use a folder with one `01-overview.md`. The folder
gives every story the same shape and a stable URL.

## 7. Disambiguating "Library"

The word "library" overlaps five distinct concepts in haywire. Each has
its own home in this structure.

| # | Term | What it is | Home |
|---|---|---|---|
| 1 | **Library** (`BaseLibrary`, `@library`) | The plugin protocol class authored by a developer | `components/libraries/` |
| 2 | **Library System** | Framework infrastructure: `LibraryRegistry`, `LibraryDiscovery`, `LibraryIdentity`, `FileWatcher` | `architecture/library-system/` |
| 3 | **Haybale package** | Distribution unit: a Python package containing a `BaseLibrary` subclass | `components/haybale-package/` |
| 4 | **Library Manager** | Studio's in-app package-manager UI | `architecture/library-manager/` |
| 5 | **LibrarySettings / LibraryState** | Per-library scope for cross-cutting subsystems | Chapter inside `components/settings/` and `components/states/` |

This table is mirrored in `reference/glossary.md`. The terms
"Library System" and "Library Manager" are deliberately built by
adjective on top of "Library" so they stay aligned with the existing
codebase term `haywire.core.library`.

## 8. Settings — three tiers

The settings story has three audiences corresponding to the three
implemented classes. Both the node-design tier and the library-app-state
tier are component-author concerns; framework settings are
architecture-only:

- **NodeSettings** — declared on a node. → `components/settings/`
- **LibrarySettings** — declared on a library; powers app-state and
  cross-node defaults. → `components/settings/` (chapter)
- **FrameworkSettings** — used solely for framework classes; resolution
  chain mechanics. → `architecture/settings/`

## 9. State

`components/states/` documents the `@state` decorator and the
`LibraryStateContainer` model — specifically, app/session-lifecycle
state owned by editors and panels for metadata throughout the lifecycle
of the app and its browser sessions.

It is *not* the home for:

- **Graph Variables** — graph-scoped state in worker functions →
  `architecture/graph/02-variables.md`
- **Session UI state, undo/redo** → `architecture/session-and-state/`

## 10. Adapters

Adapters are authored component classes with their own registry. They
are assembled into adapter chains when edges are created.

- Authoring → `components/adapters/`
- Runtime mechanics (chain construction, sample-data testing) →
  `architecture/execution/edges/`

## 11. Archive policy

Two archive locations, with a clear rule:

- **`docs/archive/`** — foundational, citable historical artefacts
  (notably `Haywire_design.md`, the original whitepaper). Published.
- **`internals/archive/`** — superseded internal designs, old specs,
  deleted-but-historical plans (`speculative/archive/`,
  `Architecture/history/`, retired PRDs). Not published.

## 12. Migration strategy

1. **Audit** every file in `internals/` (the legacy `docs/`):
   classify as current / outdated-fixable / obsolete / historical.
2. **Move foundational artefacts** to `docs/archive/`.
3. **Move historical noise** to `internals/archive/`.
4. **For each surviving doc**, identify its destination folder in this
   plan. Multiple docs may merge into one story; long docs may split
   across chapters.
5. **Write missing stories.** Major gaps identified during the
   interview:
   - `architecture/graph/` — Graph as a first-class concept
   - `architecture/execution/{virtual-machine,lazy-evaluation,callbacks}/`
   - `architecture/studio/` — studio as a product
   - `components/states/` — `@state` decorator and friends
   - `components/haybale-package/` — packaging story
   - `architecture/library-manager/` — studio package-manager UI
6. **Build `mkdocs.yml`** referencing the new paths.
7. **Drop `internals/Architecture/` and `internals/documentation/`** once
   drained.

## 13. Out of scope for this plan

- Writing the actual content of any folder. This plan is layout only.
- Choosing specific Material-theme features, plugins, or themes.
- Auto-generating API reference (mkdocstrings) — `reference/api/` is
  reserved as a future home but not built now.
- Versioning the docs site (mike, etc.) — defer until v1.0.

## 14. Decision log

Numbered Q's reference the structured interview that produced this plan.

- **Q1**: audit-first, then triage; obsolete content does not survive.
- **Q2**: hybrid — perspectives are entry points; `reference/` holds
  shared truth.
- **Q3**: perspective-first top-level layout (refined in Q8).
- **Q4**: MkDocs + Material now, Zensical-ready later.
- **Q5**: `docs/` (public) and `internals/` (working) are separate
  top-level dirs.
- **Q6**: stories are folders with chapters by default.
- **Q7**: inventory derived from existing docs + design-doc concepts.
- **Q8**: flat `components/` and flat `architecture/`; perspective
  handled via `welcome/<perspective>/index.md`.
- **Q9**: `architecture/graph/` is its own dedicated story; Haystacks
  live there.
- **Q10**: six subfolders under `architecture/execution/`.
- **Q11**: `Haywire_design.md` is preserved as the original whitepaper.
- **Q12**: two archive locations: `docs/archive/` (foundational) and
  `internals/archive/` (historical noise).
- **Q13**: `components/states/` documents `@state` for editors/panels
  managing app & session lifecycle metadata; graph variables and
  session UI state live in architecture.
- **Q14**: hot-reload is its own top-level architecture folder.
- **Q15**: rename to disambiguate "library" — Library / Library System
  / Haybale package / Library Manager / LibrarySettings+LibraryState.
- **Q16**: studio-as-product gets `architecture/studio/` as umbrella.
- **Q17**: settings split by audience; adapters live in components,
  with runtime mechanics covered under `architecture/execution/edges/`.
- **Q18**: this file (single STRUCTURE.md plan) — scaffolding stubs and
  `mkdocs.yml` happen in a later pass.

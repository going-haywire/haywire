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

Each component/architecture folder contains one `<area>-canon.md` or
`<area>-arch.md` file (see §6). Folder name and filename mirror each
other so the URL is `…/components/nodes/node-canon` etc.

```text
docs/
  index.md                              ← landing page; "Pick a perspective."
  STRUCTURE.md                          ← this file (contributor guide)
  audit-internals.md                    ← heuristic triage of legacy docs
  audit-survivors.md                    ← survivors with content-type tags

  welcome/                              ← per-perspective entry points
    user/index.md                       ← reading order for node authors
    advanced/index.md                   ← reading order for workbench extenders
    core/index.md                       ← reading order for system architects

  components/                           ← extension points
    nodes/node-canon.md
    datatypes/datatype-canon.md
    ports/port-canon.md
    adapters/adapter-canon.md
    settings/setting-canon.md
    widgets/widget-canon.md
    skins/skin-canon.md
    themes/theme-canon.md
    editors/editor-canon.md
    panels/panel-canon.md
    states/state-canon.md               ← @state decorator: app/session-lifecycle state
                                          owned by editors/panels for metadata throughout
                                          the lifecycle of the app and its browser sessions
    libraries/library-canon.md
    haybale-package/haybale-package-canon.md

  architecture/                         ← system internals
    overview/overview-arch.md           ← end-to-end tour (system-reference)
    design/design-arch.md               ← UI design guide, naming, hui rules

    graph/graph-arch.md                 ← Graph as data structure (impl-spec)

    execution/                          ← how a Graph becomes runtime behaviour
      execution-arch.md                 ← umbrella (system-reference)
      assembly/assembly-arch.md         ← graph→flow pipeline
      edges/edges-arch.md               ← edge wrapper, adapter chains, hooks vs pipes
      flow/flow-arch.md                 ← control flow vs localized data flow
      virtual-machine/virtual-machine-arch.md
      lazy-evaluation/lazy-evaluation-arch.md
      callbacks/callbacks-arch.md

    library-system/library-system-arch.md     ← runtime infrastructure
    library-manager/library-manager-arch.md   ← studio's package-manager UI
    hot-reload/hot-reload-arch.md             ← cross-cutting reload mechanics
    settings/settings-arch.md                 ← resolution chain, three-tier model
    session-and-state/session-and-state-arch.md

    studio/                             ← the studio as a product
      studio-arch.md                    ← umbrella (system-reference)
      app-shell/app-shell-arch.md
      workspace/workspace-arch.md
      canvas/canvas-arch.md
      rendering/rendering-arch.md

  reference/                            ← shared truth layer
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

A **story** is a folder containing **one canonical file**. The filename
is `<area>-canon.md` for `components/` and `<area>-arch.md` for
`architecture/`. The folder gives every story a stable URL; the single
file inside it carries all the content.

Rationale: the codebase is moving fast and the dominant reader is an
LLM. One example per concept = one update per API change. Multiple
chapters or multiple examples multiply maintenance work.

If a story grows too large for one file, split into chapters
(`01-…md`, `02-…md`) inside the same folder — but only when the file
genuinely cannot stay readable as one piece.

### 6.1 Three templates

Every canon/arch file declares its template in YAML frontmatter. There
are three:

**`canonical-example`** (used by every `components/<area>/<area>-canon.md`)

```text
1. What it solves      — capability statement, one paragraph
2. How it fits         — dependencies, where this sits in the system
3. Important concepts  — named entities and rules an author needs
4. One comprehensive   — a single worked example exercising every
   example                concept above
```

**`impl-spec`** (used by single-subsystem architecture folders;
proven shape from `library_state.md`)

```text
1. Mental model        — what this subsystem is, one paragraph
2. Contract            — declaration / registration / access / invariants
3. Lifecycle           — creation, hot-reload, ordering, observability
4. Boundary            — what this is NOT for
5. Examples            — concrete worked cases
6. Open questions      — what remains undecided
```

**`system-reference`** (used by multi-component umbrella folders;
proven shape from `Library_System_Technical_Reference.md`)

```text
1. Overview            — what the system is
2. Components          — numbered subsystems with file/class refs
3. Data flow           — end-to-end sequences across components
4. Performance / errors / boundaries — operational concerns
```

Picking rule: a folder describing **one bounded subsystem with a
mental model and a contract** uses `impl-spec`. A folder describing
**a multi-component system or umbrella** uses `system-reference`. When
in doubt, default to `impl-spec`.

### 6.2 Frontmatter

Every canon/arch file has YAML frontmatter:

```yaml
---
status: placeholder | draft | current
template: canonical-example | impl-spec | system-reference
scope: <one-line scope statement>
see-also:
  - <relative path to source material in internals/>
---
```

`status: placeholder` means the file has only the template stub.
`status: draft` means content has been written but not verified
against the codebase. `status: current` means the content has been
verified.

Search for `status: placeholder` to find the work list.

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

One archive location:

- **`docs/archive/`** — foundational, citable historical artefacts.
  Currently holds the original whitepaper (`Haywire_design.md` and
  its `HayWire_Diagram.drawio` source). Published.

Internal-historical material (dropped audits, superseded specs,
retired plans) was deleted on disk after migration completed. The full
history is preserved in git — `git log --follow <docs-file>` traces
back through the renames into the original sources. Use git instead
of an on-disk archive; the canon/arch docs in `docs/` are the truth.

## 12. Migration strategy

The migration ran in three phases. **All three are now complete.**
Remaining work is content authoring for the placeholder files —
tracked as `status: placeholder` in frontmatter and surfaced in the
TOC.

### Phase 0 — Audit and scaffold (DONE)

- Heuristic audit of every file in `internals/`. Results in
  [`audit-internals.md`](audit-internals.md) (triage: good / check /
  drop) and [`audit-survivors.md`](audit-survivors.md) (47 survivors
  with content-type categorisation).
- Every folder in §4 was scaffolded with one placeholder file
  (`<area>-canon.md` or `<area>-arch.md`) using the §6 templates and
  §6.2 frontmatter.

### Phase 1 — Migrate (DONE — 47 of 47 survivors)

All 47 surviving source files have been migrated. The full triage with
destination links and verification findings is recorded in
[`audit-survivors.md`](audit-survivors.md) — every row marked
**✅ DONE**.

Migration outcome — 23 canon/arch files filled with verified content
(`status: draft`):

- **Components**: nodes, datatypes, ports, adapters, settings, widgets,
  themes, editors, panels, states, libraries, haybale-package
- **Architecture**: library-system, library-manager, hot-reload,
  settings, session-and-state, studio (umbrella), execution/edges,
  execution/assembly, execution/callbacks
- **Reference**: glossary, design-guide

Verification findings (codebase as ground truth) recorded in
`audit-survivors.md` notes column.

### Phase 2 — Cleanup (DONE)

- All 75 source files migrated to canonical destinations and then
  deleted from disk. Git tracks them as `RD` (renamed-then-deleted),
  preserving full history — `git log --follow <docs-file>` traces back
  through the original sources.
- The `internals/` top-level directory was removed entirely.
- The whitepaper (`Haywire_design.md` + `HayWire_Diagram.drawio`) is
  preserved in `docs/archive/whitepaper/` as a citable foundational
  artefact (per §11).
- `mkdocs.yml` written at repo root with the perspective-organised
  navigation per §5.

### Remaining placeholders (TODO list — 16 files)

Visible by `grep -rl 'status: placeholder' docs/`:

- `architecture/overview/`, `architecture/design/`, `architecture/graph/`
- `architecture/execution/{execution,flow,virtual-machine,lazy-evaluation}/`
- `architecture/studio/{app-shell,workspace,canvas,rendering}/`
- `components/skins/`
- `welcome/{user,advanced,core}/index.md`

Source material for these placeholders is preserved in git history.
Use `git log --follow <placeholder>` to find the renamed-and-deleted
sources that informed the see-also links. Notably, the original
1757-line `haywire-ui-architecture-spec_details.md` (cited from the
four `studio/` sub-folder placeholders) is recoverable via git; pick
the file's last-content commit before the bulk rename to read it in
context.

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
  `internals/archive/` (historical noise). *(Superseded after migration:
  `internals/archive/` was deleted; git history serves as the
  historical archive — see §11 / §12 phase 2.)*
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
- **Q19**: components folders are authors-guide territory; short
  recipes and tutorials live as chapters *inside* the canon file, not
  as separate folder types.
- **Q20**: components canonical-example template adopted: 4 parts
  (what it solves / how it fits / important concepts / one example).
  One file per component for maintenance economy under a moving
  codebase and an LLM-dominant audience.
- **Q21**: architecture has two templates — `impl-spec` for single
  bounded subsystems, `system-reference` for multi-component umbrellas.
  Picked per folder; both proven in the existing corpus.
- **Q22**: every folder gets scaffolded with a placeholder canon/arch
  file now; placeholders stay visible in the TOC as the TODO list.
- **Q23**: filename conventions — `<area>-canon.md` for components,
  `<area>-arch.md` for architecture (template declared in
  frontmatter). Source archive was `internals/archive/`; foundational
  artefacts go to `docs/archive/`. *(Superseded after migration:
  `internals/archive/` was deleted — see §11.)*

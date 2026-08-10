# Module: Docs

> mkdocs-material documentation site for Haywire: extension-point authoring guides, framework internals, reference glossary, and a UI design guide.

**Path:** `docs/`
**Language:** Markdown (mkdocs-material)
**Owner:** All teams (each owns docs near their module)
**Tree hash:** `6bd22598222b26ed28aaff7df7d4a09d0e594201`
**Mapped at:** 19bda1e (2026-07-05)

---

## 1. Scope & Purpose

Per `CLAUDE.md`, **`docs/` is the first place to look up how a system works** — before reading source code. The site is published with `uv run mkdocs serve` (default `http://127.0.0.1:8000`). Layout follows a strict three-shelf model: components (authoring guides), architecture (internals), and reference (glossary + design guide).

## 2. Folder Architecture

```
docs/
├── index.md               ← site landing page
├── welcome/               ← onboarding
├── adr/                   ← Architecture Decision Records (0001–0014, 0017 — see note)
│   ├── 0009-focus-id-stable-key.md
│   ├── 0010-event-source-queue-mode.md (new — per-EVENT-node queue_mode, DROP vs BLOCK)
│   ├── 0011-collapse-settings-tiers.md (new — P2: highest-priority-set-wins, drops OVERRIDE)
│   ├── 0012-settings-json-persistence.md (new — P3: TOML→JSON, IType to_dict/from_dict at disk edge)
│   ├── 0013-settings-single-cell.md (new — P4: setting value lives in a DataField cell; carries
│   │                                   the former ADR 0016 as an inline "Amendment" section)
│   ├── 0014-promotion-as-direction.md (new — P5: promoted port = setting's cell by reference;
│   │                                   carries the former ADR 0015 as an inline "Amendment" section)
│   └── 0017-widget-selection-port-contract.md (new — widget_key/widget_config stamped once;
│                                       0015/0016 numbers retired, not reused — gap is intentional)
├── architecture/          ← framework internals
│   ├── settings/settings-arch.md (majorly rewritten — single-cell model §6.4, promotion §6.5,
│   │                               stamped widget contract §6.6; ~2.7x longer)
│   └── <area>/<area>-arch.md
├── components/            ← extension-point authoring guides
│   ├── settings/setting-canon.md (majorly rewritten alongside the ADR arc above)
│   └── <area>-canon.md files
├── haybale/               ← library/package authoring + marketplace docs
│   ├── haybale-canon.md   (authoring + packaging, merged)
│   ├── metadata-flow.md   (haybale.toml → pyproject → marketstall → cache)
│   └── marketplace/
├── guides/                ← how-tos (e.g., sharing-libraries.md)
├── plans/                 ← implementation plans (distinct from docs/superpowers/plans/ below)
├── reference/             ← glossary + design guide + dependency report
│   ├── glossary.md (updated — Promotion, CHOICES, widget key entries rewritten for ADR 0013/0014/0017)
│   ├── files/             ← one page per TOML format (haybale, pyproject, marketstall, marketplace)
│   ├── dependency-report.md (updated — haybale-visiongraph false-positive re-audit note)
│   └── design-guide.md
├── superpowers/plans/     ← dated implementation-plan writeups; pruned once landed
│                            (two 2026-06 plans removed post-merge in this window)
└── archive/               ← retired pages
```

## 3. Always-load vs On-demand

### Always-load (when researching a topic)

- `docs/reference/glossary.md` — canonical vocabulary; resolve term ambiguity here first.
- `docs/index.md` + `docs/welcome/` — site map and onboarding.

### On-demand (by task)

- Authoring nodes/types/ports/themes/editors/panels → the matching `docs/components/<area>/<area>-canon.md`.
- **Authoring widgets** → `docs/components/widgets/widget-canon.md` (covers BaseWidget unification, ADR 0007).
- Widget rendering in ports panel → ADR 0008 + `haybale_graph_editor.panels.node_ports_panel`.
- Authoring a library / haybale package → `docs/haybale/haybale-canon.md` (one page; the two old canons merged).
- What a field in any TOML file means → `docs/reference/files/<file>-toml.md`. Defined once there; every other doc links.
- Marketplace behaviour → `docs/haybale/marketplace/`.
- Understanding execution/library/settings/session internals → `docs/architecture/`.
- Show vs hide widget logic → ADR 0003.
- Why focus routing keys on `Focus.id` (not the class) → ADR 0009 + `haywire.ui.panel.focus`.
- Node compatibility warnings → ADR 0005 + `haywire.core.node.node_warning`.
- Realtime frame-dropping / queue mode → ADR 0010 + `haywire.core.execution.event_source`.
- **Settings system internals (resolution, storage, promotion)** → `docs/architecture/settings/settings-arch.md` is the single always-current internals doc; read it before the ADRs below unless you need the historical "why." The settings↔DataField unification arc, in order: ADR 0011 (tier collapse, drop OVERRIDE) → ADR 0012 (JSON persistence, IType disk-edge serialization) → ADR 0013 (single-cell value model; **includes a merged-in amendment, formerly ADR 0016**, on cell-authoritative reads/registry-owned cells) → ADR 0014 (promotion-as-direction, one cell/two views; **includes a merged-in amendment, formerly ADR 0015**, on the storage-key-as-port-id mechanism). ADR numbers 0015 and 0016 no longer exist as standalone files — do not look for them; their content lives inline in 0013/0014 as "Amendment" sections.
- Authoring settings on a node/library → `docs/components/settings/setting-canon.md`.
- Widget selection for a setting/port field (`widget_key`/`widget_config`, `choices=` removal) → ADR 0017.
- Graph canvas selection behaviour → `docs/plans/` or the code in `haybale_graph_editor`.
- Building UI → `docs/reference/design-guide.md` is non-optional.

## 4. Rules & Boundaries

- **Look here before reading source code** when answering "how does X work?".
- Components canon files cover authoring; architecture files cover internals — don't merge the two.
- "Library" has five distinct meanings; `glossary.md` is authoritative.
- New UI features must follow `design-guide.md`.
- Site is built with `mkdocs.yml` at repo root.
- **ADRs are append-only, but content can be merged as an amendment into an existing ADR when a follow-up refines rather than replaces it** — an amended ADR keeps its original number and gains a trailing `## Amendment — ...` section; the retired number is never reused. Precedent: ADR 0015 → merged into 0014; ADR 0016 → merged into 0013 (commit `b07aca75`). When citing settings behaviour, cite 0013/0014 — not 0015/0016.
- `docs/superpowers/plans/` holds dated one-off implementation-plan writeups; expect files here to be pruned once the plan has landed and its substance is captured in an ADR or canon/arch doc (don't treat their absence as a doc gap — check the ADRs first).

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Glossary | `docs/reference/glossary.md` | Includes 5 meanings of "library" |
| UI design rules | `docs/reference/design-guide.md` | Tokens + anti-patterns |
| mkdocs config | repo-root `mkdocs.yml` | Nav, theme, plugins |
| Settings resolution/storage internals | `docs/architecture/settings/settings-arch.md` | Current-state doc; §6.4–§6.6 cover single-cell, promotion, widget contract |
| Settings↔DataField unification history | `docs/adr/0011` – `0014`, `0017` | 0015/0016 retired-by-merge into 0014/0013 |
| Settings authoring | `docs/components/settings/setting-canon.md` | `setting()`/`shadow()`/`watch()`, promotion, widgets |

---

## Dependencies

### Depends on

- The code it documents (drifts when code changes — there is a separate `refreshing-docs` workflow).

### Depended on by

- Skills (`haywire-exec`, `haywire-libs`, `haywire-settings`, `haywire-ui`, etc.) load slices of these docs.
- Humans onboarding to the project.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Local site | `mkdocs.yml` | `uv run mkdocs serve` → `http://127.0.0.1:8000` |
| Site landing | `docs/index.md` | Top of nav |
| Glossary | `docs/reference/glossary.md` | First stop for terminology |

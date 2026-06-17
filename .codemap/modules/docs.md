# Module: Docs

> mkdocs-material documentation site for Haywire: extension-point authoring guides, framework internals, reference glossary, and a UI design guide.

**Path:** `docs/`
**Language:** Markdown (mkdocs-material)
**Owner:** All teams (each owns docs near their module)
**Tree hash:** `4191941554dd8e97fd63298e43e1f51babf7091a`
**Mapped at:** 51d1ac64 (2026-06-17)

---

## 1. Scope & Purpose

Per `CLAUDE.md`, **`docs/` is the first place to look up how a system works** — before reading source code. The site is published with `uv run mkdocs serve` (default `http://127.0.0.1:8000`). Layout follows a strict three-shelf model: components (authoring guides), architecture (internals), and reference (glossary + design guide).

## 2. Folder Architecture

```
docs/
├── index.md               ← site landing page
├── welcome/               ← onboarding
├── adr/                   ← Architecture Decision Records (0001–0009)
│   ├── 0003-show-widget-strategy.md
│   ├── 0004-semantic-slot-names.md
│   ├── 0005-compatibility-warnings.md
│   ├── 0006-node-render-performance.md
│   ├── 0007-widget-unification-basewidget.md
│   ├── 0008-ports-panel-widget-rendering.md
│   └── 0009-focus-id-stable-key.md (new)
├── architecture/          ← framework internals
│   └── <area>/<area>-arch.md
├── components/            ← extension-point authoring guides
│   ├── widgets/widget-canon.md (majorly rewritten for widget unification)
│   ├── panels/
│   │   └── panel-canon.md (updated — host rendering, redraw coordination patterns)
│   ├── states/
│   │   └── state-canon.md (new — state container & FocusId patterns)
│   ├── editors/editor-canon.md
│   └── <area>-canon.md files
├── haybale/               ← library/package authoring + marketplace docs
│   ├── library-canon.md (new)
│   ├── haybale-package-canon.md
│   └── marketplace/
├── guides/                ← how-tos (e.g., sharing-libraries.md)
├── plans/                 ← implementation plans (new in v0.0.19 docs)
├── reference/             ← glossary + design guide
│   ├── glossary.md (updated)
│   └── design-guide.md (expanded)
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
- Authoring a library / haybale package → `docs/haybale/` (library-canon.md, haybale-package-canon.md).
- Marketplace behaviour → `docs/haybale/marketplace/`.
- Understanding execution/library/settings/session internals → `docs/architecture/`.
- Show vs hide widget logic → ADR 0003.
- Why focus routing keys on `Focus.id` (not the class) → ADR 0009 + `haywire.ui.panel.focus`.
- Node compatibility warnings → ADR 0005 + `haywire.core.node.node_warning`.
- Graph canvas selection behaviour → `docs/plans/` or the code in `haybale_graph_editor`.
- Building UI → `docs/reference/design-guide.md` is non-optional.

## 4. Rules & Boundaries

- **Look here before reading source code** when answering "how does X work?".
- Components canon files cover authoring; architecture files cover internals — don't merge the two.
- "Library" has five distinct meanings; `glossary.md` is authoritative.
- New UI features must follow `design-guide.md`.
- Site is built with `mkdocs.yml` at repo root.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Glossary | `docs/reference/glossary.md` | Includes 5 meanings of "library" |
| UI design rules | `docs/reference/design-guide.md` | Tokens + anti-patterns |
| mkdocs config | repo-root `mkdocs.yml` | Nav, theme, plugins |

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

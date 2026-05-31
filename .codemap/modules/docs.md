# Module: Docs

> mkdocs-material documentation site for Haywire: extension-point authoring guides, framework internals, reference glossary, and a UI design guide.

**Path:** `docs/`
**Language:** Markdown (mkdocs-material)
**Owner:** All teams (each owns docs near their module)
**Tree hash:** `1b72a3e4ced64c34af43bab1ba30832072d9d78d`
**Mapped at:** 4e5c1da7 (2026-05-31)

---

## 1. Scope & Purpose

Per `CLAUDE.md`, **`docs/` is the first place to look up how a system works** — before reading source code. The site is published with `uv run mkdocs serve` (default `http://127.0.0.1:8000`). Layout follows a strict three-shelf model: components (authoring guides), architecture (internals), and reference (glossary + design guide).

## 2. Folder Architecture

```
docs/
├── index.md               ← site landing page
├── welcome/               ← onboarding
├── adr/                   ← Architecture Decision Records
├── architecture/          ← framework internals
│   └── <area>/<area>-arch.md     e.g., execution-pipeline, library-system, settings-resolution
├── components/            ← extension-point authoring guides
│   └── <area>/<area>-canon.md    e.g., nodes-canon, types-canon, ports-canon, libraries-canon
├── guides/                ← how-tos
├── reference/             ← glossary + design guide
│   ├── glossary.md        ← canonical vocabulary (incl. 5 meanings of "library")
│   └── design-guide.md    ← UI design rules + design tokens
└── archive/               ← retired pages
```

## 3. Always-load vs On-demand

### Always-load (when researching a topic)

- `docs/reference/glossary.md` — canonical vocabulary; resolve term ambiguity here first.
- `docs/index.md` + `docs/welcome/` — site map and onboarding.

### On-demand (by task)

- Authoring nodes/types/ports/widgets/themes/editors/panels → the matching `docs/components/<area>/<area>-canon.md`.
- Understanding execution/library/settings/session internals → the matching `docs/architecture/<area>/<area>-arch.md`.
- ADRs → `docs/adr/` only when explicitly investigating an old decision.
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

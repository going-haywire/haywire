# Module: Docs

> mkdocs-material documentation site for Haywire: extension-point authoring guides, framework internals, Architecture Decision Records, reference glossary and a UI design guide.

**Path:** `docs/`
**Language:** Markdown (mkdocs-material)
**Owner:** All teams (each owns docs near their module)
**Tree hash:** `622d2aeda8c1c2465c997d564918eef2edbc7d83`
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

`docs/` is the reference for how Haywire works. It answers "how does X work" before anyone reads source. It holds the authoring canon for every extension point, the architecture internals per subsystem, ADRs (70 files, numbered 0001–0075 with gaps), the glossary and the design guide. Its code examples are live embeds from source, so they cannot go stale silently. The site builds from `mkdocs.yml` at the repo root. Run `uv run mkdocs serve` to preview.

## 2. Folder Architecture

```
docs/
├── index.md             ← site landing page
├── welcome/             ← onboarding
├── adr/                 ← Architecture Decision Records (70 files; 0015/0016 retired, folded into 0013/0014)
├── architecture/        ← framework internals:
│   ├── design/ errors/ execution/ graph/ hot-reload/ library-system/ overview/
│   ├── session-and-state/ settings/ sharing/ studio/ volumes/
│   └── settings/settings-arch.md  ← single-cell model, promotion, stamped widget contract
├── components/          ← extension-point authoring guides (<area>-canon.md):
│   ├── adapters/ datatypes/ editors/ farmhands/ nodes/ panels/ settings/ skins/ states/ themes/ widgets/
├── haybale/             ← library authoring and packaging: haybale-canon.md, metadata-flow.md, marketplace/
├── guides/              ← how-tos (e.g. sharing-libraries)
├── reference/           ← glossary.md, design-guide.md, doc-authoring.md, files/ (one page per TOML format)
├── superpowers/plans/   ← dated implementation-plan writeups; pruned once landed
└── archive/             ← retired pages
```

## 3. Always-load vs On-demand

### Always-load (when researching a topic)

- `reference/glossary.md` — canonical vocabulary. Resolve term ambiguity here first ("library" has five distinct meanings).
- `index.md` and `welcome/` — site map and onboarding.

### On-demand (by task)

- **Authoring a node, type, port, theme, editor or panel** → `components/<area>/<area>-canon.md`.
- **Authoring widgets** → `components/widgets/widget-canon.md` (BaseWidget unification, ADR 0007).
- **Authoring a library or package** → `haybale/haybale-canon.md`; metadata fields → `haybale/metadata-flow.md`.
- **What a TOML field means** → `reference/files/<file>-toml.md`. Defined once there; other docs link.
- **Marketplace behaviour** → `haybale/marketplace/`.
- **Execution, library, settings, session internals** → `architecture/`.
- **Settings internals** → `architecture/settings/settings-arch.md`, read before the ADRs. Settings arc in order: ADR 0011 (tier collapse) → 0012 (JSON persistence) → 0013 (single-cell value model; includes former 0016 as Amendment) → 0014 (promotion-as-direction; includes former 0015 as Amendment) → 0017 (widget selection port contract).
- **Settings authoring on a node or library** → `components/settings/setting-canon.md`.
- **Show vs hide widget logic** → ADR 0003. **Focus routing** → ADR 0009. **Node compatibility warnings** → ADR 0005. **Realtime frame dropping / queue mode** → ADR 0010.
- **Execution and audio decisions** → `architecture/execution/` and the ADR index (`adr/`); ADR 0070 (data node runs at least once per instance) and 0075 (fields travel on a carrier) are recent.
- **Building UI** → `reference/design-guide.md` is non-optional.

## 4. Rules & Boundaries

- Look here before reading source code when answering "how does X work".
- Components canon covers authoring; architecture covers internals. Do not merge the two.
- ADRs are append-only. A follow-up that refines an ADR is merged as a trailing `## Amendment` section and keeps the original number; retired numbers are never reused. Cite 0013 and 0014 for settings behaviour, not 0015 or 0016.
- Glossary and ADRs land with the code that introduces them, not in separate passes.
- New UI features follow `reference/design-guide.md`.
- Code examples are live embeds from source. Keep embeds pointed at live files.
- Do not reference superpowers plans from permanent files; move lasting reasons to `.insights/`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Vocabulary | `reference/glossary.md` | Authoritative terms |
| UI rules and tokens | `reference/design-guide.md` | Design tokens and anti-patterns |
| Site config | `mkdocs.yml` (repo root) | Nav and theme |
| Decisions | `adr/` | Append-only with amendments |
| Settings internals | `architecture/settings/settings-arch.md` | Single-cell, promotion, widget contract |

---

## Dependencies

### Depends on

- Documents every mapped module. Its code embeds read from [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md) and the `haybale-*` libraries.

### Depended on by

- Users and agents researching behaviour. The Farmhand docs bake in the docs tree (`haywire/core/docs/tree.py`) for the MCP server.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Site landing | `index.md` | Map of the site |
| Glossary | `reference/glossary.md` | Canonical vocabulary |
| Design guide | `reference/design-guide.md` | UI rules |
| ADR index | `adr/` | Decisions |

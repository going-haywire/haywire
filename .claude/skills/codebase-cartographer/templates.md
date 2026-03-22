# Templates Reference

Use these templates verbatim as starting points. Adapt headings and content
to the specific codebase, but keep the structure consistent so that
consuming skills can parse the map reliably.

---

## INDEX.md Template

```markdown
# 🗺️ Codebase Map — {Project Name}

> {One-sentence description of what this project does.}

| Generated | Commit | Tool |
|-----------|--------|------|
| {YYYY-MM-DD HH:MM UTC} | {short hash} | codebase-cartographer |

## Tech Stack

{Language(s)}, {Framework(s)}, {Package manager}, {Runtime(s)}

## Module Index

| Module | Purpose | Manifest |
|--------|---------|----------|
| {name} | {one-line purpose} | [→ modules/{name}.md](modules/{name}.md) |
| ... | ... | ... |

## Cross-cutting Concerns (optional)

| Concern | Doc |
|---------|-----|
| {e.g. Authentication} | [→ cross-cuts/auth.md](cross-cuts/auth.md) |

## How to Use This Map

1. **Start here.** Scan the Module Index above to find the area relevant
   to your task.
2. **Load the manifest.** Open only the module manifest you need.
3. **Follow the Always-load guidance** in that manifest to pull in the
   minimum source files required.
4. **Check cross-cuts** if your task spans multiple modules.
5. **Follow inter-module links** if you need to understand dependencies.

## Quick Stats

- Total modules: {N}
- Estimated source files: {N}
- Map coverage: {percentage of top-level dirs covered}
```

---

## Module Manifest Template — `modules/{name}.md`

```markdown
# Module: {Module Name}

> {2–3 sentence summary of what this module does, who uses it, and why
> it exists as a separate boundary.}

**Path:** `{relative/path/to/module/}`
**Language:** {primary language}
**Owner:** {team or individual, if known}
**Tree hash:** `{output of git rev-parse HEAD:{module-path}}`
**Mapped at:** {short commit hash} ({YYYY-MM-DD})

---

## 1. Scope & Purpose

{Paragraph explaining the module's responsibility. What problems does it
solve? What domain concept does it represent? What would break if this
module disappeared?}

## 2. Folder Architecture

```
{module-root}/
├── {dir-or-file}    ← {annotation}
├── {dir-or-file}    ← {annotation}
│   ├── {subdir}     ← {annotation}
│   └── ...
└── {dir-or-file}    ← {annotation}
```

## 3. Always-load vs On-demand

### Always-load (read these first for any task in this module)

- `{path}` — {why: e.g., "main types & interfaces", "config schema"}
- `{path}` — {why}

### On-demand (read only when the task touches these areas)

- `{path}` — {when: e.g., "when modifying the API layer"}
- `{path}` — {when}

## 4. Rules & Boundaries

- {Rule 1: e.g., "All DB access goes through the repository layer, never
  directly from handlers."}
- {Rule 2: e.g., "This module must not import from the `ui/` module."}
- {Rule 3: e.g., "Public API types are defined in `types.ts` and must not
  be changed without a migration."}

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| {e.g., User schema} | `{path}` | {e.g., "Generated from Prisma"} |
| {e.g., Config} | `{path}` | {e.g., "Env vars validated here"} |

---

## Dependencies

### Depends on

- [{Other module}](other-module.md) — {what it uses: "User types", "Auth middleware"}

### Depended on by

- [{Other module}](other-module.md) — {what it provides: "API client", "Event emitter"}

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| {e.g., HTTP server start} | `{path}` | {brief description} |
| {e.g., CLI command} | `{path}` | {brief description} |
```

---

## Cross-cut Document Template — `cross-cuts/{concern}.md`

```markdown
# Cross-cut: {Concern Name}

> {One-sentence summary of this cross-cutting concern.}

## Overview

{2–3 paragraphs explaining the concern, how it flows through the system,
and which modules it touches.}

## Modules Involved

| Module | Role | Manifest |
|--------|------|----------|
| {name} | {e.g., "Initiates auth flow"} | [→ modules/{name}.md](../modules/{name}.md) |
| ... | ... | ... |

## Flow

{Describe the typical flow, e.g., a numbered list or a simple ASCII
diagram. Keep it under 30 lines.}

## Key Files

- `{path}` — {role in this cross-cut}
- `{path}` — {role}

## Gotchas

- {Known pitfall or non-obvious behaviour}
```

---

## META.md Template

```markdown
# Map Metadata

| Field | Value |
|-------|-------|
| Generated at | {YYYY-MM-DD HH:MM UTC} |
| Last refreshed at | {YYYY-MM-DD HH:MM UTC or "—" if never refreshed} |
| Commit | {full hash from `git rev-parse HEAD`} |
| Branch | {branch name from `git rev-parse --abbrev-ref HEAD`} |
| Generator | codebase-cartographer |
| Modules mapped | {N} |
| Cross-cuts mapped | {N} |
| Git tracked | {Yes / No — "No" if not a git repo} |

## Module Tree Hashes

This table enables incremental refresh. Each hash is the output of
`git rev-parse HEAD:{module-path}` at generation/refresh time. If a
module's current tree hash differs from the value below, its manifest
is stale and should be regenerated.

| Module | Path | Tree hash | Last updated |
|--------|------|-----------|--------------|
| {name} | {relative/path} | {hash} | {YYYY-MM-DD} |
| ... | ... | ... | ... |

## Refresh Instructions

To refresh this map:

1. Run the codebase-cartographer skill — it will detect this META.md
   and perform an incremental update automatically.
2. Or manually:
   a. Run `git rev-parse HEAD:{module-path}` for each module above.
   b. Compare against the stored tree hash.
   c. Rewrite only the manifests whose hashes changed.
   d. Update this table and the Change Log below.

## Uncommitted Changes

If `git status --porcelain` shows uncommitted changes at refresh time,
the map only reflects the last committed state. Uncommitted work is
noted here but not mapped.

Last check: {clean / N files with uncommitted changes}

## Change Log

| Date | Commit | Summary |
|------|--------|---------|
| {date} | {short hash} | Initial generation — {N} modules mapped |
```

When refreshing, append a row to the Change Log for each refresh:
```markdown
| {date} | {short hash} | Refreshed {N} modules ({list}). {M} unchanged. {K} new. {J} removed. |
```

Include a condensed `git diff --stat` summary as a sub-section after
the Change Log entry when it would be helpful (e.g., >10 files changed):
```markdown
### Diff since {old short hash}

{paste condensed output of `git diff --stat {old}..{new} | tail -1`}

Changed modules: {module-a}, {module-b}
Unchanged modules: {module-c}, {module-d}
```

---

## Style Rules for All Templates

1. **Line budgets are hard limits.** INDEX.md ≤ 120 lines.
   Module manifests ≤ 200 lines. Cross-cuts ≤ 150 lines.
2. **Use relative paths** from the `.codemap/` directory.
3. **One sentence per table cell.** If you need more, put it in the
   body section instead.
4. **No code snippets** in the map — link to the source file instead.
5. **Mark unknowns.** If you cannot determine something, write
   `⚠️ TODO: {what needs investigation}` rather than guessing.
6. **Keep annotations terse.** The goal is navigation, not explanation.
   A reader should be able to scan a manifest in under 60 seconds.

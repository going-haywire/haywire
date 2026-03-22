---
name: codebase-cartographer
description: >
  Generate a modular .codemap/ documentation map of any codebase — interlinked module manifests that skills and agents use to navigate code efficiently. Trigger on: "map/document/index this codebase", "architecture doc", "project overview", "help me understand this repo", onboarding requests, or when any skill needs a structural reference to the codebase.
---

# Codebase Cartographer

Generate a modular, interlinked documentation map of any codebase so that
skills, agents, and humans can navigate to exactly the right code section
without loading irrelevant context.

## Philosophy

The map is **not** a single giant document. It is a tree of small, focused
manifest files — one per module or logical boundary — linked together by a
lightweight root index. Any consumer (skill, agent, human) loads only the
root index (~50–100 lines), finds the module they need, then loads only that
module's manifest. This keeps the context window lean.

---

## Quick-start (read this first, then the reference files as needed)

### 1. Scan the codebase

```
Read the top-level directory tree (2 levels deep).
Identify: language(s), framework(s), package manager, entry points.
```

### 2. Identify modules

A "module" is any logical boundary the team would recognise:
a top-level folder, a package, a microservice, a bounded context, a
feature area, etc. Aim for 4–15 modules for most projects; nest deeper
only if a module is genuinely complex.

### 3. Generate the map

Produce the following file tree inside a `.codemap/` directory at the
project root (or wherever the user specifies):

```
.codemap/
├── INDEX.md            ← root index (always-load)
├── modules/
│   ├── <module-a>.md   ← per-module manifest
│   ├── <module-b>.md
│   └── ...
├── cross-cuts/
│   ├── data-flow.md    ← optional cross-cutting concern docs
│   ├── auth.md
│   └── ...
└── META.md             ← generation metadata & refresh instructions
```

### 4. Write each file

Follow the templates in `references/templates.md`. The key rules:

- **INDEX.md** ≤ 120 lines. Contains: project summary, module table
  (name → one-line purpose → relative path to manifest), tech stack,
  and a "How to use this map" section for consumers.

- **Module manifests** ≤ 200 lines each. Contains the five sections
  the user asked for:
  1. **Scope & Purpose** — what this module does and why it exists.
  2. **Folder Architecture** — annotated tree of the module's directory.
  3. **Always-load vs On-demand** — which files/concepts a consumer
     should load immediately vs defer until needed.
  4. **Rules & Boundaries** — invariants, forbidden patterns, API
     contracts, ownership.
  5. **Source of Truth** — canonical files for config, types, schemas,
     or state that other modules depend on.

  Plus two linking sections:
  - **Depends on** → links to other module manifests this module imports.
  - **Depended on by** → links to manifests that import this module.

- **Cross-cut docs** (optional) — for concerns that span modules:
  authentication flow, data pipeline, deployment topology, etc.

- **META.md** — when the map was generated, which commit, how to refresh.

### 5. Validate

After generating, do a quick self-check:
- Every module manifest is linked from INDEX.md.
- Every inter-module link points to a file that exists.
- No single file exceeds its line budget.
- The map covers ≥90 % of the codebase's top-level directories.

### 6. Present to the user

Show a summary of what was generated, how many modules were found,
and give the user the `.codemap/INDEX.md` as the entry point.

---

## Git tracking

When generating a map, always record git state:

1. Run `git rev-parse HEAD` to get the current commit hash.
2. Run `git rev-parse --abbrev-ref HEAD` for the branch name.
3. For **each module**, compute its tree hash:
   `git rev-parse HEAD:{relative/path/to/module}`.
4. Store the global hash and branch in META.md.
5. Store per-module tree hashes in META.md's module hash table.

If the codebase is not a git repo, skip hash tracking and note
"Not a git repository — incremental refresh unavailable" in META.md.

---

## Refresh workflow (incremental updates)

When `.codemap/` already exists, **do not regenerate from scratch**.
Follow this incremental flow instead:

### Step 0: Detect existing map

Before generating anything, check whether `.codemap/META.md` exists.
If it does, switch to this refresh workflow. If not, do a full
generation (Quick-start above).

### Step 1: Read the old state

Parse META.md to extract:
- `old_commit` — the commit hash from last generation.
- `module_hashes` — the per-module tree hash table.

If `old_commit` is missing or invalid, fall back to full regeneration.

### Step 2: Check for uncommitted changes

Run:
```bash
git status --porcelain
```
If there are uncommitted changes, warn the user:
> "There are uncommitted changes. The refresh will compare against the
> last committed state. Uncommitted files may not be reflected."

Let the user decide whether to proceed or commit first.

### Step 3: Identify stale modules

For each module in the hash table, recompute its current tree hash:
```bash
git rev-parse HEAD:{module-path}
```

Compare against the stored hash. Three outcomes per module:

| Outcome | Action |
|---------|--------|
| Hash unchanged | Skip — manifest is current |
| Hash changed | Regenerate this module's manifest |
| Module path no longer exists | Remove manifest, update INDEX.md |

Also check for **new top-level directories** that weren't in the
previous map. If found, generate new manifests for them.

### Step 4: Get a human-readable change summary

Run:
```bash
git diff --stat {old_commit}..HEAD
```

Include a condensed version of this output in META.md's change log
so the user (and consuming agents) can see at a glance what moved.

For each stale module, also run:
```bash
git diff --name-only {old_commit}..HEAD -- {module-path}
```
to see exactly which files changed. Use this to inform the manifest
update — for example, if only test files changed, the Always-load
section probably doesn't need updating.

### Step 5: Regenerate stale manifests

For each module whose tree hash changed:
1. Re-scan its directory structure.
2. Rewrite its manifest following the same template.
3. Update its "Depends on" / "Depended on by" links (changes in one
   module may affect another module's dependency section).
4. Record the new tree hash.

### Step 6: Update INDEX.md (if needed)

Update INDEX.md only if:
- A module was added or removed.
- A module's one-line purpose changed significantly.
- The tech stack changed (new dependency in root package manifest).

If only existing module contents changed, INDEX.md stays untouched.

### Step 7: Update META.md

- Set the new commit hash and timestamp.
- Update the per-module hash table.
- Append an entry to the change log:
  ```
  | {date} | Refreshed {N} modules: {list}. {M} unchanged. |
  ```

### Step 8: Report to the user

Show a summary:
- How many modules were refreshed vs skipped.
- Any new modules discovered.
- Any modules removed (directory deleted).
- The git diff stat summary.

---

## How other skills/agents consume the map

Instruct consuming skills to:

1. Read `.codemap/INDEX.md` (tiny, always fits in context).
2. Identify which module(s) are relevant to the current task.
3. Read only those module manifests.
4. Use the "Always-load" vs "On-demand" guidance within each manifest
   to decide which actual source files to read.

This two-hop lookup keeps context usage minimal.

---

## Reference files

Read these before generating:

- `references/templates.md` — exact templates for INDEX.md, module
  manifests, cross-cut docs, and META.md. **Read this before writing
  any output.**
- `references/analysis-guide.md` — how to identify modules, detect
  boundaries, and handle edge cases (monorepos, microservices,
  framework-specific patterns).

---

## Important guidelines

- Prefer accuracy over completeness. It is better to honestly mark a
  section as "TODO — needs deeper analysis" than to hallucinate.
- Use relative paths everywhere so the map works regardless of where
  the repo is cloned.
- Keep language neutral where possible; annotate language-specific
  patterns only when they affect navigation.
- If the codebase is very large (>500 files), generate a "quick map"
  first (INDEX.md + top 5 most important modules) and offer to expand.
- Always ask the user if they want cross-cut docs before generating
  them — they add value but also add maintenance burden.

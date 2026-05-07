# Analysis Guide

How to identify modules, detect boundaries, and handle edge cases when
mapping a codebase.

---

## Step 1: Reconnaissance

Before writing anything, gather these signals:

1. **Directory tree** (2 levels deep from root).
2. **Package manifest** — `package.json`, `Cargo.toml`, `pyproject.toml`,
   `go.mod`, `pom.xml`, etc. This tells you the language, deps, and often
   the project's self-description.
3. **Entry points** — `main.*`, `index.*`, `app.*`, `server.*`, CLI
   definitions, Dockerfile `CMD`/`ENTRYPOINT`.
4. **Existing docs** — `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`,
   `CLAUDE.md`, `internals/` folder.
5. **CI config** — `.github/workflows/`, `Makefile`, `Justfile`, etc.
   These reveal the build/test/deploy pipeline and often name the
   important directories.
6. **Ignore patterns** — `.gitignore`, `.dockerignore`. These tell you
   what is generated vs authored.

---

## Step 2: Module Identification

A module is a **logical boundary** that a team member would recognise.
Use these heuristics (in priority order):

### Strong signals (almost certainly a module)

- Has its own `package.json`, `Cargo.toml`, or equivalent.
- Is a microservice with its own Dockerfile or deploy config.
- Is referenced as a workspace member in a monorepo tool.
- Has a clear domain name matching business language (e.g., `billing/`,
  `auth/`, `notifications/`).

### Medium signals (likely a module)

- Is a top-level directory with >5 source files.
- Has its own test directory or test config.
- Is imported by many other directories (high fan-out).
- Has a README or index file that describes its purpose.

### Weak signals (maybe a module, maybe a sub-module)

- Is a sub-directory more than 2 levels deep.
- Contains only utility or helper code.
- Has few or no imports from other parts of the codebase.

### Not a module

- Build output directories (`dist/`, `build/`, `target/`, `node_modules/`).
- Config-only directories (`.github/`, `.vscode/`).
- Empty or placeholder directories.
- Third-party vendored code (unless the team actively modifies it).

---

## Step 3: Dependency Detection

For each module, identify:

1. **Internal imports** — which other modules does it import from?
   Search for import statements referencing paths outside the module.
2. **Shared types** — which type definitions or interfaces are consumed
   across module boundaries?
3. **Runtime dependencies** — does it call another module's API over
   HTTP, gRPC, message queue, etc.?
4. **Database dependencies** — do multiple modules read/write the same
   tables or collections?

Record these as "Depends on" and "Depended on by" links.

---

## Step 4: Always-load vs On-demand Classification

For each module, classify its files:

### Always-load criteria

The file is always-load if **any** of these are true:
- It defines the module's public API (exported types, interfaces, routes).
- It is the main entry point.
- It contains configuration or environment validation.
- It defines core domain types or schemas.
- Changing it would require changes in other modules.

### On-demand criteria

The file is on-demand if:
- It implements internal logic that doesn't affect the public API.
- It is a test file.
- It is a migration, seed, or fixture file.
- It is a utility used only within this module.
- It is documentation or examples.

When in doubt, classify as **on-demand**. It's better to load a file
when asked than to bloat every context window with it.

---

## Edge Cases

### Monorepos with many packages

- Map each workspace package as a module.
- If there are >15 packages, group them into "module groups" in INDEX.md
  and create a sub-index for each group.

### Microservices in separate repos

- Map each repo independently.
- Create a top-level INDEX.md that links to each repo's `.codemap/`.

### Framework-specific patterns

**Next.js / Nuxt / SvelteKit / Remix:**
- `app/` or `pages/` is usually one module ("Routes").
- `components/` is another ("UI Components").
- `lib/` or `utils/` is another ("Shared Utilities").
- API routes may be their own module if complex.

**Django / Rails:**
- Each Django app or Rails concern is a module.
- `models/` within an app is always-load.
- `migrations/` is on-demand.

**Go:**
- Each top-level `cmd/` entry is a module.
- Each `internals/` or `pkg/` package is a module.

**Rust:**
- Each workspace crate is a module.
- `lib.rs` / `mod.rs` are always-load within each crate.

### Very small codebases (<20 files)

- Generate a single INDEX.md with inline descriptions.
- Skip separate module manifests — the overhead isn't worth it.
- Still generate META.md for refresh tracking.

### Very large codebases (>500 files)

- Generate a "quick map" first: INDEX.md + the 5 most important modules.
- Offer to expand incrementally.
- Consider generating cross-cut docs for the top 2–3 concerns.

---

## Rules of Thumb

1. **Aim for 4–15 modules.** Fewer than 4 means the map is too shallow.
   More than 15 means you should group or nest.
2. **Every module should be explainable in one sentence.** If you need
   a paragraph, the boundary might be wrong.
3. **Follow the code's own boundaries.** Don't impose an architecture
   the code doesn't have. Document what is, not what should be.
4. **Mark tech debt honestly.** If a module has poor boundaries, say so
   in the Rules & Boundaries section.
5. **Prefer breadth over depth on the first pass.** Cover all modules
   at a shallow level before going deep on any one.

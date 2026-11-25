# A project's `.haywire/` is local: design

Task `design/haywire-dir-in-git`, issues
[#205](https://github.com/going-haywire/haywire/issues/205) and
[#245](https://github.com/going-haywire/haywire/issues/245).

| Status | |
|---|---|
| Decided | 2026-11-25: 1A, 2A, 3D, 4A, 5A, 6A, 7B, 8A |
| Implemented | not yet: the core slice lands ADR 0096 and the glossary edits below (`docs/reference/doc-authoring.md`: an ADR is written in the same change as its code) |

## The files today

| File | Holds | Written by, when | Scope |
|---|---|---|---|
| `settings.json` | Workspace settings tier: UI toggles, log level, `haystack.last_haystack_name`, `network.port` | Studio UI on each change (`core/settings/registry.py:8`); port by `scripts/worktree_setup.py:22` | User and machine |
| `marketplace.toml` | `[[heaps]]` (absolute paths) and `[[caches]]` | Heaps by `haywire init` (`init.py:1094`, `--dev` `init.py:804`); caches by every refresh at studio start (`marketstall/refresh.py:388`) | Machine; derived |
| `host.toml` | `[libraries] disabled` | Library browser enable/disable via `HostStore` (`haywire_studio/app.py:205`) | Machine |
| `config.toml` | `[haywire] version` | `haywire init` (`haywire_studio/config.py:80`); **no reader** | Leftover |
| `workspace_state.json` | Open graphs, slots, pan/zoom | Session (`session/workspace/manager.py:40`) | Session (#87) |
| `studio.json`, `studioctl.log`, `farmhand_token` (no longer minted) | Running studio | `studio start` | Runtime |
| `.gitignore` | `studio.json` | Studio identity (`farmhand/identity.py:25`) | — |

How repositories handle it: core ignores `.haywire/` (`.gitignore:221`) but tracks
`config.toml`; the `init` template ignores only `workspace_state.json` (`init.py:492`); the
org-library refresh adds three lines (`agents.py:93`); share and rename exclude
`settings.json` by hand (`core/publishing/git.py:39`).

| Library | Tracks under `.haywire/` |
|---|---|
| comfyui | `.gitignore`, `config.toml`, `marketplace.toml` |
| protokol | `config.toml`, `marketplace.toml` |
| speech | `config.toml`, `marketplace.toml` (heap still points at `haybale-speach`) |
| spandrel | `config.toml` (ignores `marketplace.toml`) |
| stream | nothing (`?? .haywire/`) |
| visiongraph | `.gitignore`, `config.toml`, `host.toml`, `marketplace.toml`, `settings.json` |

`~/.haywire/` lies outside every repository and is out of scope.

## Decisions

1. **A. `settings.json` is ignored everywhere.** The port stays in it. The UI rewrites it on
   ordinary use; no setting has to travel with a repository yet. Rejected: a committed file
   plus a `settings.local.json` tier (B), committing it with the port moved out (C).
2. **A. `marketplace.toml` is ignored everywhere.** Caches are derived, `--dev` heaps describe
   one machine. Rejected: committing relative heaps with caches split out (B), the status quo (C).
3. **D. Heaps of the project's own `barn/` libraries are derived at every refresh** and never
   written. Rejected: no heaps on a clone (A), copying the main folder's file in the
   worktree setup (B, the own heap would point at the main folder), writing missing heaps (C).
4. **A. `--dev` sibling heaps are derived too**, from `pyproject.toml`: workspace members plus
   editable path sources that are libraries. `[[heaps]]` stays as a hand-written override
   only; `init --dev` writes none (`_register_dev_repo_locals_in_project` goes), and rename
   has no heaps to rewrite (`rename/planner.py:70`). Rejected: `init --dev` keeps writing
   siblings (B, two records that drift), no override at all (C).
5. **A. `host.toml` is ignored.** Disabling a library is a choice on one machine; which
   libraries a project uses is in `pyproject.toml`. Rejected: committing it (B), splitting it (C).
6. **A. `config.toml` is retired.** `init` stops writing it; `ensure_project_config` and
   `get_project_config` are deleted; every repository untracks it. Shared project config,
   if ever needed, goes in `pyproject.toml` `[tool.haywire]`. Rejected: keeping it empty for
   later (B), the status quo (C).
7. **B. `.haywire/` ignores itself.** One helper `ensure_haywire_dir(root)` creates the
   directory and writes `.haywire/.gitignore` holding `*` **whenever that file is missing**,
   not only on creation, so existing directories are covered. Every writer goes through it
   (settings save, workspace state, `HostStore`, refresh, studio identity). Removed: the
   `init` template's `.haywire` line, `agents.py`'s `_GITIGNORE`, and `LOCAL_STATE` with
   `WHOLE_TREE_BUT_LOCAL_STATE` in `core/publishing/git.py` and their uses. Rejected: a root
   `.gitignore` line (A), both (C).
8. **A. Migration: core first, then the release, then one `chore/` PR per library**
   (comfyui, protokol, speech, spandrel, stream, visiongraph): `git rm --cached` what the
   table above lists, drop the old `.gitignore` lines 44–47 (spandrel: also line 38). Each
   library PR only with the user's OK. Rejected: library PRs with a temporary `/.haywire/`
   line before the release (B), the org-library refresh untracking files itself (C).

Out of scope: `~/.haywire/`; workspace state per principal (#87); a committed shared
project settings file.

## Slices

1. **Core** (`fix/haywire-dir-local`, fixes #205 and #245): decisions 3, 4, 6, 7; core
   untracks `.haywire/config.toml` and keeps `.gitignore:221` or drops it (the directory
   ignores itself); ADR 0096; glossary edits; `docs/reference/files/marketplace-toml.md`
   (heaps derived, file local: rewrite *Project marketplace*, *Heap fields* and the
   absolute-path warning at line 173); `.insights/` if a trap shows up. Tests: heap
   derivation from workspace members and path sources, override precedence, the helper
   writing `.gitignore` into an existing directory, share/rename clean-tree checks with an
   untracked `.haywire/`.
2. **Release** of core.
3. **Six library PRs**, as decision 8.

## Draft ADR 0096

```markdown
---
name: a-projects-haywire-folder-is-local
description: nothing in a project's .haywire/ is committed; the folder ignores itself through a .gitignore holding *, heaps are derived from pyproject.toml, and the unread config.toml is retired
status: accepted
level: architectural
---

# A project's `.haywire/` is local and ignores itself

**Context.**

- A project's `.haywire/` holds `settings.json`, `marketplace.toml`, `host.toml`, `config.toml`, `workspace_state.json` and the running studio's files. The studio rewrites most of them during ordinary use: settings on each UI change, `[[caches]]` in `marketplace.toml` at every start, `host.toml` on each enable or disable.
- Repositories disagreed: core ignored the folder but tracked `config.toml`; the `init` template ignored only `workspace_state.json`; visiongraph tracked `settings.json`, `host.toml` and `marketplace.toml`; speech's tracked `marketplace.toml` changed on every studio start (#245) and its heap still pointed at the folder's old name. Share and rename skipped `settings.json` by hand (#205).
- `[[heaps]]` held absolute paths of one machine, written by `haywire init` and `init --dev`, while `pyproject.toml` already lists the same libraries by relative path: `[tool.uv.workspace] members` and editable `[tool.uv.sources]`.
- `config.toml` was written by `init` and read by nothing.

**Decision.**

- **Nothing in a project's `.haywire/` is committed.** `settings.json`, `marketplace.toml`, `host.toml`, `workspace_state.json` and the studio's runtime files are all local to one checkout.
- **The folder ignores itself.** One helper creates `.haywire/` and writes `.haywire/.gitignore` holding `*` whenever it is missing; every writer goes through it. No repository needs a `.haywire` line in its own `.gitignore`, and share and rename need no exception for any file in it.
- **Heaps are derived.** At every refresh the studio derives heaps from `pyproject.toml`: the workspace members (the project's own `barn/` libraries) and editable path sources that are libraries (a `--dev` project's siblings), each with the path of the current checkout. A `[[heaps]]` entry in `marketplace.toml` remains as a hand-written override for a library elsewhere on disk; `haywire init` writes none.
- **`config.toml` is retired.** Shared project configuration, when one is needed, belongs in `pyproject.toml` `[tool.haywire]`.

**Considered.**

- *A committed `settings.json` with an ignored `settings.local.json` on top.* A third settings tier for a need no setting has yet.
- *Committing heaps with relative paths and moving `[[caches]]` into an ignored file.* Changes the parser, `init`, `init --dev` and rename, and sibling paths still assume one folder layout.
- *Committing `host.toml`.* Disabling a library is a choice on one machine; the libraries a project uses are in `pyproject.toml`.
- *A `/.haywire/` line in each repository's root `.gitignore`.* Leaves any folder opened without `init` unprotected and keeps a template line in sync in every repository.

**Consequences.**

- A fresh clone or a worktree gets its heaps right on its first studio start, with nothing copied or regenerated by the worktree setup.
- `marketplace.toml` is safe to delete unless it holds a hand-written heap.
- Existing repositories untrack their `.haywire/` files once, after the core release that brings the helper.
- A project that wants a shared setting has no place for it in `.haywire/`; it would add one to `pyproject.toml`.
```

## Glossary edits (with slice 1)

- **Marketplace** (`glossary.md:235`): "built by merging the project's local `[[heaps]]`"
  becomes "built by merging the project's **heaps**, derived from `pyproject.toml` at each
  refresh, with all remote subscriptions …".
- **Agent files** (`glossary.md:266`): drop "the machine-local `.haywire` lines in
  `.gitignore`" from the declarations.
- New term **Heap**: a library on local disk the marketplace shows as `local` and lets win
  over a marketplace row of the same name; derived from the project's `pyproject.toml`
  (workspace members, editable path sources), or written by hand in the project's
  `marketplace.toml`. Avoid: local library (ambiguous with an installed one).

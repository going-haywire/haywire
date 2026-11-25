---
name: a-projects-haywire-folder-is-local
description: nothing in a project's .haywire/ is committed; the folder ignores itself through a .gitignore holding *, heaps are derived from pyproject.toml, and the unread config.toml is retired
status: accepted
level: architectural
---

# A project's `.haywire/` is local and ignores itself

**Context.**

- A project's `.haywire/` holds `settings.json`, `marketplace.toml`, `host.toml`, `config.toml`, `workspace_state.json` and the running studio's files. The studio rewrites most of them during ordinary use: settings on each UI change, `[[caches]]` in `marketplace.toml` at every start, `host.toml` on each enable or disable.
- Repositories disagreed. Core ignored the folder but tracked `config.toml`; the `init` template ignored only `workspace_state.json`; visiongraph tracked `settings.json`, `host.toml` and `marketplace.toml`; speech's tracked `marketplace.toml` changed on every studio start (#245), and its heap still pointed at the folder's old name. Share and rename skipped `settings.json` by hand (#205).
- `[[heaps]]` held absolute paths of one machine, written by `haywire init` and `init --dev`, while `pyproject.toml` already names the same libraries by relative path: `[tool.uv.workspace] members` and editable `[tool.uv.sources]`.
- `config.toml` was written by `init` and read by nothing.

**Decision.**

- **Nothing in a project's `.haywire/` is committed.** `settings.json` (the studio port stays in it), `marketplace.toml`, `host.toml`, `workspace_state.json` and the studio's runtime files are all local to one checkout.
- **The folder ignores itself.** `ensure_haywire_dir()` (`haywire.core.storage`) creates `.haywire/` and writes `.haywire/.gitignore` holding `*` whenever that file does not hold the line; every writer creates the folder through it. `worktree_setup.py`, which runs before core is installed, writes the same file itself. No repository needs a `.haywire` line in its own `.gitignore`, and share and rename need no exception for any file in the folder.
- **Heaps are derived.** Every refresh, and every render of the library browser, derives the project's heaps from `pyproject.toml` (`haywire.core.marketstall.heaps`): the workspace members, the editable path sources, and the libraries beside such a source (the rest of a dev repo's `barn/`), each with the path of the current checkout. Only folders whose package holds a `haybale.toml` count. A `[[heaps]]` entry in `marketplace.toml` stays as a hand-written override for a library elsewhere on disk, and replaces the derived heap of the same name. `haywire init` writes none.
- **`config.toml` is retired.** Shared project configuration, when one is needed, belongs in `pyproject.toml` `[tool.haywire]`.

**Considered.**

- *A committed `settings.json` with an ignored `settings.local.json` on top.* A third settings tier for a need no setting has yet.
- *Committing heaps with relative paths and moving `[[caches]]` into an ignored file.* Changes the parser, `init`, `init --dev` and rename, and sibling paths still assume one folder layout.
- *Letting `init --dev` keep writing the sibling heaps.* Two records of the same libraries, which drift: speech's heap kept the old folder name after `pyproject.toml` was fixed.
- *Committing `host.toml`.* Disabling a library is a choice on one machine; the libraries a project uses are in `pyproject.toml`.
- *A `/.haywire/` line in each repository's root `.gitignore`.* Leaves any folder opened without `init` unprotected and keeps a template line in sync in every repository.

**Consequences.**

- A fresh clone or a worktree gets its heaps right on its first studio start, with nothing copied by the worktree setup.
- `marketplace.toml` is safe to delete unless it holds a hand-written heap.
- A repository that still tracks a `.haywire/` file shows it as modified until it untracks it (`git rm --cached`); the org libraries do so once, after the core release that brings the helper. Until then share and rename count such a change as dirt.
- A project that wants a shared setting has no place for it in `.haywire/`; it adds one to `pyproject.toml`.

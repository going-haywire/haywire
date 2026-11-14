---
name: libraries-from-other-repositories-run-from-an-umbrella-environment
description: Libraries that live in their own repositories are never linked into barn/; a separate umbrella environment beside the repositories installs every package editable to run the full studio, while each repository keeps its own environment for its tests and CI
status: accepted
level: architectural
---

# Libraries from other repositories run from an umbrella environment

**Context.**

- Several haybale libraries live in their own repositories (spandrel, visiongraph, stream, comfyui, protokol): they have heavy or platform-specific dependencies and release on their own schedule.
- Running the studio with them needs them installed beside this repository's packages. They were symlinked into `barn/`, kept out of the uv workspace (so CI never sees paths that exist on one machine only) and installed by hand with `uv pip install -e`. Every `uv sync` removed them again, because it installs exactly what the lockfile lists; the symlinks also needed gitignore entries, workspace excludes and re-linking in every worktree.
- uv applies a library's own workspace `[tool.uv.sources]` when that library is installed from a path, so a sibling repository's development `pyproject.toml` takes part in any environment that installs it.

**Decision.**

- **Nothing from another repository is linked into `barn/`.** This repository's workspace holds only its own packages; its environment and lockfile are exactly what CI resolves.
- **An umbrella environment in the folder that holds the repositories side by side** (its own small repository, `going-haywire/umbrella`) lists every package of every repository as an editable path source, pinned to the repositories' Python version. `uv sync` there builds one environment for running the full studio.
- **The studio is started inside a project folder with `--project` pointing at the umbrella** (`cd haywire-repo && uv run --project .. haywire`), because the studio takes the folder it starts in as its project.
- **Each repository keeps its own environment** for its own tests and CI.
- **Every path source is relative**, in the umbrella and in each repository's development project (`haywire init --dev` writes them so), so the same files work on any machine that clones the repositories side by side.
- **A worktree's code runs with the full studio through an overlay**: `uv run --project <umbrella> --with-editable <package>` replaces the named packages for one run without changing the umbrella.

**Considered.**

- *Keeping the symlinks and reinstalling after each sync* (`uv sync --inexact`, a wrapper). Treats the symptom; every machine-specific detail stays in the shared repository.
- *Merging the libraries into this repository.* One lockfile, but torch and native packages enter CI and every contributor's install, and the libraries lose their own release schedule.
- *Git submodules.* Real folders instead of links, but CI would have to fetch and lock every library.

**Consequences.**

- The umbrella folder is never a studio project and never gets a `CLAUDE.md`: agents also read `CLAUDE.md` files from parent folders, so one there would reach every repository's sessions.
- A repository missing on a machine has to be dropped from the umbrella's `pyproject.toml` locally before `uv sync`.
- Code that lists every installed distribution sees an overlaid package twice during an overlay run; library discovery through entry points does not.
- Hot reload works on the sibling repositories' files, since their modules load from their real folders.

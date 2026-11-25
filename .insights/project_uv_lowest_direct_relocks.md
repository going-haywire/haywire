---
name: uv lowest-direct resolution is undone silently
description: after a lowest-direct lock, a plain `uv sync` or `uv run` relocks at highest, and a lock already in lowest-direct mode keeps the versions it holds; set UV_RESOLUTION for every command and sync with --upgrade
type: project
---

**A lowest-direct resolution is undone without a word in two ways.**

1. **A command without the flag relocks at highest.** `uv lock --resolution
   lowest-direct` and then a plain `uv sync` (or `uv run`) see a lock made in another
   mode and resolve it again at highest. The tests then run the newest versions while
   you think they run the floors.
2. **A lock already in lowest-direct mode keeps what it holds.** uv prefers the
   versions in the lock, so lowering a floor (opencv `>=5.0.0.93` to `>=4.13.0.90`)
   leaves the old version locked until `--upgrade` (or `--upgrade-package`).

**How to apply.** Set `UV_RESOLUTION=lowest-direct` in the environment, so every uv
command uses it, and sync with `uv sync --upgrade --all-extras --dev`, as the `floors`
job in `ci.yml` does ([ADR 0095](../docs/adr/0095-a-dependency-floor-is-the-oldest-version-known-to-work.md)).
Check what got installed (`uv pip list`) before trusting a green run. Locally, put
`uv.lock` back afterwards (`git checkout uv.lock`).

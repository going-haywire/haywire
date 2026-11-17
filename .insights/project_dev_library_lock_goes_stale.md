---
name: A dev library's uv.lock goes stale on every core release
description: A `--dev` library's uv.lock records the versions of its path sources in ../haywire-repo; each core release bumps them, the next `uv run` relocks and dirties the tree, and `share` then meets a dirty tree
type: project
---

**A `--dev` library's `uv.lock` records the versions of its path sources** in
`../haywire-repo`. Every core release bumps those versions, so the lock is stale from
then on: the next `uv run` relocks it and leaves the working tree dirty before `share`
starts, so `share` meets a dirty tree. Only `--dev` projects (the org's libraries)
hit it.

**Workaround, until `share` tolerates the lock** (plan slice S4):

```sh
git checkout uv.lock
uv run --frozen haywire share ...
```

`--frozen` stops `uv run` from relocking. `share` relocks and commits `uv.lock` itself
as part of its version step, so the committed lock is right after a release.

**How to apply.** A dirty `uv.lock` and nothing else in a library repository after a
core release is this trap, not an edit of yours: restore it, do not commit it.

---
name: Publishing by git URL means consumers get a clone — three silent-corruption traps
description: Haybales install via git+URL clone, so gitignored files vanish, LFS assets become pointer text, and install_spec/doc URLs are tag-pinned only through SharePipeline. All three fail silently on the consumer's machine.
type: project
---

A published haybale installs as `uv pip install git+https://host/owner/repo.git#subdirectory=barn/haybale-x` (`_parse_git_install_spec`, `barn/haybale-marketplace/haybale_marketplace/library_manager.py:38`). uv **clones the repo** — it does not build and ship a wheel. Everything below follows from that, and all three failures land on *consumers*, not on the author, with no error at install time.

## 1. Anything gitignored inside `barn/` is absent for consumers

Ignored ⇒ never committed ⇒ not in the clone ⇒ missing at runtime.

The scaffolded `.gitignore` ships this trap live. `build/`, `dist/`, and `env/` were written **unanchored**, and an unanchored git pattern matches at *every depth* — including `barn/haybale-x/haybale_x/build/`. A node library with compiled shaders in `build/`, bundled assets in `dist/`, or config in `env/` silently loses all of it. Verified: with the pre-fix scaffold, `git ls-files --others --ignored --exclude-standard barn/` reports exactly those three directories inside the library package.

Fix applied at the scaffold (`_generate_gitignore`): anchor root-only patterns with a leading slash (`/build/`, `/dist/`, `/env/`, `/venv/`, `/.venv/`).

**Don't add share-time detection for this.** After anchoring, the patterns that still legitimately match at depth (`__pycache__/`, `*.egg-info/`, `*.egg`) hit on every fresh library, so a warning fires 3-for-3 on day one and trains users to skip it. An edited `.gitignore` is an expression of intent.

## 2. Git LFS turns assets into pointer text for consumers without git-lfs

Do **not** scaffold `git lfs install` or LFS patterns into `.gitattributes`.

Verified: with `*.png filter=lfs`, git stores a ~130-byte pointer file, not the image. A consumer cloning **without git-lfs installed** receives that pointer — a text file with the right filename and the wrong contents:

```text
version https://git-lfs.github.com/spec/v1
oid sha256:1e646e690fc8df067246825738a6b33f46b89bbfaa3c63576f671979c0c87540
size 26
```

The install *succeeds*; the library breaks later when it loads the asset. Whether uv's clone runs the smudge filter depends on the consumer's global LFS config — something neither the publisher nor Haywire controls or can detect. `*.png` is exactly what a library's icons and skins match, so the trap fires on the most common case.

Scaffolded at init (`_generate_gitattributes`): text=auto plus `binary` markers for common asset types, and a comment block explaining the pointer-file trap. No `filter=lfs` line is ever written.

## 3. `install_spec`/`docs_url`/`examples_url`/`tests_url` are pinned to the release tag — but only through the full pipeline

**Fixed** (`docs/superpowers/plans/2026-08-01-marketstall-tag-pinning.md`). `_build_entry_for_library` (`packages/haywire-studio/src/haywire_studio/packaging/share/marketstall.py:28`) accepts an optional `tag` parameter. `apply_marketstall()` (`share/pipeline/steps/commit.py:18`) always supplies `f"v{pipeline.version}"` — the version step 3 resolves and tag-collision-checks before step 5 runs, so the tag name is known even though `apply()` (later in that same step) hasn't created the actual git tag yet. All four ref-bearing URLs pin to that tag, so a marketstall entry advertising `min_version = "0.3.1"` installs exactly that state, not whatever `master`/`main` currently holds.

**This only applies through the full `SharePipeline` flow.** `write_marketstall()`/`build_marketstall_entries()`/`_build_entry_for_library()` called directly with no `tag` argument (any standalone script, or a test that doesn't pass one) still fall back to the pre-fix behavior: `install_spec` ref-less (floats to default-branch HEAD), the other three URLs pinned to whatever branch is currently checked out. This is intentional backward compatibility, not a remaining bug — if you add a new caller of these functions, decide explicitly whether it has a tag to pass.

The marketstall **share URL** itself (`_derive_url` in `share/url.py`, i.e. `result.share_url` — the URL *to* `marketstall.toml`, not any haybale entry) is deliberately NOT part of this fix and stays branch-pinned: it's meant to always resolve to the latest commit on the branch, not freeze to a past release tag.

If a tag-pinned `install_spec` is ever consumed via `[tool.uv.sources]` (as opposed to the plain PEP 508 `git+URL@tag#subdirectory=` string it uses today), the `@tag` suffix must **not** end up in the `git` value itself. Verified: uv treats it as part of the URL path and the clone 404s (`repository 'https://github.com/pypa/packaging.git@24.0/' not found`). It needs a separate key, which uv then locks to a resolved SHA:

```toml
[tool.uv.sources]
packaging = { git = "https://github.com/pypa/packaging.git", tag = "24.0" }
```

PEP 508's `git+URL@tag#subdirectory=` spelling (what `install_spec` actually uses) is fine as-is — this gotcha only bites if something later re-parses `install_spec` into a `[tool.uv.sources]` table, e.g. a `_parse_git_install_spec`/`_write_install_to_pyproject`-style consumer in `haybale-marketplace/library_manager.py`.

Files:
- `barn/haybale-marketplace/haybale_marketplace/library_manager.py`
- `packages/haywire-studio/src/haywire_studio/packaging/share/marketstall.py`
- `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/commit.py`
- `packages/haywire-studio/src/haywire_studio/init.py`
- `internals/superpowers/2026-07-30-share-wizard.md`

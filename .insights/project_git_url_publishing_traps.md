---
name: Publishing by git URL means consumers get a clone — three silent-corruption traps
description: Haybales install via git+URL clone, so gitignored files vanish, LFS assets become pointer text, and install_spec carries no ref. All three fail silently on the consumer's machine.
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

## 3. `install_spec` carries no ref — consumers always get default-branch HEAD

`_build_entry_for_library` (`packages/haywire-studio/src/haywire_studio/share.py:298`) emits no ref, so a marketstall entry advertising `min_version = "0.3.1"` still installs whatever `master` holds right now. `min_version` is advisory; nothing is reproducible, and a broken default branch immediately breaks every consumer.

Related: the marketstall **share URL** (`_derive_url`, `share.py:816`) and `docs_url`/`examples_url`/`tests_url` (`share.py:317`) all resolve against the *current branch*, not a tag — so those URLs drift as the branch moves.

If you pin `install_spec` to a tag, the `@tag` suffix must **not** end up in the `[tool.uv.sources]` dict's `git` value. Verified: uv treats it as part of the URL path and the clone 404s (`repository 'https://github.com/pypa/packaging.git@24.0/' not found`). It needs a separate key, which uv then locks to a resolved SHA:

```toml
[tool.uv.sources]
packaging = { git = "https://github.com/pypa/packaging.git", tag = "24.0" }
```

PEP 508's `git+URL@tag#subdirectory=` spelling is fine inside `install_spec` itself — but `_parse_git_install_spec` must split the ref out and `_write_install_to_pyproject` (`library_manager.py:87`) must emit it as `tag`.

Files:
- `barn/haybale-marketplace/haybale_marketplace/library_manager.py`
- `packages/haywire-studio/src/haywire_studio/share.py`
- `packages/haywire-studio/src/haywire_studio/init.py`
- `internals/superpowers/2026-07-30-share-wizard.md`

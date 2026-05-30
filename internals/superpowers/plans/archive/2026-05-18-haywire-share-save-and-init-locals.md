# `haywire share --save` & `haywire init` Locals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `haywire share` and `haywire init` into alignment with spec §6–§8 of `internals/specs/versioning-and-publishing.md`. Add a `--save` flag to `haywire share` that aggregates every `barn/*` library into a single root-level `marketstall.toml`. Refactor `haywire init` to register the project's scaffolded library as a `[[locals]]` entry in the user-global marketplace (with G5 name-collision check), update generated templates to `version = "0.0.1"` + `~=` constraints, and rework the project-level marketplace to contain only `[[locals]]` (deferring `[[packages]]` to Plan E's refresh).

**Architecture:** Two independent slices. **Slice 1 (`share --save`):** extends the existing `share_library` helper with an aggregator (`share_save_repo(repo_root)`) that walks `barn/*`, builds a marketstall entry for each library, and writes them to `<repo-root>/marketstall.toml` as one TOML document. **Slice 2 (`init` refactor):** replaces `_generate_project_marketplace` / `_generate_dev_marketplace` with a `[[locals]]`-only emitter; adds a `_register_local_in_global` helper that reads `~/.haywire/marketplace.toml`, refuses if a `[[locals]]` with the same name already exists (G5), and appends the new entry; updates pyproject/library-pyproject templates to `version = "0.0.1"` + `haywire-core~=0.0.1` / `haywire-studio~=0.0.1`. The two slices share no code, but both update `tests/test_init_scaffolding.py` so test-touching commits are grouped.

**Tech Stack:** Python 3.10+, `toml` (already a dep), `pathlib`, `subprocess` (for git remote detection, reused from existing `share.py`). The `haywire.core.marketplace.MarketplaceEntry` dataclass is reused for `[[packages]]` emission in `share --save`. `[[locals]]` entries are written as plain dicts (`name`, `path`, optional `label`/`description`) since `MarketplaceEntry` is the `[[packages]]` schema only — locals have a different shape per spec §6.

**Spec reference:** This plan covers spec **T5** (`haywire share --save`) and **T6** (`haywire init` locals). Also brings the init templates into alignment with **§3** (`version = "0.0.1"`) and **§4** (`~=` constraints). Out of scope: the marketplace runtime / refresh / conflict resolution / Library Manager UI (Plan E covers T7); cleaning the project-level `[[packages]]` that the OLD init wrote (Plan E's refresh will overwrite them).

---

## Approach Rationale (read before starting)

**Why locals get raw-dict serialization, not `MarketplaceEntry`:** Spec §6 says `[[locals]]` entries use a different schema (`name`, `path`, optional metadata) than `[[packages]]`. Reusing `MarketplaceEntry` (which has 11 required-ish fields including `min_version`, `source`, `install_spec`) would either force locals to carry meaningless fields or require a separate locals subclass. The cleanest path: helper functions that emit a plain `dict[str, object]` for locals, parallel to how `share_library` calls `MarketplaceEntry().to_dict()` for packages.

**Why we don't introduce a `LocalEntry` dataclass:** YAGNI. Locals have ~3 fields and one writer (init), no parsers in this plan. A typed dict (`TypedDict`) might pay off in Plan E (which parses locals during refresh), but Plan D's emitter side is fine with `dict[str, object]`. Plan E can introduce a typed parser when it needs one.

**Why the existing project-marketplace file isn't deleted entirely:** Per the user's choice (Q2), we keep the file but make it `[[locals]]`-only. This preserves a contract: every project has `<project>/.haywire/marketplace.toml` from day one, so Plan E's refresh doesn't have to handle a missing-file case. The file contains exactly one `[[locals]]` entry (the project's own library); `[[packages]]` is empty until refresh populates it.

**Why we update the init templates to `0.0.1` + `~=`:** Plan A migrated the monorepo to 0.0.1 with `~=` constraints. Generated user projects must be consistent — `haybale-studio>=0.1.0` would fail `uv sync` once Plan B's CI publishes 0.0.x to PyPI. Updating templates is a tiny edit (4 lines across 2 functions) but keeps the dev/release story coherent.

**Why `share --save` aggregates all `barn/*` libraries:** Spec §8 line 545–552 is explicit: "all entries are aggregated into the single root `marketstall.toml`". Single-library repos and multi-library repos use the same file. This contrasts with the existing no-flag invocation (`haywire share`) which still prints one library's snippet to stdout — that path is preserved for the "give me one quick snippet" use case.

**Why the existing `share_library` is preserved unchanged:** The no-flag command (`haywire share [<library_path>]`) is a useful debugging tool — pipe-friendly stdout output of one library's marketstall block. The new `--save` mode is a layer on top. We refactor only what's needed to share helpers between the two.

**Why we tolerate the dev-mode dev-repo paths leaking into the user-global marketplace:** Spec §8 says `--dev` writes `[[locals]]` entries for "each dev-repo library the user wants to test against". These have absolute paths. If two dev projects point at the same dev-repo directory, both add the same path (different names — `haybale-core` from one project, `haybale-core` from another — wait, same name). G5 catches this: the second `haywire init --dev` would refuse because the user-global already has a `[[locals]] name = "haybale-core"`. The user-facing behavior is: only the first project that runs `init --dev` registers the dev-repo libraries globally; subsequent dev projects use what's already there. Reasonable single-machine-single-dev-checkout assumption per the spec's "dev-mode projects are non-portable by design" note.

---

## File Structure

### Files modified
- `packages/haywire-studio/src/haywire_studio/share.py` — add `share_save_repo(repo_root)`, factor out `_build_entry_for_library(lib_dir)` helper so the existing single-library path and the new save-all path share it. Add CLI plumbing in app.py for `--save`.
- `packages/haywire-studio/src/haywire_studio/init.py` — replace `_generate_project_marketplace` / `_generate_dev_marketplace` with `_generate_project_marketplace_locals_only` (writes the project's `[[locals]]`-only marketplace). Add `_register_local_in_global` (writes to `~/.haywire/marketplace.toml`, raises on G5). Add `_dev_repo_libraries(dev_repo)` for `--dev` to walk the dev-repo's barn/. Update `_generate_project_pyproject` and `_generate_library_pyproject` to use `0.0.1` + `~=` constraints.
- `packages/haywire-studio/src/haywire_studio/app.py` — extend `share_parser` with `--save` flag.
- `tests/test_init_scaffolding.py` — rewrite the marketplace-related tests in `TestDevMode` and `TestProjectStructure` to match the new locals-only model; add tests for G5 collision; update version-assertion fixtures.

### Files created
- `tests/test_share_save.py` — new test file for `haywire share --save` (kept separate from the existing `test_init_scaffolding.py` since the two slices test independent code paths).

### Files NOT touched (out of scope)
- `packages/haywire-core/src/haywire/core/marketplace.py` — `MarketplaceEntry` is reused; no field changes.
- The two-tier marketplace runtime (`[[marketplaces]]`/`[[marketstalls]]` subscriptions, refresh, conflict resolution) — Plan E.
- The Library Manager UI in `barn/haybale-studio/` — Plan E/F.

---

## Self-Review Plan-Time Checks (already performed by author)

- Spec §8 line 532-543 says init writes locals to the user-global marketplace + checks for G5 collision — covered by Task 6 (`_register_local_in_global`) and Task 7 (collision test).
- Spec §8 line 545-552 says `share --save` aggregates all `barn/*` into one root `marketstall.toml` — covered by Tasks 2-3.
- Spec §3+§4 say version 0.0.1 + `~=` — covered by Task 5 (template updates).
- Spec §6 `[[locals]]` schema (name, path, optional metadata) — covered by Task 4's `_local_entry` helper.
- The existing `<project>/.haywire/marketplace.toml` schema is reduced to `[[locals]]`-only per user's Q2 choice — covered by Task 4's `_generate_project_marketplace_locals_only`.

---

## Task list

### Task 1: Baseline verification

**Files:** read-only.

- [ ] **Step 1: Confirm pre-edit baseline is clean**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
git branch --show-current
git log --oneline -3
uv run ruff check .
uv run pytest -m "not integration" -q 2>&1 | tail -3
```

Expected:
- Branch: `feat/versioning-pre-release-and-bump-script`
- Top 3 commits: Plan C squashed (`feat(skill): /haywire-release release-flow playbook`), Plan B squashed (`feat: CI publish workflow + marketstall generator`), Plan A squashed (`feat: versioning migration + bump_version.py script`).
- Ruff: `All checks passed!`
- Pytest: `1156 passed, 1 skipped, 75 deselected`.

If any of these differ, STOP and notify the user — the plan assumes Plans A, B, C are landed.

- [ ] **Step 2: Confirm the existing init/share tests pass**

```bash
uv run pytest tests/test_init_scaffolding.py -v 2>&1 | tail -5
```

Expected: `40 passed`.

- [ ] **Step 3: Confirm the `haywire share` and `haywire init` CLI subcommands exist**

```bash
uv run python -m haywire_studio share --help 2>&1 | head -5
uv run python -m haywire_studio init --help 2>&1 | head -5
```

Expected: both print argparse help.

---

### Task 2: `share` — factor out per-library entry builder

This is a refactor with no behavior change. We pull the entry-building logic out of `share_library` into a reusable helper `_build_entry_for_library(lib_dir)` so the new `share_save_repo` (Task 3) can call it for every barn library.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share.py`

- [ ] **Step 1: Read the current `share_library` function**

Open `packages/haywire-studio/src/haywire_studio/share.py`. The function spans lines 134–219.

The refactor target: lines 145–216 (everything from `pyproject_path = lib_dir / "pyproject.toml"` through the `entry = MarketplaceEntry(...)` block). The print statements at lines 218-219 (`# Copy this snippet ...` + `toml.dumps(...)`) stay in `share_library`.

- [ ] **Step 2: Extract `_build_entry_for_library(lib_dir: Path) -> dict | None`**

Add this function ABOVE `share_library` in `share.py` (after `_detect_library`):

```python
def _build_entry_for_library(lib_dir: Path) -> dict | None:
    """Build a marketplace entry for one library directory.

    Returns the entry dict (TOML-serializable), or None if `lib_dir` lacks a
    pyproject.toml. Used by both `haywire share` (single library, stdout) and
    `haywire share --save` (every barn library, aggregated to file).
    """
    pyproject_path = lib_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    data = toml.loads(pyproject_path.read_text())
    project = data.get("project", {})

    name = project.get("name", lib_dir.name)
    version = project.get("version", "0.0.0")
    description = project.get("description", "")
    tags = project.get("keywords", [])

    authors = project.get("authors", [])
    author = authors[0].get("name", "") if authors else ""

    git_root = _find_git_root(lib_dir)
    remote_url = _get_remote_url(git_root) if git_root else None

    subdirectory: Path | str
    if remote_url:
        assert git_root is not None
        https_url = _ssh_to_https(remote_url)
        https_url = https_url.removesuffix(".git")
        subdirectory = lib_dir.relative_to(git_root)
        install_spec = f"{name} @ git+{https_url}.git#subdirectory={subdirectory}"
    else:
        https_url = ""
        subdirectory = (
            lib_dir.relative_to(Path.cwd()) if lib_dir.is_relative_to(Path.cwd()) else lib_dir.name
        )
        install_spec = f"{name} @ git+https://<REPO_URL>.git#subdirectory={subdirectory}"

    module_dir = _find_module_dir(lib_dir)
    label_fallback = name.removeprefix("haybale-").replace("-", " ").replace("_", " ").title()
    label = _read_library_label(module_dir, label_fallback) if module_dir else label_fallback
    dependencies = _read_library_dependencies(module_dir) if module_dir else []

    docs_url = ""
    if remote_url and module_dir:
        assert git_root is not None
        module_rel = module_dir.relative_to(git_root)
        if "github.com" in https_url:
            raw_base = https_url.replace("github.com", "raw.githubusercontent.com")
            docs_url = f"{raw_base}/main/{module_rel}/"
        elif "gitlab.com" in https_url:
            docs_url = f"{https_url}/-/raw/main/{module_rel}/"

    return MarketplaceEntry(
        name=name,
        label=label,
        min_version=version,
        description=description,
        author=author,
        source="git",
        install_spec=install_spec,
        tags=tags,
        dependencies=dependencies,
        source_url=https_url if remote_url else "",
        docs_url=docs_url,
    ).to_dict()
```

- [ ] **Step 3: Replace `share_library`'s body to call the helper**

Replace the body of `share_library` (the function starting at line 134) with:

```python
def share_library(library_path: str | None):
    """Print a marketplace.toml snippet for the given library directory."""
    if library_path is None:
        lib_dir = _detect_library()
    else:
        lib_dir = Path(library_path).resolve()

    if not lib_dir.is_dir():
        print(f"Error: '{library_path}' is not a directory.")
        sys.exit(1)

    entry = _build_entry_for_library(lib_dir)
    if entry is None:
        print(f"Error: No pyproject.toml found in '{library_path}'.")
        sys.exit(1)

    # Warn when no git remote — the original behavior surfaces this to the user.
    git_root = _find_git_root(lib_dir)
    if not git_root or not _get_remote_url(git_root):
        print("Warning: No git remote found. Using placeholder URL.\n")

    print("# Copy this snippet into a marketplace.toml:\n")
    print(toml.dumps({"packages": [entry]}).strip())
```

- [ ] **Step 4: Run the existing tests to confirm no regression**

There are no tests for `share_library` in the suite today (verified in Task 1), so we'll rely on a manual smoke check:

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run python -m haywire_studio share barn/haybale-haystack 2>&1 | head -20
```

Expected: prints `# Copy this snippet into a marketplace.toml:` followed by a `[[packages]]` block with `name = "haybale-haystack"`, `source = "git"`, etc. Should match what the old code produced (run `git stash; uv run python -m haywire_studio share barn/haybale-haystack > /tmp/before.txt; git stash pop` if you want a side-by-side comparison).

- [ ] **Step 5: Lint and type-check**

```bash
uv run ruff check packages/haywire-studio/
uv run mypy packages/haywire-studio/src/
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/share.py
git commit -m "$(cat <<'EOF'
refactor(share): factor _build_entry_for_library out of share_library

Pulls the per-library marketstall-entry construction into a reusable
helper. share_library now delegates to it; the new helper is also
the building block for the upcoming `haywire share --save` aggregator
(next commit). Pure refactor — no behavior change for the existing
no-flag invocation.

Refs spec internals/specs/versioning-and-publishing.md T5.
EOF
)"
```

---

### Task 3: `share --save` — aggregator + CLI flag (TDD red→green)

Adds the new `share_save_repo(repo_root)` function and the `--save` CLI flag.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share.py`
- Modify: `packages/haywire-studio/src/haywire_studio/app.py`
- Create: `tests/test_share_save.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_share_save.py` with:

```python
"""Tests for `haywire share --save` (aggregates all barn/* libraries into marketstall.toml)."""

from pathlib import Path

import pytest
import toml


@pytest.fixture
def repo_with_two_barn_libs(tmp_path: Path) -> Path:
    """Create a fake repo with two barn libraries under barn/."""
    repo = tmp_path / "fake-repo"
    repo.mkdir()
    (repo / ".git").mkdir()  # Marks it as a git root for share's detector.

    # Library A
    lib_a = repo / "barn" / "haybale-alpha"
    (lib_a / "haybale_alpha").mkdir(parents=True)
    (lib_a / "pyproject.toml").write_text(
        '[project]\n'
        'name = "haybale-alpha"\n'
        'version = "0.0.1"\n'
        'description = "Alpha library"\n'
        'keywords = ["alpha", "demo"]\n'
        'authors = [{name = "Alpha Author"}]\n'
    )
    (lib_a / "haybale_alpha" / "__init__.py").write_text(
        '@library(label="Alpha", id="alpha", dependencies=["haybale_beta"])\n'
        'class Library: pass\n'
    )

    # Library B
    lib_b = repo / "barn" / "haybale-beta"
    (lib_b / "haybale_beta").mkdir(parents=True)
    (lib_b / "pyproject.toml").write_text(
        '[project]\n'
        'name = "haybale-beta"\n'
        'version = "0.0.1"\n'
        'description = "Beta library"\n'
    )
    (lib_b / "haybale_beta" / "__init__.py").write_text(
        '@library(label="Beta", id="beta")\n'
        'class Library: pass\n'
    )

    return repo


def test_share_save_writes_marketstall_at_repo_root(repo_with_two_barn_libs: Path) -> None:
    from haywire_studio.share import share_save_repo

    out_path = share_save_repo(repo_with_two_barn_libs)

    assert out_path == repo_with_two_barn_libs / "marketstall.toml"
    assert out_path.is_file()


def test_share_save_aggregates_all_barn_libraries(repo_with_two_barn_libs: Path) -> None:
    from haywire_studio.share import share_save_repo

    share_save_repo(repo_with_two_barn_libs)

    data = toml.loads((repo_with_two_barn_libs / "marketstall.toml").read_text())
    names = sorted(pkg["name"] for pkg in data["packages"])
    assert names == ["haybale-alpha", "haybale-beta"]


def test_share_save_each_entry_is_source_git(repo_with_two_barn_libs: Path) -> None:
    from haywire_studio.share import share_save_repo

    share_save_repo(repo_with_two_barn_libs)

    data = toml.loads((repo_with_two_barn_libs / "marketstall.toml").read_text())
    for pkg in data["packages"]:
        assert pkg["source"] == "git"


def test_share_save_skips_dirs_without_pyproject(tmp_path: Path) -> None:
    """A directory under barn/ that has no pyproject.toml must be silently skipped."""
    from haywire_studio.share import share_save_repo

    repo = tmp_path / "sparse-repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "barn" / "haybale-alpha").mkdir(parents=True)
    (repo / "barn" / "haybale-alpha" / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.0.1"\ndescription = "a"\n'
    )
    (repo / "barn" / "not-a-library").mkdir(parents=True)
    # not-a-library has no pyproject.toml; share_save_repo must skip it.

    share_save_repo(repo)
    data = toml.loads((repo / "marketstall.toml").read_text())
    names = [pkg["name"] for pkg in data["packages"]]
    assert names == ["haybale-alpha"]


def test_share_save_raises_when_no_barn(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo, NoBarnError

    repo = tmp_path / "no-barn-repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    with pytest.raises(NoBarnError):
        share_save_repo(repo)
```

- [ ] **Step 2: Run, confirm tests FAIL**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run pytest tests/test_share_save.py -v
```

Expected: 5 tests fail with `ImportError: cannot import name 'share_save_repo' from 'haywire_studio.share'` (or `NoBarnError`).

- [ ] **Step 3: Implement `share_save_repo` and `NoBarnError`**

Append to `packages/haywire-studio/src/haywire_studio/share.py`:

```python
class NoBarnError(RuntimeError):
    """Raised when `share --save` is invoked on a repo with no `barn/` directory."""


def share_save_repo(repo_root: Path) -> Path:
    """Aggregate every library under `<repo_root>/barn/*` into one marketstall.toml.

    Walks `barn/*` (sorted), builds a marketplace entry for each directory that
    contains a `pyproject.toml` (via `_build_entry_for_library`), and writes the
    aggregated list to `<repo_root>/marketstall.toml`. Directories without a
    pyproject are silently skipped. Returns the output path.

    Raises NoBarnError if `<repo_root>/barn/` doesn't exist.
    """
    barn = repo_root / "barn"
    if not barn.is_dir():
        raise NoBarnError(f"no barn/ directory at {repo_root}")

    entries: list[dict] = []
    for lib_dir in sorted(barn.iterdir()):
        if not lib_dir.is_dir():
            continue
        entry = _build_entry_for_library(lib_dir)
        if entry is None:
            continue
        entries.append(entry)

    out_path = repo_root / "marketstall.toml"
    header = (
        "# marketstall.toml — share this file's raw URL so others can subscribe to your library feed\n"
        "# Run: haywire share --save   to update this file\n\n"
    )
    out_path.write_text(header + toml.dumps({"packages": entries}))
    return out_path
```

- [ ] **Step 4: Run tests, confirm GREEN**

```bash
uv run pytest tests/test_share_save.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Add the `--save` CLI flag**

Open `packages/haywire-studio/src/haywire_studio/app.py`. Find the `share_parser` block (around line 303-312):

```python
    share_parser = subparsers.add_parser(
        "share", help="Generate a marketplace.toml snippet for sharing a library"
    )
    share_parser.add_argument(
        "library_path",
        nargs="?",
        default=None,
        help="Path to the library directory (e.g. libs/haybale-myproject). "
        "Auto-detected if libs/ contains exactly one library.",
    )
```

Append a new `--save` argument inside `share_parser`:

```python
    share_parser.add_argument(
        "--save",
        action="store_true",
        help="Aggregate every barn/* library into <repo-root>/marketstall.toml.",
    )
```

Find the `if args.command == "share":` branch (around line 321-324):

```python
    elif args.command == "share":
        from .share import share_library

        share_library(args.library_path)
```

Replace it with:

```python
    elif args.command == "share":
        if args.save:
            from pathlib import Path

            from .share import share_save_repo, NoBarnError

            try:
                out_path = share_save_repo(Path.cwd())
                print(f"Wrote {out_path}")
            except NoBarnError as exc:
                print(f"Error: {exc}")
                sys.exit(1)
        else:
            from .share import share_library

            share_library(args.library_path)
```

Also add `import sys` near the top of `app.py` if not already present. Verify with `grep -n "^import sys" packages/haywire-studio/src/haywire_studio/app.py`.

- [ ] **Step 6: Smoke-test against the live monorepo**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run python -m haywire_studio share --save
ls -la marketstall.toml
head -5 marketstall.toml
```

Expected: prints `Wrote .../marketstall.toml`, the file exists at the repo root, starts with the header comment + `[[packages]]` blocks. Verify by parsing:

```bash
uv run python -c "
import tomllib, pathlib
data = tomllib.loads(pathlib.Path('marketstall.toml').read_text())
print(f'{len(data[\"packages\"])} packages')
for p in data['packages']:
    print(f'  {p[\"name\"]:30s} source={p[\"source\"]}')
"
```

Expected: 8 packages (the 8 barn/haybale-* libraries in this monorepo: `haybale-TEST_A`, `haybale-core`, `haybale-example`, `haybale-graph-editor`, `haybale-haystack`, `haybale-studio`, `haybale-testing`, `haybale-visiongraph`). Each `source=git`.

Clean up:

```bash
rm marketstall.toml
```

- [ ] **Step 7: Lint and type-check**

```bash
uv run ruff check packages/haywire-studio/ tests/test_share_save.py
uv run mypy packages/haywire-studio/src/
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/share.py \
        packages/haywire-studio/src/haywire_studio/app.py \
        tests/test_share_save.py
git commit -m "$(cat <<'EOF'
feat(share): add --save to aggregate every barn/* into marketstall.toml

Adds share_save_repo() that walks <repo_root>/barn/*, builds a
[[packages]] entry for each library (reusing _build_entry_for_library
from the previous commit), and writes them to
<repo_root>/marketstall.toml. The single-library `haywire share`
invocation (stdout) is unchanged. Spec §8 says the marketstall lives
at the repo root regardless of project structure; for projects with
multiple barn libraries, entries aggregate into the single root file.

Five new unit tests cover the happy path, multi-library aggregation,
source=git invariant, skipping directories without pyproject, and
the NoBarnError when barn/ doesn't exist.

Refs spec internals/specs/versioning-and-publishing.md T5, §8.
EOF
)"
```

---

### Task 4: `init` — locals-only project marketplace + `[[locals]]` helper (TDD red→green)

Refactors the existing `_generate_project_marketplace` / `_generate_dev_marketplace` to emit a `[[locals]]`-only project marketplace, plus introduces a `_local_entry` helper for the dict shape used by both the project marketplace and (in Task 6) the user-global marketplace.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/init.py`
- Modify: `tests/test_init_scaffolding.py`

- [ ] **Step 1: Write failing tests for the new behavior**

Open `tests/test_init_scaffolding.py`. Replace the entire `TestDevMode` class (lines 163-212) with the new tests below, AND add a new `TestProjectMarketplace` class for the non-dev path. Old vs new behavior:

- **Old:** `<project>/.haywire/marketplace.toml` contained either just the project's library (`source = "local"` as a `[[packages]]` entry) or the project library + every dev-repo library (also as `[[packages]]`).
- **New:** `<project>/.haywire/marketplace.toml` contains ONLY a `[[locals]]` section with the project's own library. No `[[packages]]`. The user-global marketplace (`~/.haywire/marketplace.toml`) gets `[[locals]]` entries — covered in Task 6.

Replace the entire `TestDevMode` class with this new content (keeping the existing fixtures `scaffold_project` and `scaffold_project_dev` at the top of the file unchanged):

```python
class TestProjectMarketplace:
    """The project's <project>/.haywire/marketplace.toml contains [[locals]] only."""

    def test_project_marketplace_exists(self, scaffold_project):
        assert (scaffold_project / ".haywire" / "marketplace.toml").is_file()

    def test_project_marketplace_has_one_local(self, scaffold_project):
        data = toml.loads((scaffold_project / ".haywire" / "marketplace.toml").read_text())
        locals_ = data.get("locals", [])
        assert len(locals_) == 1
        assert locals_[0]["name"] == "haybale-test-project"

    def test_project_marketplace_local_path_is_absolute(self, scaffold_project):
        data = toml.loads((scaffold_project / ".haywire" / "marketplace.toml").read_text())
        path = data["locals"][0]["path"]
        assert Path(path).is_absolute()
        assert Path(path) == scaffold_project / "barn" / "haybale-test-project"

    def test_project_marketplace_has_no_packages(self, scaffold_project):
        """No [[packages]] section — refresh (Plan E) populates that."""
        data = toml.loads((scaffold_project / ".haywire" / "marketplace.toml").read_text())
        assert data.get("packages", []) == []


class TestDevMode:
    """`haywire init --dev` adds editable source paths to the generated pyprojects."""

    def test_project_has_sources(self, scaffold_project_dev):
        data = toml.loads((scaffold_project_dev / "pyproject.toml").read_text())
        sources = data["tool"]["uv"]["sources"]
        assert "haywire-studio" in sources
        assert "haywire-core" in sources
        assert "haybale-core" in sources
        assert "haybale-studio" in sources

    def test_sources_are_editable(self, scaffold_project_dev):
        data = toml.loads((scaffold_project_dev / "pyproject.toml").read_text())
        for pkg in ["haywire-studio", "haywire-core"]:
            assert data["tool"]["uv"]["sources"][pkg]["editable"] is True

    def test_source_paths_exist(self, scaffold_project_dev):
        data = toml.loads((scaffold_project_dev / "pyproject.toml").read_text())
        for pkg in ["haywire-studio", "haywire-core"]:
            assert Path(data["tool"]["uv"]["sources"][pkg]["path"]).is_dir()

    def test_library_has_framework_source(self, scaffold_project_dev):
        data = toml.loads(
            (scaffold_project_dev / "barn" / "haybale-test-project-dev" / "pyproject.toml").read_text()
        )
        sources = data["tool"]["uv"]["sources"]
        assert "haywire-core" in sources
        assert sources["haywire-core"]["editable"] is True

    def test_dev_project_marketplace_still_locals_only(self, scaffold_project_dev):
        """Even in --dev mode, the PROJECT marketplace is just the project's library.
        Dev-repo libraries go to the user-global marketplace (tested in TestUserGlobalRegistration)."""
        data = toml.loads((scaffold_project_dev / ".haywire" / "marketplace.toml").read_text())
        locals_ = data.get("locals", [])
        assert len(locals_) == 1
        assert locals_[0]["name"] == "haybale-test-project-dev"
        assert data.get("packages", []) == []
```

- [ ] **Step 2: Run, confirm the new tests FAIL**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run pytest tests/test_init_scaffolding.py -v 2>&1 | tail -20
```

Expected: roughly 34-36 pass (the unchanged scaffolding tests), 6-8 fail in `TestProjectMarketplace` and `TestDevMode`. The failures should mention either `packages` (the old code writes `[[packages]]` not `[[locals]]`) or `KeyError` on `locals`.

- [ ] **Step 3: Implement `_local_entry` and rewrite the marketplace generators**

Open `packages/haywire-studio/src/haywire_studio/init.py`. Find `_project_lib_entry` (lines 235-247) and `_generate_project_marketplace` (lines 250-268) and `_generate_dev_marketplace` (lines 271-362).

Replace ALL THREE of those functions with this:

```python
def _local_entry(name: str, path: Path, label: str = "", description: str = "") -> dict:
    """Build a [[locals]] entry per spec §6.

    Locals have a different schema than [[packages]]: only `name` and `path` are
    required; label and description are optional metadata. Locals are always
    installed editably from the path; they're never published.
    """
    entry: dict[str, object] = {
        "name": name,
        "path": str(path),
    }
    if label:
        entry["label"] = label
    if description:
        entry["description"] = description
    return entry


def _generate_project_marketplace_locals_only(name: str, project_dir: Path) -> str:
    """Generate <project>/.haywire/marketplace.toml with the project's library only.

    Per spec §6, the project marketplace has [[locals]] (the project's own library,
    written here at init time) and [[packages]] (populated by refresh — Plan E).
    This emitter writes [[locals]] only; the [[packages]] section is empty.
    """
    label = name.replace("-", " ").replace("_", " ").title()
    entry = _local_entry(
        name=f"haybale-{name}",
        path=project_dir / "barn" / f"haybale-{name}",
        label=label,
        description=f"Local library for the {name} project",
    )
    header = (
        "# Project marketplace — managed by haywire.\n"
        "# [[locals]] are project-scoped editable libraries, written at `haywire init` time.\n"
        "# [[packages]] is the cache populated by the Library Manager's refresh action;\n"
        "# leave it empty here until you've added remote sources to ~/.haywire/marketplace.toml.\n\n"
    )
    return header + toml.dumps({"locals": [entry]})
```

(Delete `_project_lib_entry`, `_generate_project_marketplace`, `_generate_dev_marketplace`.)

Then find where `init_project` writes the project marketplace (around lines 423-427):

```python
    # Marketplace manifest — always written; dev variant includes dev-repo libs
    if dev_repo:
        marketplace = _generate_dev_marketplace(dev_repo, name, module_name, project_dir)
    else:
        marketplace = _generate_project_marketplace(name, module_name, project_dir)
    (project_dir / ".haywire" / "marketplace.toml").write_text(marketplace)
```

Replace with:

```python
    # Project marketplace — locals-only (the project's scaffolded library).
    # Dev-repo libraries (in --dev mode) are registered in the user-global
    # marketplace instead, by _register_local_in_global below.
    (project_dir / ".haywire" / "marketplace.toml").write_text(
        _generate_project_marketplace_locals_only(name, project_dir)
    )
```

- [ ] **Step 4: Run, confirm GREEN**

```bash
uv run pytest tests/test_init_scaffolding.py -v 2>&1 | tail -10
```

Expected: all tests pass (~38-40, depending on which ones we removed/added).

- [ ] **Step 5: Lint + type-check**

```bash
uv run ruff check packages/haywire-studio/ tests/test_init_scaffolding.py
uv run mypy packages/haywire-studio/src/
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/init.py tests/test_init_scaffolding.py
git commit -m "$(cat <<'EOF'
feat(init): project marketplace is now [[locals]]-only

Replaces _generate_project_marketplace / _generate_dev_marketplace
with _generate_project_marketplace_locals_only — emits the project's
own library as a [[locals]] entry, no [[packages]]. Refresh (Plan E)
will populate [[packages]] later from subscribed sources.

Introduces _local_entry helper for the [[locals]] schema (name +
path + optional metadata, per spec §6) — used here for the project
marketplace and by the next commit for the user-global registration.

Updates test_init_scaffolding.py TestDevMode + adds new
TestProjectMarketplace; the old dev-marketplace-lists-all-libs tests
are removed because dev-repo libraries now belong in the user-global
marketplace.

Refs spec internals/specs/versioning-and-publishing.md T6, §6, §8.
EOF
)"
```

---

### Task 5: `init` — update generated templates to `0.0.1` + `~=` constraints

Plan A migrated the monorepo to `0.0.1` + `~=`. The generated project/library templates in `init.py` still write `version = "0.1.0"` and `>=0.1.0` constraints, which would fail `uv sync` once Plan B publishes 0.0.x packages to PyPI. This task brings the templates into alignment.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/init.py`
- Modify: `tests/test_init_scaffolding.py`

- [ ] **Step 1: Update the version assertions in existing tests**

In `tests/test_init_scaffolding.py`, the `test_dependencies` test (around lines 88-92) currently checks:

```python
    def test_dependencies(self, scaffold_project):
        data = toml.loads((scaffold_project / "pyproject.toml").read_text())
        deps = data["project"]["dependencies"]
        assert "haywire-studio>=0.1.0" in deps
        assert "haybale-core>=1.0.0" not in deps
```

Update to:

```python
    def test_dependencies(self, scaffold_project):
        data = toml.loads((scaffold_project / "pyproject.toml").read_text())
        deps = data["project"]["dependencies"]
        assert "haywire-studio~=0.0.1" in deps
        assert "haybale-core>=1.0.0" not in deps
```

And the `test_library_dependency` test (lines 108-112):

```python
    def test_library_dependency(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / "barn" / "haybale-test-project" / "pyproject.toml").read_text()
        )
        assert "haywire-core>=0.1.0" in data["project"]["dependencies"]
```

Update to:

```python
    def test_library_dependency(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / "barn" / "haybale-test-project" / "pyproject.toml").read_text()
        )
        assert "haywire-core~=0.0.1" in data["project"]["dependencies"]
```

Also add a new test in the `TestLibraryPyproject` class to assert the version:

```python
    def test_library_version_is_release(self, scaffold_project):
        data = toml.loads(
            (scaffold_project / "barn" / "haybale-test-project" / "pyproject.toml").read_text()
        )
        assert data["project"]["version"] == "0.0.1"
```

- [ ] **Step 2: Run, confirm the version tests FAIL**

```bash
uv run pytest tests/test_init_scaffolding.py::TestProjectPyproject::test_dependencies tests/test_init_scaffolding.py::TestLibraryPyproject::test_library_dependency tests/test_init_scaffolding.py::TestLibraryPyproject::test_library_version_is_release -v
```

Expected: all 3 fail. The first two will report `assertion: haywire-studio~=0.0.1 in [...]` failing because the deps list still contains `haywire-studio>=0.1.0`. The third will fail on `data["project"]["version"]` being `"0.1.0"`.

- [ ] **Step 3: Update `_generate_project_pyproject`**

In `packages/haywire-studio/src/haywire_studio/init.py`, find `_generate_project_pyproject` (around lines 42-83). The dependencies dict has:

```python
            "dependencies": [
                "haywire-studio>=0.1.0",
                lib_name,
            ],
```

Update to:

```python
            "dependencies": [
                "haywire-studio~=0.0.1",
                lib_name,
            ],
```

(The dev-mode addition that appends `"haybale-core", "haybale-studio"` to dependencies — those are bare names, no version, so they don't need updating. uv resolves them via `[tool.uv.sources]` in dev mode.)

- [ ] **Step 4: Update `_generate_library_pyproject`**

Find `_generate_library_pyproject` (around lines 86-120). It contains:

```python
    return f'''[project]
name = "{lib_name}"
version = "0.1.0"
description = "Local library for {name} project"
requires-python = ">=3.10"
license = {{text = "MIT"}}

dependencies = ["haywire-core>=0.1.0"]
```

Update both lines:

```python
    return f'''[project]
name = "{lib_name}"
version = "0.0.1"
description = "Local library for {name} project"
requires-python = ">=3.10"
license = {{text = "MIT"}}

dependencies = ["haywire-core~=0.0.1"]
```

- [ ] **Step 5: Update `_generate_library_init` if it references the version**

Open `_generate_library_init` (around lines 123-232). It uses `_pkg_version('haybale-{name}')` for `version=` in the `@library` decorator, which is the right pattern (reads at runtime from `importlib.metadata`). Verify there's no hardcoded `0.1.0` string anywhere in this function:

```bash
grep -n '0\.1\.0' packages/haywire-studio/src/haywire_studio/init.py
```

Expected: NO matches after Steps 3-4. If any remain, update them to `0.0.1`.

- [ ] **Step 6: Run all init tests, confirm GREEN**

```bash
uv run pytest tests/test_init_scaffolding.py -v 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 7: Smoke-test by scaffolding a real project**

```bash
cd /tmp
rm -rf /tmp/test-init-d/
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run python -c "
import os
os.chdir('/tmp')
from haywire_studio.init import init_project
init_project('test-init-d', auto_sync=False)
"
echo "--- generated project pyproject ---"
grep -E '~=|>=' /tmp/test-init-d/pyproject.toml
echo "--- generated library pyproject ---"
grep -E '^version|~=|>=' /tmp/test-init-d/barn/haybale-test-init-d/pyproject.toml
rm -rf /tmp/test-init-d/
```

Expected:
- Project pyproject dependencies show `haywire-studio~=0.0.1`.
- Library pyproject shows `version = "0.0.1"` and `haywire-core~=0.0.1`.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/init.py tests/test_init_scaffolding.py
git commit -m "$(cat <<'EOF'
feat(init): generated templates use 0.0.1 + ~= per Plan A convention

Aligns the init scaffolding templates with the monorepo's release
versioning (Plan A migrated all packages to 0.0.1 with ~= constraints
on inter-package deps). Generated user projects now use:
  - version = "0.0.1" for the scaffolded library
  - haywire-studio~=0.0.1 in project deps
  - haywire-core~=0.0.1 in library deps

Without this, generated projects would fail `uv sync` once Plan B
publishes 0.0.x packages to PyPI — there's no 0.1.x to resolve.

Refs spec internals/specs/versioning-and-publishing.md §3, §4, T6.
EOF
)"
```

---

### Task 6: `init` — register `[[locals]]` in the user-global marketplace + G5 check (TDD red→green)

Per spec §8, `haywire init` writes a `[[locals]]` entry to `~/.haywire/marketplace.toml` for the scaffolded project's library. If a `[[locals]]` with the same `name` already exists, the init refuses with an error (G5 — name collision between projects).

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/init.py`
- Modify: `tests/test_init_scaffolding.py`

- [ ] **Step 1: Write failing tests**

The tests need to control where `~/.haywire/` resolves to (so they don't pollute the user's real config). The existing `scaffold_project` fixture uses `monkeypatch.chdir` but doesn't redirect `Path.home()`. Add a new fixture that does.

Append to `tests/test_init_scaffolding.py` (after the existing fixtures, before the test classes):

```python
@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect Path.home() to a tmp dir so user-global config writes are sandboxed.

    Also patches haywire_studio.config.GLOBAL_CONFIG_DIR which is captured
    at module-import time from Path.home() — without this patch, the module
    keeps pointing at the real home directory.
    """
    fake = tmp_path / "fake-home"
    fake.mkdir()
    monkeypatch.setenv("HOME", str(fake))
    monkeypatch.setattr("pathlib.Path.home", lambda: fake)
    import haywire_studio.config as cfg

    monkeypatch.setattr(cfg, "GLOBAL_CONFIG_DIR", fake / ".haywire")
    return fake


@pytest.fixture
def scaffold_project_with_fake_home(tmp_path, monkeypatch, fake_home):
    """Like scaffold_project, but with a sandboxed user-global home."""
    monkeypatch.chdir(tmp_path)
    from haywire_studio.init import init_project

    init_project("test-project", auto_sync=False)
    return tmp_path / "test-project"
```

Append a new test class to the end of `tests/test_init_scaffolding.py`:

```python
class TestUserGlobalRegistration:
    """`haywire init` writes a [[locals]] entry to ~/.haywire/marketplace.toml."""

    def test_user_global_marketplace_exists_after_init(self, scaffold_project_with_fake_home, fake_home):
        global_mp = fake_home / ".haywire" / "marketplace.toml"
        assert global_mp.is_file()

    def test_user_global_has_local_for_project(self, scaffold_project_with_fake_home, fake_home):
        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        locals_ = data.get("locals", [])
        names = [entry["name"] for entry in locals_]
        assert "haybale-test-project" in names

    def test_user_global_local_path_is_absolute_to_project(
        self, scaffold_project_with_fake_home, fake_home
    ):
        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        local = next(e for e in data["locals"] if e["name"] == "haybale-test-project")
        assert Path(local["path"]).is_absolute()
        assert "test-project" in local["path"]
        assert local["path"].endswith("barn/haybale-test-project")


class TestG5NameCollision:
    """`haywire init` refuses if a [[locals]] with the same name already exists."""

    def test_second_init_with_same_name_refused(self, tmp_path, monkeypatch, fake_home):
        from haywire_studio.init import init_project

        # First project at /tmp/a/test-project
        a = tmp_path / "a"
        a.mkdir()
        monkeypatch.chdir(a)
        init_project("test-project", auto_sync=False)

        # Second project trying to claim the same library name at /tmp/b/test-project
        b = tmp_path / "b"
        b.mkdir()
        monkeypatch.chdir(b)
        with pytest.raises(SystemExit) as exc_info:
            init_project("test-project", auto_sync=False)

        assert exc_info.value.code != 0

    def test_collision_does_not_create_second_project_dir(self, tmp_path, monkeypatch, fake_home):
        from haywire_studio.init import init_project

        a = tmp_path / "a"
        a.mkdir()
        monkeypatch.chdir(a)
        init_project("test-project", auto_sync=False)

        b = tmp_path / "b"
        b.mkdir()
        monkeypatch.chdir(b)
        with pytest.raises(SystemExit):
            init_project("test-project", auto_sync=False)

        # Verify the second project's directory was not created (or was rolled back).
        assert not (b / "test-project").exists()
```

- [ ] **Step 2: Run, confirm tests FAIL**

```bash
uv run pytest tests/test_init_scaffolding.py::TestUserGlobalRegistration tests/test_init_scaffolding.py::TestG5NameCollision -v
```

Expected: all 5 tests fail. The first three because no `[[locals]]` is being written to the user-global; the last two because there's no collision check (the second init succeeds).

- [ ] **Step 3: Implement `_register_local_in_global` + the G5 collision check**

Add to `packages/haywire-studio/src/haywire_studio/init.py` near the top (after the imports, before `_get_dev_repo_root`):

```python
class ProjectNameCollisionError(RuntimeError):
    """Raised when haywire init would create a [[locals]] whose name already exists in the user-global marketplace."""
```

Add this helper after `_local_entry` (which Task 4 already added):

```python
def _register_local_in_global(name: str, project_dir: Path) -> None:
    """Append a [[locals]] entry for this project to ~/.haywire/marketplace.toml.

    Refuses with ProjectNameCollisionError if a [[locals]] entry with the same
    name already exists (spec § 6 G5 — name collision between projects).

    Reads/writes via haywire_studio.config.GLOBAL_CONFIG_DIR so tests can patch
    the location.
    """
    from .config import GLOBAL_CONFIG_DIR, ensure_global_config

    ensure_global_config()
    global_mp = GLOBAL_CONFIG_DIR / "marketplace.toml"
    data = toml.loads(global_mp.read_text())

    locals_ = data.get("locals", [])
    label = name.replace("-", " ").replace("_", " ").title()
    new_entry = _local_entry(
        name=f"haybale-{name}",
        path=project_dir / "barn" / f"haybale-{name}",
        label=label,
        description=f"Local library for the {name} project",
    )

    for existing in locals_:
        if existing.get("name") == new_entry["name"]:
            raise ProjectNameCollisionError(
                f'A project library named "{new_entry["name"]}" is already registered '
                f'at {existing.get("path")} in the user-global marketplace. '
                f"Rename your new project or remove the conflicting entry from "
                f"{global_mp}."
            )

    locals_.append(new_entry)
    data["locals"] = locals_
    global_mp.write_text(toml.dumps(data))
```

- [ ] **Step 4: Wire `_register_local_in_global` into `init_project` (with collision check first)**

Open `init_project` (around line 365). Find the section just before the directory creation (around line 374-377):

```python
    project_dir = Path.cwd() / name

    if project_dir.exists():
        print(f"Error: Directory '{name}' already exists.")
        sys.exit(1)
```

Insert the G5 check BEFORE creating any directories — we want to fail fast without leaving a partial project on disk:

```python
    project_dir = Path.cwd() / name

    if project_dir.exists():
        print(f"Error: Directory '{name}' already exists.")
        sys.exit(1)

    # G5 collision check (spec §6) — refuse if a [[locals]] with the same name
    # already exists in the user-global marketplace.
    try:
        _check_global_collision(name)
    except ProjectNameCollisionError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
```

Add this small helper next to `_register_local_in_global` (it's the read-only pre-check that doesn't write):

```python
def _check_global_collision(name: str) -> None:
    """Raise ProjectNameCollisionError if `haybale-{name}` is already in the user-global locals."""
    from .config import GLOBAL_CONFIG_DIR, ensure_global_config

    ensure_global_config()
    global_mp = GLOBAL_CONFIG_DIR / "marketplace.toml"
    data = toml.loads(global_mp.read_text())
    locals_ = data.get("locals", [])
    target_name = f"haybale-{name}"
    for existing in locals_:
        if existing.get("name") == target_name:
            raise ProjectNameCollisionError(
                f'A project library named "{target_name}" is already registered '
                f'at {existing.get("path")} in the user-global marketplace. '
                f"Rename your new project or remove the conflicting entry from "
                f"{global_mp}."
            )
```

(Yes, the collision logic is duplicated between `_check_global_collision` and `_register_local_in_global`. Acceptable for this small case: the pre-check has to read-only-look before any disk writes happen, and the actual write does its own check to defend against a race. Eight lines of duplication beats threading a "should-I-check?" parameter.)

Finally, near the end of `init_project` (after the project marketplace is written, around line 427), add the user-global registration:

```python
    # Project marketplace — locals-only (from Task 4)
    (project_dir / ".haywire" / "marketplace.toml").write_text(
        _generate_project_marketplace_locals_only(name, project_dir)
    )

    # Register the project's library in the user-global marketplace so the
    # Library Manager (and other haywire installs) can find it.
    _register_local_in_global(name, project_dir)
```

(Place this AFTER `ensure_global_config()` and AFTER the project's own marketplace is written. The order matters because Plan A's `add_recent_project` already calls `ensure_global_config` — we just want to make sure the user-global file exists before we try to read/write it.)

- [ ] **Step 5: Run all init tests, confirm GREEN**

```bash
uv run pytest tests/test_init_scaffolding.py -v 2>&1 | tail -15
```

Expected: all tests pass.

- [ ] **Step 6: Sanity-check via the full test suite (no regressions)**

```bash
uv run pytest -m "not integration" -q 2>&1 | tail -3
```

Expected: `1167 passed` or thereabouts (1156 baseline + 5 from Task 3's test_share_save + ~6 net from test_init_scaffolding changes). Any failure is a real regression — STOP and report.

- [ ] **Step 7: Lint + type-check**

```bash
uv run ruff check packages/haywire-studio/ tests/
uv run mypy packages/haywire-studio/src/
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/init.py tests/test_init_scaffolding.py
git commit -m "$(cat <<'EOF'
feat(init): register scaffolded library in user-global marketplace + G5 check

`haywire init` now writes a [[locals]] entry to
~/.haywire/marketplace.toml for the scaffolded project's library
(spec §8 line 532-538). Before any disk writes, checks for a name
collision (spec §6 G5): if another [[locals]] already uses the same
project library name, refuses with a clear error directing the user
to rename the new project or remove the conflicting entry.

ProjectNameCollisionError is raised both by the pre-flight
_check_global_collision (read-only, blocks bad init early) and by
_register_local_in_global (defends against concurrent writes).

Tests use a fake_home fixture that patches Path.home() and
GLOBAL_CONFIG_DIR so user-global writes are sandboxed to tmp_path.

Refs spec internals/specs/versioning-and-publishing.md T6, §6, §8.
EOF
)"
```

---

### Task 7: `init --dev` — register dev-repo libraries in user-global as `[[locals]]`

Per spec §8, `haywire init --dev` additionally writes `[[locals]]` entries for each dev-repo library the user wants to test against. This task adds that step.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/init.py`
- Modify: `tests/test_init_scaffolding.py`

- [ ] **Step 1: Write failing tests**

Append a new test class to `tests/test_init_scaffolding.py`:

```python
class TestDevModeUserGlobalRegistration:
    """`haywire init --dev` also registers dev-repo libraries in the user-global marketplace."""

    @pytest.fixture
    def scaffold_dev_with_fake_home(self, tmp_path, monkeypatch, fake_home):
        monkeypatch.chdir(tmp_path)
        from haywire_studio.init import _get_dev_repo_root, init_project

        init_project("test-dev-project", auto_sync=False, dev_repo=_get_dev_repo_root())
        return tmp_path / "test-dev-project"

    def test_user_global_has_all_dev_repo_libraries(
        self, scaffold_dev_with_fake_home, fake_home
    ):
        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        names = {entry["name"] for entry in data.get("locals", [])}

        # The project's own library:
        assert "haybale-test-dev-project" in names

        # The dev-repo libraries:
        for dev_lib in [
            "haybale-core",
            "haybale-studio",
            "haybale-graph-editor",
            "haybale-haystack",
            "haybale-example",
            "haybale-testing",
            "haybale-visiongraph",
            "haybale-TEST_A",
        ]:
            assert dev_lib in names, f"missing dev-repo library: {dev_lib}"

    def test_dev_locals_paths_point_at_dev_repo(self, scaffold_dev_with_fake_home, fake_home):
        from haywire_studio.init import _get_dev_repo_root

        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        dev_root = _get_dev_repo_root()

        for entry in data["locals"]:
            if entry["name"] == "haybale-test-dev-project":
                continue   # The project's own library lives in the project, not the dev repo
            path = entry["path"]
            assert path.startswith(dev_root), f"{entry['name']}: {path} not under {dev_root}"
            assert Path(path).is_dir(), f"{entry['name']}: {path} does not exist"

    def test_regular_init_does_not_register_dev_repo_libraries(
        self, scaffold_project_with_fake_home, fake_home
    ):
        """Without --dev, only the project's own library should appear."""
        data = toml.loads((fake_home / ".haywire" / "marketplace.toml").read_text())
        names = [entry["name"] for entry in data.get("locals", [])]
        assert names == ["haybale-test-project"]
```

- [ ] **Step 2: Run, confirm tests FAIL**

```bash
uv run pytest tests/test_init_scaffolding.py::TestDevModeUserGlobalRegistration -v
```

Expected: 2 of the 3 fail (the dev-repo-library tests). The "regular init does not register" test should already pass since the previous task only registers the project's own library.

- [ ] **Step 3: Implement dev-repo library registration**

In `packages/haywire-studio/src/haywire_studio/init.py`, add a helper after `_register_local_in_global`:

```python
def _register_dev_repo_locals_in_global(dev_repo: str) -> None:
    """In --dev mode, register every dev-repo barn library as a [[locals]] in the user-global marketplace.

    Walks `<dev_repo>/barn/*` and adds a [[locals]] entry for each directory
    with a pyproject.toml. Entries that already exist (by name) in the user-
    global marketplace are skipped silently — this is idempotent so multiple
    --dev projects on the same machine don't double-register or fail.
    """
    from .config import GLOBAL_CONFIG_DIR, ensure_global_config

    ensure_global_config()
    global_mp = GLOBAL_CONFIG_DIR / "marketplace.toml"
    data = toml.loads(global_mp.read_text())
    locals_ = data.get("locals", [])
    existing_names = {entry.get("name") for entry in locals_}

    barn = Path(dev_repo) / "barn"
    if not barn.is_dir():
        return

    for lib_dir in sorted(barn.iterdir()):
        if not lib_dir.is_dir() or not (lib_dir / "pyproject.toml").exists():
            continue
        # Read the package name from pyproject — don't trust the directory name.
        pyproject = toml.loads((lib_dir / "pyproject.toml").read_text())
        lib_name = pyproject.get("project", {}).get("name", lib_dir.name)
        if lib_name in existing_names:
            continue   # Idempotent: already registered, leave it alone.

        label = lib_name.removeprefix("haybale-").replace("-", " ").replace("_", " ").title()
        description = pyproject.get("project", {}).get("description", "")
        locals_.append(
            _local_entry(
                name=lib_name,
                path=lib_dir,
                label=label,
                description=description,
            )
        )
        existing_names.add(lib_name)

    data["locals"] = locals_
    global_mp.write_text(toml.dumps(data))
```

Then wire it into `init_project`. After the existing `_register_local_in_global(name, project_dir)` call (added in Task 6), add:

```python
    _register_local_in_global(name, project_dir)

    if dev_repo:
        _register_dev_repo_locals_in_global(dev_repo)
```

- [ ] **Step 4: Run all init tests, confirm GREEN**

```bash
uv run pytest tests/test_init_scaffolding.py -v 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 5: Smoke-test via real --dev scaffold**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
rm -rf /tmp/test-init-dev-smoke/
# Sandbox the global marketplace by exporting HOME — uses the existing config.GLOBAL_CONFIG_DIR which is captured at import time.
# For a quick smoke test we accept that this DOES write to ~/.haywire — back it up first.
[ -f ~/.haywire/marketplace.toml ] && cp ~/.haywire/marketplace.toml ~/.haywire/marketplace.toml.bak.beforetask7
cd /tmp
uv run --project /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo python -m haywire_studio init test-init-dev-smoke --no-sync --dev
echo "--- user-global marketplace ---"
cat ~/.haywire/marketplace.toml
echo
echo "--- project marketplace ---"
cat /tmp/test-init-dev-smoke/.haywire/marketplace.toml
# Restore the user's pre-test marketplace:
[ -f ~/.haywire/marketplace.toml.bak.beforetask7 ] && mv ~/.haywire/marketplace.toml.bak.beforetask7 ~/.haywire/marketplace.toml
rm -rf /tmp/test-init-dev-smoke/
```

Expected:
- User-global shows `[[locals]]` entries for `haybale-test-init-dev-smoke` (the project) + all 8 dev-repo libraries (`haybale-core`, `haybale-studio`, etc.).
- Project marketplace contains only one `[[locals]]` entry (the project's own library) and an empty `[[packages]]`.

- [ ] **Step 6: Lint + type-check**

```bash
uv run ruff check packages/haywire-studio/ tests/
uv run mypy packages/haywire-studio/src/
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/init.py tests/test_init_scaffolding.py
git commit -m "$(cat <<'EOF'
feat(init): --dev registers dev-repo libraries in user-global marketplace

Per spec §8 line 540-543, `haywire init --dev` additionally writes
[[locals]] entries for each dev-repo barn library to
~/.haywire/marketplace.toml. Walks <dev_repo>/barn/*, reads each
library's name + description from pyproject, and appends them via
_local_entry. Idempotent: existing entries (by name) are skipped
silently, so multiple --dev projects on the same machine don't
collide or double-register.

Refs spec internals/specs/versioning-and-publishing.md T6, §8.
EOF
)"
```

---

### Task 8: Final verification

**Files:** read-only.

- [ ] **Step 1: Run the full fast test suite**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run pytest -m "not integration" -q 2>&1 | tail -3
```

Expected: every test passes. Baseline at start of Plan D was 1156 passed. Plan D adds:
- 5 in `tests/test_share_save.py` (Task 3).
- Net +6 in `tests/test_init_scaffolding.py` (Task 4: rewrote TestDevMode = net -2; Task 5: +1 version test; Task 6: +5 (TestUserGlobalRegistration + TestG5NameCollision); Task 7: +3).

So the final tally should be around `1167 passed, 1 skipped, 75 deselected`. Exact number is less important than: nothing fails.

- [ ] **Step 2: Run ruff across the whole repo**

```bash
uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 3: Run mypy on the touched paths**

```bash
uv run mypy packages/haywire-studio/src/ scripts/bump_version.py scripts/generate_marketstall.py
```

Expected: clean.

- [ ] **Step 4: Confirm git status is clean**

```bash
git status --short
```

Expected: only `?? docs/superpowers/` (the pre-existing untracked planning artifacts).

- [ ] **Step 5: Confirm bump_version + generate_marketstall still work (no regressions in Plans A/B)**

```bash
uv run python scripts/bump_version.py 0.0.1 --dry-run
uv run python scripts/generate_marketstall.py --out /tmp/marketplace.toml && head -3 /tmp/marketplace.toml && rm /tmp/marketplace.toml
```

Expected:
- bump: `Nothing to do: all packages already at version 0.0.1.`
- generate: writes marketplace.toml starting with `# Official haywire marketplace`.

- [ ] **Step 6: Confirm `haywire share` (no flag) still produces stdout output**

```bash
uv run python -m haywire_studio share barn/haybale-haystack | head -5
```

Expected: prints `# Copy this snippet into a marketplace.toml:` followed by a `[[packages]]` block with `name = "haybale-haystack"`.

- [ ] **Step 7: Confirm `haywire share --save` works against the live monorepo**

```bash
uv run python -m haywire_studio share --save
ls -la marketstall.toml
uv run python -c "
import tomllib, pathlib
data = tomllib.loads(pathlib.Path('marketstall.toml').read_text())
print(f'{len(data[\"packages\"])} packages')
"
rm marketstall.toml
```

Expected: `Wrote .../marketstall.toml`, 8 packages.

- [ ] **Step 8: View commit history**

```bash
git log --oneline -10
```

Expected: 6 new commits from Plan D, on top of Plan C's squashed commit:

```
<sha> feat(init): --dev registers dev-repo libraries in user-global marketplace
<sha> feat(init): register scaffolded library in user-global marketplace + G5 check
<sha> feat(init): generated templates use 0.0.1 + ~= per Plan A convention
<sha> feat(init): project marketplace is now [[locals]]-only
<sha> feat(share): add --save to aggregate every barn/* into marketstall.toml
<sha> refactor(share): factor _build_entry_for_library out of share_library
11742443 feat(skill): /haywire-release release-flow playbook
655fc5fd feat: CI publish workflow + marketstall generator
28537691 feat: versioning migration + bump_version.py script
78a52a5f new versioning and publishing specs
```

---

## Self-Review (already performed by the plan author)

### Spec coverage

- §3 + §4 (0.0.1 + `~=` constraints in generated templates) — Task 5. ✅
- §6 `[[locals]]` schema — Task 4 (`_local_entry`). ✅
- §6 G5 name-collision check — Task 6 (`_check_global_collision` + `_register_local_in_global`). ✅
- §6 project marketplace is `[[locals]]`-only at init time — Task 4 (`_generate_project_marketplace_locals_only`). ✅
- §8 `haywire init` writes locals to user-global, not a marketstall — Task 6. ✅
- §8 `haywire init --dev` registers dev-repo libraries in the user-global — Task 7. ✅
- §8 `haywire share --save` aggregates `barn/*` into root `marketstall.toml` — Tasks 2 + 3. ✅
- §8 `haywire share` (no flag) still produces a single-library stdout snippet — Task 2 preserves the existing behavior, Task 8 step 6 verifies. ✅

### Out of scope (correctly deferred)

- Two-tier marketplace runtime / refresh / conflict resolution / subscribed remotes — Plan E (T7).
- Library Manager UI changes — Plan E/F.
- The pre-existing `[[packages]]` entries that the OLD init wrote to existing projects — Plan E's refresh will overwrite them. No migration needed in Plan D.

### Placeholder scan

No "TBD", "implement later", "similar to Task N" — every step contains the actual content. ✅

### Type / signature consistency

- `_local_entry(name, path, label="", description="") -> dict` defined in Task 4, used in Tasks 4, 6, 7. ✅
- `_register_local_in_global(name, project_dir)` defined in Task 6, called in Task 7's `init_project` flow. ✅
- `_check_global_collision(name)` defined in Task 6, called in `init_project` before disk writes. ✅
- `ProjectNameCollisionError` defined in Task 6, raised by both `_check_global_collision` and `_register_local_in_global` for symmetry. ✅
- `share_save_repo(repo_root: Path) -> Path` defined in Task 3, called from `app.py`'s share branch with `--save`. ✅
- `NoBarnError` defined in Task 3, caught in `app.py`'s share branch. ✅
- `_build_entry_for_library(lib_dir: Path) -> dict | None` defined in Task 2, called from `share_library` (Task 2) and `share_save_repo` (Task 3). ✅

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-18-haywire-share-save-and-init-locals.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
2. **Inline Execution** — execute in this session with checkpoints.

Which approach?

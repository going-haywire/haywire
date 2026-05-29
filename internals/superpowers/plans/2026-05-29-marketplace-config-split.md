# Marketplace Config Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `publish_order` into `pip_publish_order` / `git_publish_order`, move `git_packages` from `[tool.haywire.marketstall]` into `[tool.haywire.release]`, and introduce an explicit `marketplace` allowlist so the official feed contains exactly and only the declared haybale packages.

**Architecture:** `ReleaseConfig` (in `bump_version.py`) gains `git_publish_order`; `all_packages` becomes all three versioned lists. `generate_marketstall.py` drops its `git_packages` field and reads `marketplace` from `[tool.haywire.marketstall]`, deriving `source` by lookup. The generator validates: every `marketplace` entry must be in exactly one publish list, and no package may be in both `pip_publish_order` and `git_publish_order`. CI workflows and test fixtures are updated to use the new key names.

**Tech Stack:** Python 3.12, tomllib (stdlib), pytest, GitHub Actions YAML.

---

## File Map

| File | Change |
|---|---|
| `pyproject.toml` | Rename `publish_order` → `pip_publish_order`; add `git_publish_order`; remove `git_packages` from `[tool.haywire.marketstall]`; add `marketplace` to `[tool.haywire.marketstall]` |
| `scripts/bump_version.py` | `ReleaseConfig`: rename `publish_order` → `pip_publish_order`, add `git_publish_order`; update `all_packages`; update `read_release_config` |
| `scripts/generate_marketstall.py` | `MarketstallConfig`: drop `git_packages`, add `marketplace`; update `read_marketstall_config`; replace generate loop with marketplace-driven logic + validation |
| `scripts/check_deps.py` | Docstring update only (references `publish_order`) |
| `.github/workflows/publish.yml` | Two `publish_order` → `pip_publish_order` in inline Python snippets |
| `.github/workflows/publish-testpypi.yml` | Same two substitutions |
| `tests/scripts/fixtures/sample_root_pyproject.toml` | Rename `publish_order` → `pip_publish_order` |
| `tests/scripts/fixtures/sample_marketstall_root_pyproject.toml` | Rename `publish_order` → `pip_publish_order`; add `marketplace` |
| `tests/scripts/test_bump_version.py` | Update assertions for renamed field |
| `tests/scripts/test_generate_marketstall.py` | Update inline fixture strings; add validation tests |

---

## Task 1: Update `ReleaseConfig` in `bump_version.py`

**Files:**
- Modify: `scripts/bump_version.py:24-40`
- Modify: `tests/scripts/fixtures/sample_root_pyproject.toml`
- Modify: `tests/scripts/test_bump_version.py`

- [ ] **Step 1: Write the failing test**

Open `tests/scripts/test_bump_version.py`. Replace the `test_read_release_config_returns_publishable_and_lockstep_lists` test with:

```python
@pytest.mark.unit
def test_read_release_config_returns_pip_git_and_lockstep_lists(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())

    config = bump_version.read_release_config(root)

    assert config.pip_publish_order == ["alpha-pkg", "beta-pkg"]
    assert config.git_publish_order == ["delta-pkg"]
    assert config.lockstep_unpublished == ["gamma-pkg"]
    assert config.all_packages == ["alpha-pkg", "beta-pkg", "delta-pkg", "gamma-pkg"]
```

- [ ] **Step 2: Update the fixture to match**

Rewrite `tests/scripts/fixtures/sample_root_pyproject.toml`:

```toml
[project]
name = "fake-workspace"
version = "0.0.0"

[tool.uv.workspace]
members = [
    "subdir-a/*",
    "subdir-b/*",
]

[tool.haywire.release]
pip_publish_order = [
    "alpha-pkg",
    "beta-pkg",
]
git_publish_order = [
    "delta-pkg",
]
lockstep_unpublished = [
    "gamma-pkg",
]
```

- [ ] **Step 3: Run the test to verify it fails**

```
uv run pytest tests/scripts/test_bump_version.py::test_read_release_config_returns_pip_git_and_lockstep_lists -v
```

Expected: FAIL — `ReleaseConfig` has no `pip_publish_order` or `git_publish_order`.

- [ ] **Step 4: Update `ReleaseConfig` and `read_release_config`**

In `scripts/bump_version.py`, replace lines 24–40:

```python
@dataclass(frozen=True)
class ReleaseConfig:
    pip_publish_order: list[str]
    git_publish_order: list[str]
    lockstep_unpublished: list[str]

    @property
    def all_packages(self) -> list[str]:
        return [*self.pip_publish_order, *self.git_publish_order, *self.lockstep_unpublished]


def read_release_config(root_pyproject: Path) -> ReleaseConfig:
    data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    block = data["tool"]["haywire"]["release"]
    return ReleaseConfig(
        pip_publish_order=list(block["pip_publish_order"]),
        git_publish_order=list(block.get("git_publish_order", [])),
        lockstep_unpublished=list(block.get("lockstep_unpublished", [])),
    )
```

- [ ] **Step 5: Fix the bump_version `apply_bump` walk comment**

In `scripts/bump_version.py` line 151, update the comment:

```python
    # Walk in pip_publish_order, git_publish_order, then lockstep_unpublished — deterministic ordering.
    for pkg_name in config.all_packages:
```

- [ ] **Step 6: Fix `locate_packages` test — it sets up `delta-pkg` on disk**

The existing `test_locate_packages_finds_pyprojects_by_project_name` test uses the updated fixture, so `delta-pkg` must exist on disk. Update that test in `tests/scripts/test_bump_version.py`:

```python
@pytest.mark.unit
def test_locate_packages_finds_pyprojects_by_project_name(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())

    for member_dir, pkg_name in [
        ("subdir-a/alpha", "alpha-pkg"),
        ("subdir-a/beta", "beta-pkg"),
        ("subdir-a/delta", "delta-pkg"),
        ("subdir-b/gamma", "gamma-pkg"),
        ("subdir-b/unrelated", "noise-pkg"),
    ]:
        d = tmp_path / member_dir
        d.mkdir(parents=True)
        (d / "pyproject.toml").write_text(f'[project]\nname = "{pkg_name}"\nversion = "0.0.1"\n')

    config = bump_version.read_release_config(root)
    located = bump_version.locate_packages(root, config)

    assert set(located.keys()) == {"alpha-pkg", "beta-pkg", "delta-pkg", "gamma-pkg"}
    assert located["alpha-pkg"] == tmp_path / "subdir-a/alpha/pyproject.toml"
    assert located["gamma-pkg"] == tmp_path / "subdir-b/gamma/pyproject.toml"
```

- [ ] **Step 7: Fix the missing-package test — add delta-pkg**

Update `test_locate_packages_raises_when_a_release_package_is_missing` in `tests/scripts/test_bump_version.py` to match. Read the rest of that test first, then ensure `MissingPackageError` mentions `beta-pkg`, `delta-pkg`, and `gamma-pkg` (the three not on disk):

```python
@pytest.mark.unit
def test_locate_packages_raises_when_a_release_package_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())
    # Only one of four packages exists on disk.
    d = tmp_path / "subdir-a/alpha"
    d.mkdir(parents=True)
    (d / "pyproject.toml").write_text('[project]\nname = "alpha-pkg"\nversion = "0.0.1"\n')

    config = bump_version.read_release_config(root)
    with pytest.raises(bump_version.MissingPackageError, match="beta-pkg"):
        bump_version.locate_packages(root, config)
```

- [ ] **Step 8: Run all bump_version tests**

```
uv run pytest tests/scripts/test_bump_version.py -v
```

Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add scripts/bump_version.py tests/scripts/test_bump_version.py tests/scripts/fixtures/sample_root_pyproject.toml
git commit -m "refactor: split publish_order into pip_publish_order + git_publish_order in ReleaseConfig"
```

---

## Task 2: Update `generate_marketstall.py` — config reading and data model

**Files:**
- Modify: `scripts/generate_marketstall.py:96-122`
- Modify: `tests/scripts/fixtures/sample_marketstall_root_pyproject.toml`
- Modify: `tests/scripts/test_generate_marketstall.py`

- [ ] **Step 1: Update the marketstall fixture**

Rewrite `tests/scripts/fixtures/sample_marketstall_root_pyproject.toml`:

```toml
[project]
name = "fake-workspace"
version = "0.0.0"

[tool.uv.workspace]
members = [
    "subdir-a/*",
    "subdir-b/*",
]

[tool.haywire.release]
pip_publish_order = [
    "haybale-alpha",
    "haybale-beta",
]
git_publish_order = []
lockstep_unpublished = [
    "haybale-internal",
]

[tool.haywire.marketstall]
source_url = "https://github.com/example/fake-workspace"
docs_branch = "main"
default_author = "Fake Team"
default_tags = []
marketplace = [
    "haybale-alpha",
    "haybale-beta",
]
```

- [ ] **Step 2: Write the failing test for `read_marketstall_config`**

In `tests/scripts/test_generate_marketstall.py`, replace `test_marketstall_config_reads_defaults_from_root_pyproject`:

```python
@pytest.mark.unit
def test_marketstall_config_reads_defaults_from_root_pyproject(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_marketstall_root_pyproject.toml").read_text())

    config = generate_marketstall.read_marketstall_config(root)

    assert config.source_url == "https://github.com/example/fake-workspace"
    assert config.docs_branch == "main"
    assert config.default_author == "Fake Team"
    assert config.default_tags == []
    assert config.feed_base_url == ""
    assert config.marketplace == ["haybale-alpha", "haybale-beta"]
```

- [ ] **Step 3: Run to verify it fails**

```
uv run pytest tests/scripts/test_generate_marketstall.py::test_marketstall_config_reads_defaults_from_root_pyproject -v
```

Expected: FAIL — `MarketstallConfig` has no `marketplace` field.

- [ ] **Step 4: Update `MarketstallConfig` and `read_marketstall_config`**

In `scripts/generate_marketstall.py`, replace the `MarketstallConfig` dataclass and `read_marketstall_config` function (lines 96–122):

```python
@dataclass(frozen=True)
class MarketstallConfig:
    """Repo-level config consumed by build_entry. Read from [tool.haywire.marketstall].

    ``feed_base_url`` (spec §11) is the deployed-feed root; the generator
    composes per-stall URLs as ``{feed_base_url}/stalls/{dist-name}.toml``.
    ``marketplace`` is the explicit allowlist of package names that appear in
    the official feed. Source (pypi vs git) is derived by lookup against the
    release config's pip_publish_order / git_publish_order.
    """

    source_url: str
    docs_branch: str
    default_author: str
    default_tags: list[str]
    feed_base_url: str
    marketplace: list[str]


def read_marketstall_config(root_pyproject: Path) -> MarketstallConfig:
    data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    block = data["tool"]["haywire"]["marketstall"]
    return MarketstallConfig(
        source_url=block["source_url"],
        docs_branch=block.get("docs_branch", "main"),
        default_author=block.get("default_author", ""),
        default_tags=list(block.get("default_tags", [])),
        feed_base_url=block.get("feed_base_url", "").rstrip("/"),
        marketplace=list(block.get("marketplace", [])),
    )
```

- [ ] **Step 5: Run the config test**

```
uv run pytest tests/scripts/test_generate_marketstall.py::test_marketstall_config_reads_defaults_from_root_pyproject -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_marketstall.py tests/scripts/test_generate_marketstall.py tests/scripts/fixtures/sample_marketstall_root_pyproject.toml
git commit -m "refactor: replace git_packages with marketplace allowlist in MarketstallConfig"
```

---

## Task 3: Rewrite the `generate()` function — marketplace-driven loop with validation

**Files:**
- Modify: `scripts/generate_marketstall.py:298-368`
- Modify: `tests/scripts/test_generate_marketstall.py`

- [ ] **Step 1: Write the failing validation tests**

Add these tests to `tests/scripts/test_generate_marketstall.py`:

```python
@pytest.mark.unit
def test_generate_errors_when_marketplace_entry_not_in_any_publish_list(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        '[tool.haywire.release]\n'
        'pip_publish_order = ["haybale-alpha"]\n'
        'git_publish_order = []\n'
        'lockstep_unpublished = []\n'
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/repo"\n'
        'docs_branch = "main"\n'
        'default_author = ""\n'
        "default_tags = []\n"
        'marketplace = ["haybale-alpha", "haybale-unknown"]\n'
    )
    pkg = tmp_path / "pkgs/haybale-alpha"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.0.1"\ndescription = "d"\ndependencies = []\n'
    )
    (pkg / "haybale_alpha").mkdir()
    (pkg / "haybale_alpha" / "__init__.py").write_text('"""alpha."""\n')

    with pytest.raises(ValueError, match="haybale-unknown"):
        generate_marketstall.generate(root, feed_base_url="https://feed.example/x")


@pytest.mark.unit
def test_generate_errors_when_package_in_both_publish_lists(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        '[tool.haywire.release]\n'
        'pip_publish_order = ["haybale-alpha"]\n'
        'git_publish_order = ["haybale-alpha"]\n'
        'lockstep_unpublished = []\n'
        "[tool.haywire.marketstall]\n"
        'source_url = "https://github.com/example/repo"\n'
        'docs_branch = "main"\n'
        'default_author = ""\n'
        "default_tags = []\n"
        'marketplace = ["haybale-alpha"]\n'
    )
    pkg = tmp_path / "pkgs/haybale-alpha"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.0.1"\ndescription = "d"\ndependencies = []\n'
    )
    (pkg / "haybale_alpha").mkdir()
    (pkg / "haybale_alpha" / "__init__.py").write_text('"""alpha."""\n')

    with pytest.raises(ValueError, match="haybale-alpha"):
        generate_marketstall.generate(root, feed_base_url="https://feed.example/x")
```

- [ ] **Step 2: Run to verify they fail**

```
uv run pytest tests/scripts/test_generate_marketstall.py::test_generate_errors_when_marketplace_entry_not_in_any_publish_list tests/scripts/test_generate_marketstall.py::test_generate_errors_when_package_in_both_publish_lists -v
```

Expected: both FAIL.

- [ ] **Step 3: Rewrite the `generate()` function**

In `scripts/generate_marketstall.py`, replace the `generate()` function (from `def generate(` through the closing `return GenerateResult(...)`):

```python
def generate(root_pyproject: Path, *, feed_base_url: str | None = None) -> GenerateResult:
    """Build the two-tier official feed (spec §11) for the workspace.

    Reads:
      - [tool.haywire.release] pip_publish_order, git_publish_order
      - [tool.haywire.marketstall] marketplace (explicit allowlist), plus URL/defaults
      - each marketplace package's pyproject + __init__.py

    Validates:
      - Every marketplace entry appears in exactly one of pip_publish_order or
        git_publish_order (unknown name → ValueError).
      - No name may appear in both pip_publish_order and git_publish_order.

    Returns a :class:`GenerateResult` carrying:
      - ``marketplace_toml``: aggregator TOML with one ``[[stalls]]`` per entry
        in marketplace, URL = ``{feed_base_url}/stalls/{dist-name}.toml``.
      - ``stalls``: list of ``(dist-name, stall-toml)`` pairs in marketplace order.
    """
    from scripts.bump_version import locate_packages, read_release_config

    release = read_release_config(root_pyproject)
    config = read_marketstall_config(root_pyproject)
    root_dir = root_pyproject.parent

    base_url = (feed_base_url or config.feed_base_url).rstrip("/")
    if not base_url:
        raise ValueError(
            "feed_base_url is required: set [tool.haywire.marketstall].feed_base_url "
            "in pyproject.toml or pass --feed-base-url on the command line."
        )

    pip_set = set(release.pip_publish_order)
    git_set = set(release.git_publish_order)

    # Validate: no package in both lists.
    both = pip_set & git_set
    if both:
        raise ValueError(
            f"packages appear in both pip_publish_order and git_publish_order: {sorted(both)}. "
            "A package can only have one source."
        )

    # Validate: every marketplace entry must be in exactly one publish list.
    marketplace_set = set(config.marketplace)
    unknown = marketplace_set - pip_set - git_set
    if unknown:
        raise ValueError(
            f"marketplace entries not found in pip_publish_order or git_publish_order: "
            f"{sorted(unknown)}. "
            "Add them to the appropriate publish list or remove them from marketplace."
        )

    located = locate_packages(root_pyproject, release)

    stalls: list[tuple[str, str]] = []
    stall_urls: list[str] = []

    for pkg_name in config.marketplace:
        source = "pypi" if pkg_name in pip_set else "git"
        pyproject_path = located[pkg_name]
        pkg_dir = pyproject_path.parent
        module_path = _resolve_module_path(pyproject_path, pkg_dir)
        init_py = pkg_dir / module_path / "__init__.py"
        module_name = Path(module_path).name
        subdirectory = pkg_dir.relative_to(root_dir).as_posix()
        entry = build_entry(
            pyproject_path=pyproject_path,
            init_py=init_py,
            config=config,
            subdirectory=subdirectory,
            module_name=module_name,
            source=source,
        )
        dist_name = str(entry["name"])
        stalls.append((dist_name, emit_stall_toml(entry)))
        stall_urls.append(f"{base_url}/stalls/{dist_name}.toml")

    return GenerateResult(
        marketplace_toml=emit_marketplace_toml(stall_urls),
        stalls=stalls,
    )
```

- [ ] **Step 4: Remove the now-dead `git_packages` overlap check**

The old check (`bad = set(config.git_packages) & set(release.publish_order)`) is gone — it lived just above the old loop. Confirm it no longer exists in the file:

```
grep -n "git_packages" scripts/generate_marketstall.py
```

Expected: no output (the field is gone from `MarketstallConfig` and the function).

- [ ] **Step 5: Run the new validation tests**

```
uv run pytest tests/scripts/test_generate_marketstall.py::test_generate_errors_when_marketplace_entry_not_in_any_publish_list tests/scripts/test_generate_marketstall.py::test_generate_errors_when_package_in_both_publish_lists -v
```

Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_marketstall.py tests/scripts/test_generate_marketstall.py
git commit -m "feat: marketplace-driven feed generation with strict haybale validation"
```

---

## Task 4: Update existing `generate_marketstall` tests to use new fixture shape

**Files:**
- Modify: `tests/scripts/test_generate_marketstall.py` (inline fixture strings throughout)

The existing tests that build inline pyproject strings all use `publish_order`. They need updating to `pip_publish_order` + `git_publish_order`, and inline `marketplace` where needed.

- [ ] **Step 1: Run the full generate_marketstall test file to see what's currently broken**

```
uv run pytest tests/scripts/test_generate_marketstall.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR"
```

Note which tests fail — these are the ones with inline `publish_order` strings.

- [ ] **Step 2: Update `test_generate_walks_publish_order_and_returns_toml`**

Rename the test to `test_generate_walks_marketplace_and_returns_toml` and update its inline root pyproject. Replace the root `write_text` call:

```python
root.write_text((FIXTURE_DIR / "sample_marketstall_root_pyproject.toml").read_text())
```

This fixture already has the correct shape after Task 2. The test asserts `["haybale-alpha", "haybale-beta"]` — that still holds since the fixture's `marketplace` lists both.

- [ ] **Step 3: Update `test_generate_resolves_module_path_from_entry_points`**

Replace the inline root pyproject string in that test:

```python
root.write_text(
    '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
    '[tool.haywire.release]\npip_publish_order = ["haybale-foo"]\ngit_publish_order = []\nlockstep_unpublished = []\n'
    "[tool.haywire.marketstall]\n"
    'source_url = "https://github.com/example/fake-workspace"\n'
    'docs_branch = "main"\n'
    'default_author = ""\n'
    "default_tags = []\n"
    'marketplace = ["haybale-foo"]\n'
)
```

- [ ] **Step 4: Update `test_generate_resolves_src_layout_via_hatch_packages`**

Replace the inline root pyproject string in that test. Note: `haywire-frame` starts with `haywire-`, so it is exempt from the "must be in marketplace" check — but it still needs to be discoverable. Since it goes in `pip_publish_order` and is NOT in `marketplace`, the generator should not emit a stall for it. The test currently asserts `entry["name"] == "haywire-frame"` — this will now fail because framework packages are excluded. Update the test to assert the stalls list is empty:

```python
root.write_text(
    '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
    '[tool.haywire.release]\npip_publish_order = ["haywire-frame"]\ngit_publish_order = []\nlockstep_unpublished = []\n'
    "[tool.haywire.marketstall]\n"
    'source_url = "https://github.com/example/repo"\n'
    'docs_branch = "main"\n'
    'default_author = "Team"\n'
    "default_tags = []\n"
    'marketplace = []\n'
)
# ...keep package on-disk setup unchanged...

result = generate_marketstall.generate(root, feed_base_url="https://feed.example/x")
# haywire-frame is a framework package — exempt from marketplace, not in feed.
assert result.stalls == []
mp = tomllib.loads(result.marketplace_toml)
assert mp.get("stalls", []) == []
```

- [ ] **Step 5: Update `test_generate_tolerates_missing_init_py`**

Replace the inline root pyproject string:

```python
root.write_text(
    '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
    '[tool.haywire.release]\npip_publish_order = ["haybale-ghost"]\ngit_publish_order = []\nlockstep_unpublished = []\n'
    "[tool.haywire.marketstall]\n"
    'source_url = "https://github.com/example/repo"\n'
    'docs_branch = "main"\n'
    'default_author = "Default Author"\n'
    'default_tags = ["default-tag"]\n'
    'marketplace = ["haybale-ghost"]\n'
)
```

- [ ] **Step 6: Update `test_generate_requires_feed_base_url`**

```python
root.write_text(
    '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
    "[tool.haywire.release]\npip_publish_order = []\ngit_publish_order = []\nlockstep_unpublished = []\n"
    "[tool.haywire.marketstall]\n"
    'source_url = "https://github.com/example/repo"\n'
    'docs_branch = "main"\n'
    'default_author = ""\n'
    "default_tags = []\n"
    "marketplace = []\n"
    # NOTE: no feed_base_url set
)
```

- [ ] **Step 7: Update `test_cli_writes_marketplace_and_stalls_to_out_dir`**

This test uses the fixture file, so no inline string to update. But the `lockstep_unpublished` entry (`haybale-internal`) still needs to exist on disk — check that the fixture's `lockstep_unpublished` still includes `haybale-internal`. It does. No change needed.

- [ ] **Step 8: Update `test_build_entry_emits_git_source_with_subdirectory_install_spec`**

This test calls `build_entry(..., source="git")` directly — no generate loop, no fixture pyproject. It doesn't need changes.

- [ ] **Step 9: Run the full test file**

```
uv run pytest tests/scripts/test_generate_marketstall.py -v
```

Expected: all PASS.

- [ ] **Step 10: Commit**

```bash
git add tests/scripts/test_generate_marketstall.py
git commit -m "test: update generate_marketstall tests for pip_publish_order + marketplace shape"
```

---

## Task 5: Update the root `pyproject.toml`

**Files:**
- Modify: `pyproject.toml:89-148`

- [ ] **Step 1: Update `[tool.haywire.release]`**

Replace the `[tool.haywire.release]` block in `pyproject.toml`:

```toml
[tool.haywire.release]
# Canonical machine-readable list of releasable packages.
# Consumed by: scripts/bump_version.py (this repo),
#              scripts/generate_marketstall.py,
#              .github/workflows/publish.yml.
# Order is significant for the publish workflow: dependencies first.

# Packages published to PyPI on every release tag, in dependency order.
pip_publish_order = [
    "haywire-core",
    "haywire-studio",
    "haybale-core",
    "haybale-studio",
    "haybale-marketplace",
    "haybale-graph-editor",
    "haybale-haystack",
]

# Packages published via git subdirectory URL (binary deps or deferred from PyPI).
# Versioned in lockstep; installed as git+<source_url>#subdirectory=<pkg dir>.
git_publish_order = [
    "haybale-visiongraph",
]

# Packages versioned in lockstep with the release but NOT published anywhere.
# The bump script updates these too so internal users stay coherent.
lockstep_unpublished = [
    "haybale-example",
    "haybale-testing",
    "haybale-TEST_A",
]
```

- [ ] **Step 2: Update `[tool.haywire.marketstall]`**

Replace the `[tool.haywire.marketstall]` block. Remove the `git_packages` key and add `marketplace`:

```toml
[tool.haywire.marketstall]
# Configuration for scripts/generate_marketstall.py.
# Consumed by the marketplace generator and the CI publish workflow.

# Repo URL used as the `source_url` for every generated [[haybales]] entry.
# Also forms the base for the `docs_url` raw-githubusercontent URL.
source_url = "https://github.com/going-haywire/haywire"

# Default branch used in the raw-githubusercontent docs_url.
docs_branch = "main"

# Default author and tags applied when a package's @library decorator
# doesn't set them. Per-package values from the decorator always win.
default_author = "Haywire Team"
default_tags = []

# Base URL where the deployed feed lives. The generator composes the per-stall
# subscription URLs as "{feed_base_url}/stalls/{dist-name}.toml".
feed_base_url = "https://going-haywire.github.io/haywire"

# Explicit allowlist of packages that appear in the official marketplace feed,
# in the order they appear in the feed. Source (pypi vs git) is derived by
# lookup against pip_publish_order / git_publish_order above.
# Rules enforced at generation time:
#   - Every entry here must be in pip_publish_order or git_publish_order.
#   - No package may be in both pip_publish_order and git_publish_order.
marketplace = [
    "haybale-core",
    "haybale-studio",
    "haybale-marketplace",
    "haybale-graph-editor",
    "haybale-haystack",
    "haybale-visiongraph",
]
```

- [ ] **Step 3: Verify the generator runs cleanly against the real workspace**

```
uv run python scripts/generate_marketstall.py --out-dir /tmp/hw-feed-test
```

Expected: output like:
```
Wrote /tmp/hw-feed-test/marketplace.toml
Wrote /tmp/hw-feed-test/stalls/haybale-core.toml
Wrote /tmp/hw-feed-test/stalls/haybale-studio.toml
Wrote /tmp/hw-feed-test/stalls/haybale-marketplace.toml
Wrote /tmp/hw-feed-test/stalls/haybale-graph-editor.toml
Wrote /tmp/hw-feed-test/stalls/haybale-haystack.toml
Wrote /tmp/hw-feed-test/stalls/haybale-visiongraph.toml
```

No `haywire-core.toml` or `haywire-studio.toml` should appear.

- [ ] **Step 4: Spot-check the output**

```
cat /tmp/hw-feed-test/marketplace.toml
```

Expected: 6 `[[stalls]]` entries, all pointing to `haybale-*.toml` URLs. No `haywire-*.toml`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "config: split publish_order into pip/git_publish_order; add explicit marketplace allowlist"
```

---

## Task 6: Update CI workflows

**Files:**
- Modify: `.github/workflows/publish.yml`
- Modify: `.github/workflows/publish-testpypi.yml`

Both workflows read `publish_order` in two inline Python snippets each. They build and publish everything in that list — which should remain `pip_publish_order` (git packages are not published via `uv publish`).

- [ ] **Step 1: Update `publish.yml`**

There are two occurrences of `d['tool']['haywire']['release']['publish_order']` in `publish.yml` (lines ~69 and ~136). Replace both with `pip_publish_order`:

```python
print(json.dumps(d['tool']['haywire']['release']['pip_publish_order']))
```

- [ ] **Step 2: Update `publish-testpypi.yml`**

Same two replacements in `publish-testpypi.yml` (lines ~72 and ~139):

```python
print(json.dumps(d['tool']['haywire']['release']['pip_publish_order']))
```

- [ ] **Step 3: Update the step names for clarity**

In both workflow files, rename the step labels from `Read publish_order from [tool.haywire.release]` to `Read pip_publish_order from [tool.haywire.release]` and `Read publish_order` to `Read pip_publish_order`.

- [ ] **Step 4: Verify YAML is valid**

```
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/publish.yml'))" && echo "OK"
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/publish-testpypi.yml'))" && echo "OK"
```

Expected: `OK` for both.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/publish.yml .github/workflows/publish-testpypi.yml
git commit -m "ci: update workflows to read pip_publish_order"
```

---

## Task 7: Update `check_deps.py` docstring and run the full test suite

**Files:**
- Modify: `scripts/check_deps.py:1-8`

- [ ] **Step 1: Update the module docstring**

Replace the first paragraph of `scripts/check_deps.py`:

```python
"""Audit declared vs. imported dependencies for every haywire package.

Wraps `deptry` and runs it once per package listed in
[tool.haywire.release] (pip_publish_order + git_publish_order + lockstep_unpublished).
Because the monorepo's packages import each other by *module* name (e.g. `haywire`) while
declaring each other by *distribution* name (e.g. `haywire-core`), a
package-module-name map is supplied so inter-package deps are not mis-flagged.
```

- [ ] **Step 2: Run the full test suite**

```
uv run pytest -m "not integration" -q
```

Expected: all tests PASS, no failures.

- [ ] **Step 3: Run ruff and mypy over the touched scripts**

```
uv run ruff check scripts/bump_version.py scripts/generate_marketstall.py scripts/check_deps.py
uv run mypy scripts/bump_version.py scripts/generate_marketstall.py
```

Expected: no errors.

- [ ] **Step 4: Final commit**

```bash
git add scripts/check_deps.py
git commit -m "docs: update check_deps docstring for pip_publish_order rename"
```

---

## Self-Review

**Spec coverage:**

| Requirement | Task |
|---|---|
| Rename `publish_order` → `pip_publish_order` | Task 1, 5, 6 |
| Add `git_publish_order` to release config | Task 1, 5 |
| Move `git_packages` out of `[tool.haywire.marketstall]` | Task 2, 5 |
| Add `marketplace` allowlist to `[tool.haywire.marketstall]` | Task 2, 5 |
| Generator iterates `marketplace`, derives source by lookup | Task 3 |
| Validation: marketplace entry not in any publish list → error | Task 3 |
| Validation: package in both pip + git lists → error | Task 3 |
| `all_packages` = pip + git + lockstep | Task 1 |
| CI workflows use `pip_publish_order` | Task 6 |
| `haywire-core` and `haywire-studio` absent from generated feed | Task 5 (verified in step 3) |
| `haybale-visiongraph` present in generated feed via git source | Task 5 |

**Placeholder scan:** No TBDs, no "handle edge cases", no "similar to task N". All code blocks are complete.

**Type consistency:** `MarketstallConfig.marketplace: list[str]` used consistently. `ReleaseConfig.pip_publish_order`, `.git_publish_order`, `.all_packages` consistent across Tasks 1, 3, 4.

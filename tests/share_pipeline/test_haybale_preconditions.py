"""Preflight checks introduced with haybale.toml.

Three conditions, all of which are wrong only for *consumers* — the publisher's
own machine keeps working, so nothing surfaces where it could be noticed. That
asymmetry is why each is worth a check rather than a convention.
"""

import subprocess
from pathlib import Path

import pytest

from haywire.core.publishing.generate import pyproject_drift, sync_pyproject_from_haybale
from haywire.core.publishing.pipeline import SharePipeline

_DECLARED = 'name = "haybale-alpha"\nid = "alpha"\nlabel = "Alpha"\ndescription = "d"\n'


def _run(repo: Path, *args: str) -> None:
    subprocess.run(list(args), cwd=repo, check=True, capture_output=True)


@pytest.fixture
def bare_remote(tmp_path: Path) -> Path:
    """A real reachable remote — the origin probe runs before these checks."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _run(remote, "git", "init", "--bare")
    return remote


@pytest.fixture
def project(tmp_path: Path, bare_remote: Path) -> Path:
    """A project whose pyproject already agrees with its haybale.toml."""
    repo = tmp_path / "project"
    module = repo / "barn" / "haybale-alpha" / "haybale_alpha"
    module.mkdir(parents=True)
    (module / "__init__.py").write_text('@library(id="alpha")\nclass Library: pass\n')
    (module / "haybale.toml").write_text(_DECLARED)
    (repo / "barn" / "haybale-alpha" / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\ndescription = "d"\n'
    )
    (repo / ".haywire").mkdir()
    _run(repo, "git", "init")
    _run(repo, "git", "config", "user.email", "t@t.test")
    _run(repo, "git", "config", "user.name", "T")
    _run(repo, "git", "remote", "add", "origin", str(bare_remote))
    _run(repo, "git", "add", "-A")
    _run(repo, "git", "commit", "-m", "init")
    _run(repo, "git", "push", "-u", "origin", "HEAD")
    return repo


def _lib(repo: Path) -> Path:
    return repo / "barn" / "haybale-alpha"


def _declared_file(repo: Path) -> Path:
    return _lib(repo) / "haybale_alpha" / "haybale.toml"


def _failures(repo: Path) -> list:
    """Commit first: the clean-tree probe precedes every check under test."""
    _run(repo, "git", "add", "-A")
    subprocess.run(["git", "commit", "-m", "wip"], cwd=repo, capture_output=True)
    return SharePipeline(repo).check_preconditions().failures


# ── declared paths ───────────────────────────────────────────────────────────


def test_a_declared_path_that_does_not_exist_blocks_the_publish(project: Path) -> None:
    _declared_file(project).write_text(_DECLARED + 'examples_path = "examples/"\n')

    failures = _failures(project)

    assert failures
    assert "examples_path" in failures[0].message
    assert failures[0].kind == "act"


def test_the_fix_offers_candidates_when_any_exist(project: Path) -> None:
    """Offered rather than typed: a repair cannot introduce a second wrong
    value if the user picks from what is actually on disk."""
    (project / "examples").mkdir()
    _declared_file(project).write_text(_DECLARED + 'examples_path = "wrong/"\n')

    failure = _failures(project)[0]

    assert failure.fix_id == "set_examples_path"
    assert "candidate" in failure.fix_label


def test_the_fix_clears_when_nothing_plausible_exists(project: Path) -> None:
    _declared_file(project).write_text(_DECLARED + 'examples_path = "wrong/"\n')

    failure = _failures(project)[0]

    assert failure.fix_id == "clear_examples_path"
    assert failure.fix_label == "Remove the declaration"


def test_set_declared_path_writes_the_chosen_value(project: Path) -> None:
    (project / "examples").mkdir()
    _declared_file(project).write_text(_DECLARED + 'examples_path = "wrong/"\n')

    pipeline = SharePipeline(project)
    pipeline.apply_precondition_fix("set_examples_path", lib_dir="barn/haybale-alpha", path="examples/")

    assert 'examples_path = "examples/"' in _declared_file(project).read_text()
    assert _declared_file(project) in pipeline.written


def test_clear_declared_path_removes_the_key(project: Path) -> None:
    _declared_file(project).write_text(_DECLARED + 'examples_path = "wrong/"\n')

    SharePipeline(project).apply_precondition_fix("clear_examples_path", lib_dir="barn/haybale-alpha")

    assert "examples_path" not in _declared_file(project).read_text()


def test_an_existing_declared_path_passes(project: Path) -> None:
    (project / "examples").mkdir()
    _declared_file(project).write_text(_DECLARED + 'examples_path = "examples/"\n')

    assert not [f for f in _failures(project) if "examples_path" in f.message]


# ── pyproject agreement ──────────────────────────────────────────────────────


def test_a_pyproject_that_disagrees_blocks_the_publish(project: Path) -> None:
    """The author edited pyproject by hand — the obvious place, since every
    other Python tool says so. Publishing would discard it silently."""
    pyproject = _lib(project) / "pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace('description = "d"', 'description = "edited"'))

    failure = _failures(project)[0]

    assert failure.fix_id == "sync_pyproject"
    assert "description" in failure.message
    assert failure.kind == "act"


def test_sync_regenerates_from_haybale_toml(project: Path) -> None:
    pyproject = _lib(project) / "pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace('description = "d"', 'description = "edited"'))

    pipeline = SharePipeline(project)
    pipeline.apply_precondition_fix("sync_pyproject", lib_dir="barn/haybale-alpha")

    assert 'description = "d"' in pyproject.read_text()
    assert not _failures(project)


def test_drift_is_reported_before_it_is_applied(project: Path) -> None:
    """The write is unconditional, but it must never be a surprise: the caller
    can see every changed field first."""
    pyproject = _lib(project) / "pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace('description = "d"', 'description = "edited"'))

    drift = pyproject_drift(_lib(project))

    assert drift["description"] == ("edited", "d")


def test_sync_preserves_hand_authored_fields(project: Path) -> None:
    """[project] dependencies and the build machinery are pyproject's own —
    generation must not touch them."""
    pyproject = _lib(project) / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\ndescription = "stale"\n'
        "# a comment that must survive\n"
        'dependencies = ["haywire-core>=0.0.1"]\n\n'
        '[build-system]\nrequires = ["hatchling"]\n'
    )

    sync_pyproject_from_haybale(_lib(project))

    text = pyproject.read_text()
    assert 'dependencies = ["haywire-core>=0.0.1"]' in text
    assert "[build-system]" in text
    assert "# a comment that must survive" in text
    assert 'description = "d"' in text


def test_version_is_now_generated_from_haybale_toml(project: Path) -> None:
    """haybale.toml is canon for version (D6/D7): pyproject carries a generated
    copy, since pip/uv/PyPI read that file and cannot read haybale.toml."""
    _declared_file(project).write_text(_DECLARED + 'version = "9.9.9"\n')

    sync_pyproject_from_haybale(_lib(project))

    assert 'version = "9.9.9"' in (_lib(project) / "pyproject.toml").read_text()


def test_a_deprecated_block_projects_into_a_classifier(project: Path) -> None:
    """PEP 621 has no deprecation field; this classifier is the ecosystem's
    only signal."""
    _declared_file(project).write_text(_DECLARED + '\n[deprecated]\nsince = "0.2.0"\nreason = "x"\n')

    sync_pyproject_from_haybale(_lib(project))

    assert "Development Status :: 7 - Inactive" in (_lib(project) / "pyproject.toml").read_text()


# ── the project root must be the git root ────────────────────────────────────


def test_a_project_below_the_git_root_blocks_the_publish(tmp_path: Path) -> None:
    """Declared paths are project-relative but resolved git-root-relative, so a
    mismatch sends every consumer to the wrong directory — while the
    publisher's own paths keep working."""
    repo = tmp_path / "repo"
    nested = repo / "projects" / "foo"
    module = nested / "barn" / "haybale-alpha" / "haybale_alpha"
    module.mkdir(parents=True)
    (module / "__init__.py").write_text("")
    (module / "haybale.toml").write_text(_DECLARED)
    (nested / "barn" / "haybale-alpha" / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\n'
    )
    (nested / ".haywire").mkdir()
    _run(repo, "git", "init")
    _run(repo, "git", "config", "user.email", "t@t.test")
    _run(repo, "git", "config", "user.name", "T")
    _run(repo, "git", "add", "-A")
    _run(repo, "git", "commit", "-m", "init")

    failures = SharePipeline(repo).check_preconditions().failures

    assert failures
    assert "not the root of its git repository" in failures[0].message
    # No inline fix: the remedy is restructuring a repository.
    assert failures[0].fix_id is None


# ── phase A finalizes haybale.toml before phase B generates ──────────────────


def test_the_bump_writes_the_version_into_haybale_toml_too(project: Path) -> None:
    """Phase A: the declaration is finalized before anything reads it. Writing
    only pyproject would leave the shipped file advertising the old version."""
    SharePipeline(project).apply_bump("1.2.3")

    assert 'version = "1.2.3"' in _declared_file(project).read_text()
    assert 'version = "1.2.3"' in (_lib(project) / "pyproject.toml").read_text()


def test_the_bump_records_where_the_library_is_published_from(project: Path) -> None:
    """origin is an observation about this checkout, not something authored —
    which is what makes a fork correct for free on its first publish."""
    SharePipeline(project).apply_bump("1.2.3")

    declared = _declared_file(project).read_text()
    assert "origin = " in declared


def test_the_row_prefers_the_declaration_over_re_deriving_it(project: Path) -> None:
    """Phase B reads what Phase A wrote. Re-deriving would let the row and the
    shipped file disagree about where the library came from."""
    from haywire.core.publishing.marketstall import _build_entry_for_library

    _declared_file(project).write_text(
        _DECLARED + 'origin = "https://gitlab.zhdk.ch/g/haybale-alpha"\norigin_provider = "gitlab"\n'
    )

    entry = _build_entry_for_library(_lib(project))

    assert entry is not None
    assert entry["origin"] == "https://gitlab.zhdk.ch/g/haybale-alpha"
    assert entry["origin_provider"] == "gitlab"


def test_a_self_hosted_row_resolves_without_local_config(project: Path) -> None:
    """The point of publishing origin_provider: a consumer has never heard of
    the publisher's forge and has nothing in ~/.haywire/config.toml."""
    from haywire.core.marketstall.host_providers import provider_for
    from haywire.core.marketstall.types import Haybale

    row = Haybale(
        name="haybale-alpha",
        version="1.0.0",
        origin="https://gitlab.zhdk.ch/g/repo",
        origin_provider="gitlab",
        install_spec="haybale-alpha @ git+https://gitlab.zhdk.ch/g/repo.git@v1.0.0#subdirectory=barn/haybale-alpha",
    )

    provider = provider_for(row.origin_provider, "gitlab.zhdk.ch")

    assert provider is not None
    assert provider.blob_url("g", "repo", "v1.0.0", "F.md").startswith("https://gitlab.zhdk.ch/")

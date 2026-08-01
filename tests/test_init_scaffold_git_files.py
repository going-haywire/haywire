"""`haywire init` scaffolds .gitignore and .gitattributes that don't corrupt a publish."""

import subprocess
from pathlib import Path

import pytest

from haywire_studio.init import _generate_gitattributes, _generate_gitignore

pytestmark = pytest.mark.unit


# ── .gitignore anchoring ─────────────────────────────────────────────────────


@pytest.mark.parametrize("pattern", ["/build/", "/dist/", "/env/", "/venv/", "/.venv/"])
def test_root_only_patterns_are_anchored(pattern: str) -> None:
    """An unanchored pattern matches at EVERY depth — including inside
    barn/<lib>/<module>/, where it silently excludes library content.
    Ignored ⇒ never committed ⇒ absent from the clone consumers install from."""
    assert pattern in _generate_gitignore()


@pytest.mark.parametrize("pattern", ["\nbuild/", "\ndist/", "\nenv/", "\nvenv/", "\n.venv/"])
def test_unanchored_variants_are_gone(pattern: str) -> None:
    assert pattern not in _generate_gitignore()


def test_depth_matching_patterns_are_kept_unanchored() -> None:
    """These SHOULD match at every depth — they're correctly ignored everywhere."""
    content = _generate_gitignore()
    assert "__pycache__/" in content
    assert "*.egg-info/" in content


def test_gitignore_explains_the_anchoring_rule() -> None:
    """The person about to edit the file is the one who needs the knowledge."""
    content = _generate_gitignore()
    assert "anchored" in content.lower()
    assert "barn/" in content


def test_gitignore_warns_before_adding_patterns() -> None:
    content = _generate_gitignore()
    assert "MISSING" in content or "missing" in content
    assert "clone" in content


def test_gitignore_still_ignores_workspace_state() -> None:
    assert ".haywire/workspace_state.json" in _generate_gitignore()


def test_anchored_patterns_do_not_ignore_barn_content(tmp_path: Path) -> None:
    """The real check: git itself must not ignore a library's build/ directory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / ".gitignore").write_text(_generate_gitignore())

    asset = repo / "barn" / "haybale-alpha" / "haybale_alpha" / "build" / "shader.glsl"
    asset.parent.mkdir(parents=True)
    asset.write_text("// shader\n")

    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(asset.relative_to(repo))],
        cwd=repo,
        capture_output=True,
    )
    assert ignored.returncode != 0, "barn library content must not be gitignored"


def test_root_build_dir_is_still_ignored(tmp_path: Path) -> None:
    repo = tmp_path / "repo2"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / ".gitignore").write_text(_generate_gitignore())
    (repo / "build").mkdir()
    (repo / "build" / "out.txt").write_text("x\n")

    ignored = subprocess.run(["git", "check-ignore", "-q", "build/out.txt"], cwd=repo, capture_output=True)
    assert ignored.returncode == 0


# ── .gitattributes ───────────────────────────────────────────────────────────


def test_gitattributes_normalizes_text_eol() -> None:
    assert "* text=auto" in _generate_gitattributes()


def test_gitattributes_arms_no_lfs_filter() -> None:
    """git stores a ~130-byte pointer; a consumer without git-lfs receives THAT
    instead of the asset. The install succeeds and the library breaks at runtime,
    and *.png is exactly what a node library's icons and skins match."""
    content = _generate_gitattributes()
    assert "filter=lfs" not in content
    assert "lfs install" not in content


def test_gitattributes_documents_the_lfs_tradeoff() -> None:
    """Don't arm the trap; document it where the decision gets made."""
    content = _generate_gitattributes().lower()
    assert "lfs" in content
    assert "pointer" in content


def test_gitattributes_marks_binary_assets_as_binary() -> None:
    content = _generate_gitattributes()
    assert "*.png" in content
    assert "binary" in content


# ── scaffold wiring ──────────────────────────────────────────────────────────


def test_init_writes_both_files(tmp_path: Path, monkeypatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("myproj", auto_sync=False)

    project = tmp_path / "myproj"
    assert (project / ".gitignore").read_text() == _generate_gitignore()
    assert (project / ".gitattributes").read_text() == _generate_gitattributes()


def test_scaffolded_project_commits_its_gitattributes(tmp_path: Path, monkeypatch) -> None:
    """It must be in the initial commit, or a consumer's clone applies no
    normalization at all."""
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("myproj2", auto_sync=False)

    project = tmp_path / "myproj2"
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=project, capture_output=True, text=True, check=True
    ).stdout.split()
    assert ".gitattributes" in tracked
    assert ".gitignore" in tracked

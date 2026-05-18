"""Tests for scripts/bump_version.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import bump_version


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.unit
def test_read_release_config_returns_publishable_and_lockstep_lists(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())

    config = bump_version.read_release_config(root)

    assert config.publish_order == ["alpha-pkg", "beta-pkg"]
    assert config.lockstep_unpublished == ["gamma-pkg"]
    assert config.all_packages == ["alpha-pkg", "beta-pkg", "gamma-pkg"]


@pytest.mark.unit
def test_locate_packages_finds_pyprojects_by_project_name(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())

    # Lay out fake workspace members.
    for member_dir, pkg_name in [
        ("subdir-a/alpha", "alpha-pkg"),
        ("subdir-a/beta", "beta-pkg"),
        ("subdir-b/gamma", "gamma-pkg"),
        ("subdir-b/unrelated", "noise-pkg"),  # not in release config
    ]:
        d = tmp_path / member_dir
        d.mkdir(parents=True)
        (d / "pyproject.toml").write_text(f'[project]\nname = "{pkg_name}"\nversion = "0.0.1"\n')

    config = bump_version.read_release_config(root)
    located = bump_version.locate_packages(root, config)

    assert set(located.keys()) == {"alpha-pkg", "beta-pkg", "gamma-pkg"}
    assert located["alpha-pkg"] == tmp_path / "subdir-a/alpha/pyproject.toml"
    assert located["gamma-pkg"] == tmp_path / "subdir-b/gamma/pyproject.toml"


@pytest.mark.unit
def test_locate_packages_raises_when_a_release_package_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())
    # Only one of three packages exists on disk.
    d = tmp_path / "subdir-a/alpha"
    d.mkdir(parents=True)
    (d / "pyproject.toml").write_text('[project]\nname = "alpha-pkg"\nversion = "0.0.1"\n')

    config = bump_version.read_release_config(root)
    with pytest.raises(bump_version.MissingPackageError) as exc:
        bump_version.locate_packages(root, config)

    assert "beta-pkg" in str(exc.value)
    assert "gamma-pkg" in str(exc.value)


@pytest.mark.unit
def test_rewrite_pyproject_bumps_top_level_version() -> None:
    src = '[project]\nname = "alpha"\nversion = "0.0.1"\n'
    known_siblings = {"alpha"}

    new_text, edits = bump_version.rewrite_pyproject(src, "0.0.2", known_siblings)

    assert 'version = "0.0.2"' in new_text
    assert 'version = "0.0.1"' not in new_text
    assert any("version" in e for e in edits)


@pytest.mark.unit
def test_rewrite_pyproject_rewrites_sibling_constraints_only() -> None:
    src = (
        "[project]\n"
        'name = "alpha"\n'
        'version = "0.0.1"\n'
        "dependencies = [\n"
        '    "beta-pkg~=0.0.1",\n'
        '    "external-lib>=1.0",\n'
        '    "gamma-pkg~=0.0.1",\n'
        '    "unrelated~=3.2.0",\n'
        "]\n"
    )
    known_siblings = {"alpha", "beta-pkg", "gamma-pkg"}

    new_text, _ = bump_version.rewrite_pyproject(src, "0.0.2", known_siblings)

    assert '"beta-pkg~=0.0.2"' in new_text
    assert '"gamma-pkg~=0.0.2"' in new_text
    # external libs are untouched even if their version coincidentally matches:
    assert '"external-lib>=1.0"' in new_text
    assert '"unrelated~=3.2.0"' in new_text


@pytest.mark.unit
def test_rewrite_pyproject_handles_first_migration_from_other_operator() -> None:
    """Bump script can also migrate >= constraints to ~= on the first run."""
    src = '[project]\nname = "alpha"\nversion = "0.1.0"\ndependencies = [\n    "beta-pkg>=0.1.0",\n]\n'
    known_siblings = {"alpha", "beta-pkg"}

    new_text, _ = bump_version.rewrite_pyproject(src, "0.0.1", known_siblings)

    assert '"beta-pkg~=0.0.1"' in new_text


@pytest.mark.unit
def test_rewrite_pyproject_preserves_comments_and_blank_lines() -> None:
    src = (
        "# top comment\n"
        "[project]\n"
        'name = "alpha"\n'
        'version = "0.0.1"\n'
        "\n"
        "# deps below\n"
        "dependencies = [\n"
        '    "beta-pkg~=0.0.1",  # inline note\n'
        "]\n"
    )
    known_siblings = {"alpha", "beta-pkg"}

    new_text, _ = bump_version.rewrite_pyproject(src, "0.0.2", known_siblings)

    assert new_text.startswith("# top comment\n")
    assert "# deps below" in new_text
    assert "# inline note" in new_text


@pytest.mark.unit
def test_rewrite_pyproject_idempotent_when_target_matches_current() -> None:
    src = '[project]\nname = "alpha"\nversion = "0.0.2"\ndependencies = ["beta-pkg~=0.0.2"]\n'
    known_siblings = {"alpha", "beta-pkg"}

    new_text, edits = bump_version.rewrite_pyproject(src, "0.0.2", known_siblings)

    assert new_text == src
    assert edits == []


@pytest.mark.unit
def test_rewrite_pyproject_raises_when_no_version_line() -> None:
    src = '[project]\nname = "alpha"\n'
    with pytest.raises(ValueError, match="could not find"):
        bump_version.rewrite_pyproject(src, "0.0.1", {"alpha"})


@pytest.mark.unit
def test_apply_bump_writes_files_and_returns_diff(tmp_path: Path) -> None:
    # Build a mini workspace with two packages on disk.
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())

    alpha_dir = tmp_path / "subdir-a/alpha"
    alpha_dir.mkdir(parents=True)
    (alpha_dir / "pyproject.toml").write_text(
        '[project]\nname = "alpha-pkg"\nversion = "0.0.1"\ndependencies = ["beta-pkg~=0.0.1"]\n'
    )

    beta_dir = tmp_path / "subdir-a/beta"
    beta_dir.mkdir(parents=True)
    (beta_dir / "pyproject.toml").write_text('[project]\nname = "beta-pkg"\nversion = "0.0.1"\n')

    gamma_dir = tmp_path / "subdir-b/gamma"
    gamma_dir.mkdir(parents=True)
    (gamma_dir / "pyproject.toml").write_text(
        '[project]\nname = "gamma-pkg"\nversion = "0.0.1"\ndependencies = ["alpha-pkg~=0.0.1"]\n'
    )

    diff_text, edited_count = bump_version.apply_bump(root, new_version="0.0.2", dry_run=False)

    assert edited_count == 3
    assert 'version = "0.0.2"' in (alpha_dir / "pyproject.toml").read_text()
    assert '"alpha-pkg~=0.0.2"' in (gamma_dir / "pyproject.toml").read_text()
    # Diff should reference all three files:
    assert "alpha/pyproject.toml" in diff_text
    assert "beta/pyproject.toml" in diff_text
    assert "gamma/pyproject.toml" in diff_text


@pytest.mark.unit
def test_apply_bump_dry_run_does_not_write(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())
    alpha_dir = tmp_path / "subdir-a/alpha"
    alpha_dir.mkdir(parents=True)
    original = '[project]\nname = "alpha-pkg"\nversion = "0.0.1"\n'
    (alpha_dir / "pyproject.toml").write_text(original)
    (tmp_path / "subdir-a/beta").mkdir(parents=True)
    (tmp_path / "subdir-a/beta/pyproject.toml").write_text(
        '[project]\nname = "beta-pkg"\nversion = "0.0.1"\n'
    )
    (tmp_path / "subdir-b/gamma").mkdir(parents=True)
    (tmp_path / "subdir-b/gamma/pyproject.toml").write_text(
        '[project]\nname = "gamma-pkg"\nversion = "0.0.1"\n'
    )

    diff_text, edited_count = bump_version.apply_bump(root, new_version="0.0.2", dry_run=True)

    assert edited_count == 3
    assert (alpha_dir / "pyproject.toml").read_text() == original
    assert "0.0.2" in diff_text

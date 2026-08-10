"""Tests for scripts/check_release_versions.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import check_release_versions


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _workspace(tmp_path: Path, versions: dict[str, str], haybale: dict[str, str] | None = None) -> Path:
    """Lay out a mini workspace matching sample_root_pyproject.toml.

    *versions* maps package name -> the version its pyproject declares.
    *haybale* maps package name -> the version its haybale.toml declares, for
    the packages that should have one.
    """
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())

    dirs = {
        "alpha-pkg": "subdir-a/alpha",
        "beta-pkg": "subdir-a/beta",
        "delta-pkg": "subdir-a/delta",
        "gamma-pkg": "subdir-b/gamma",
    }
    for pkg_name, rel in dirs.items():
        pkg_dir = tmp_path / rel
        pkg_dir.mkdir(parents=True)
        version = versions[pkg_name]
        (pkg_dir / "pyproject.toml").write_text(f'[project]\nname = "{pkg_name}"\nversion = "{version}"\n')
        if haybale and pkg_name in haybale:
            module_dir = pkg_dir / pkg_name.replace("-", "_")
            module_dir.mkdir()
            (module_dir / "__init__.py").write_text("")
            (module_dir / "haybale.toml").write_text(f'id = "{pkg_name}"\nversion = "{haybale[pkg_name]}"\n')
    return root


ALL_AT = {
    "alpha-pkg": "0.0.1",
    "beta-pkg": "0.0.1",
    "delta-pkg": "0.0.1",
    "gamma-pkg": "0.0.1",
}


@pytest.mark.unit
def test_passes_when_every_package_agrees(tmp_path: Path) -> None:
    root = _workspace(tmp_path, ALL_AT)

    assert check_release_versions.check(root, expected=None) == []


@pytest.mark.unit
def test_passes_when_expected_matches(tmp_path: Path) -> None:
    root = _workspace(tmp_path, ALL_AT)

    assert check_release_versions.check(root, expected="0.0.1") == []


@pytest.mark.unit
def test_fails_when_tag_does_not_match_committed_version(tmp_path: Path) -> None:
    """The gate this whole script exists for: tagged v0.0.2, never bumped."""
    root = _workspace(tmp_path, ALL_AT)

    problems = check_release_versions.check(root, expected="0.0.2")

    assert len(problems) == 4
    assert all('!= expected "0.0.2"' in p for p in problems)


@pytest.mark.unit
def test_fails_when_one_package_lags_behind(tmp_path: Path) -> None:
    versions = {**ALL_AT, "gamma-pkg": "0.0.1"}
    versions["beta-pkg"] = "0.0.2"
    root = _workspace(tmp_path, versions)

    problems = check_release_versions.check(root, expected=None)

    assert problems
    assert any("disagree" in p for p in problems)


@pytest.mark.unit
def test_fails_when_haybale_toml_lags_behind_pyproject(tmp_path: Path) -> None:
    """The sync bump_version.py performs is write-only; this reads it back."""
    root = _workspace(tmp_path, ALL_AT, haybale={"alpha-pkg": "0.0.0"})

    problems = check_release_versions.check(root, expected="0.0.1")

    assert len(problems) == 1
    assert "alpha_pkg/haybale.toml" in problems[0]
    assert '"0.0.0" != expected "0.0.1"' in problems[0]


@pytest.mark.unit
def test_passes_when_haybale_toml_is_in_sync(tmp_path: Path) -> None:
    root = _workspace(tmp_path, ALL_AT, haybale={"alpha-pkg": "0.0.1"})

    assert check_release_versions.check(root, expected="0.0.1") == []


@pytest.mark.unit
def test_reports_package_with_no_version_declared(tmp_path: Path) -> None:
    root = _workspace(tmp_path, ALL_AT)
    (tmp_path / "subdir-a/beta/pyproject.toml").write_text('[project]\nname = "beta-pkg"\n')

    problems = check_release_versions.check(root, expected="0.0.1")

    assert any("no version declared" in p for p in problems)


@pytest.mark.unit
def test_main_exits_nonzero_and_names_the_bump_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _workspace(tmp_path, ALL_AT)

    code = check_release_versions.main(["--root", str(root), "--expect", "0.0.2"])

    assert code == 1
    assert "bump_version.py 0.0.2" in capsys.readouterr().err


@pytest.mark.unit
def test_main_exits_zero_when_consistent(tmp_path: Path) -> None:
    root = _workspace(tmp_path, ALL_AT)

    assert check_release_versions.main(["--root", str(root), "--expect", "0.0.1"]) == 0

"""Pin rewriting, and the constant it depends on staying honest."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from haywire.core.update.pin import LOCKSTEP_DISTS, declared_floor, rewrite_pins

REPO_ROOT = Path(__file__).resolve().parents[2]


def _release_config() -> dict:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["tool"]["haywire"]["release"]


def test_lockstep_dists_matches_release_config():
    """LOCKSTEP_DISTS must name every dist the release actually bumps.

    pin.py cannot read the root pyproject at runtime (it ships into venvs that
    have no monorepo), so the list is restated. This test is the only thing
    keeping the copy in sync — a dist added to the release config but not to
    LOCKSTEP_DISTS silently stops receiving updates.
    """
    release = _release_config()
    expected = set(release["pip_publish_order"]) | set(release.get("git_publish_order", []))
    assert set(LOCKSTEP_DISTS) == expected


def _write(tmp_path: Path, deps: list[str]) -> Path:
    pyproject = tmp_path / "pyproject.toml"
    body = ", ".join(f'"{d}"' for d in deps)
    pyproject.write_text(
        f'[project]\nname = "p"\nversion = "0.1.0"\ndependencies = [{body}]\n',
        encoding="utf-8",
    )
    return pyproject


def test_rewrite_moves_every_lockstep_dist(tmp_path):
    """The regression: collateral lockstep dists must move, not just the headline ones."""
    pyproject = _write(
        tmp_path,
        [
            "haywire-studio==0.0.33",
            "haybale-marketplace~=0.0.33",
            "haybale-studio~=0.0.32",
            "haybale-core~=0.0.33",
            "haybale-mytest",
        ],
    )
    result = tomllib.loads(rewrite_pins(pyproject, "0.0.34"))
    deps = result["project"]["dependencies"]

    assert "haybale-core>=0.0.34" in deps
    assert "haybale-studio>=0.0.34" in deps
    assert "haywire-studio>=0.0.34" in deps
    assert "haybale-marketplace>=0.0.34" in deps


def test_rewrite_leaves_non_lockstep_deps_untouched(tmp_path):
    pyproject = _write(tmp_path, ["haywire-studio>=0.0.33", "haybale-mytest", "requests>=2.0"])
    deps = tomllib.loads(rewrite_pins(pyproject, "0.0.34"))["project"]["dependencies"]

    assert "haybale-mytest" in deps
    assert "requests>=2.0" in deps


@pytest.mark.parametrize("declared", ["~=0.0.33", ">=0.0.33", "==0.0.33", ">0.0.33"])
def test_rewrite_normalizes_lockstep_to_floor(tmp_path, declared):
    """Lockstep dists always land on ``>=``.

    A ceiling on a lockstep dist is never the author's considered policy — it is
    whatever the tool that wrote the line happened to emit — and a ``~=0.0.X``
    ceiling blocks the 0.1.0 release outright. Non-lockstep deps keep the
    author's operator; these do not.
    """
    pyproject = _write(tmp_path, [f"haybale-core{declared}"])
    deps = tomllib.loads(rewrite_pins(pyproject, "0.0.34"))["project"]["dependencies"]

    assert deps == ["haybale-core>=0.0.34"]


def test_declared_floor_reads_the_pin(tmp_path):
    pyproject = _write(tmp_path, ["haywire-studio>=0.0.34"])
    assert declared_floor(pyproject, "haywire-studio") == "0.0.34"

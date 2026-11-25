"""A project's heaps, derived from pyproject.toml and layered with hand-written [[heaps]] (ADR 0096)."""

from __future__ import annotations

from pathlib import Path

import pytest

from haywire.core.marketstall import derive_heaps, parse_project_marketplace, refresh

pytestmark = pytest.mark.unit


def _library(folder: Path, name: str, *, label: str = "", linked: list[str] | None = None) -> Path:
    """Write a minimal library: pyproject.toml plus a package holding haybale.toml."""
    module = folder / name.replace("-", "_")
    module.mkdir(parents=True)
    (module / "__init__.py").write_text("")
    lines = [f'name = "{name}"', 'version = "0.1.0"']
    if label:
        lines.append(f'label = "{label}"')
    if linked:
        lines.append("linked_libraries = [" + ", ".join(f'"{m}"' for m in linked) + "]")
    (module / "haybale.toml").write_text("\n".join(lines) + "\n")
    (folder / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
    return folder


def _project(root: Path, body: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text('[project]\nname = "proj"\n' + body)
    return root


def test_workspace_members_are_heaps(tmp_path: Path) -> None:
    project = _project(tmp_path / "proj", '[tool.uv.workspace]\nmembers = ["barn/*"]\n')
    _library(project / "barn" / "hay-b", "hay-b")
    _library(project / "barn" / "hay-a", "hay-a", label="A", linked=["haybale_core"])

    heaps = derive_heaps(project)

    assert [h["name"] for h in heaps] == ["hay-a", "hay-b"]
    assert heaps[0] == {
        "name": "hay-a",
        "path": str((project / "barn" / "hay-a").resolve()),
        "label": "A",
        "linked_libraries": ["haybale-core"],
    }


def test_a_member_without_haybale_toml_is_no_heap(tmp_path: Path) -> None:
    project = _project(tmp_path / "proj", '[tool.uv.workspace]\nmembers = ["packages/*"]\n')
    (project / "packages" / "tool" / "tool").mkdir(parents=True)
    (project / "packages" / "tool" / "tool" / "__init__.py").write_text("")
    (project / "packages" / "tool" / "pyproject.toml").write_text('[project]\nname = "tool"\n')

    assert derive_heaps(project) == []


def test_excluded_members_are_no_heaps(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "proj", '[tool.uv.workspace]\nmembers = ["barn/*"]\nexclude = ["barn/hay-skip"]\n'
    )
    _library(project / "barn" / "hay-keep", "hay-keep")
    _library(project / "barn" / "hay-skip", "hay-skip")

    assert [h["name"] for h in derive_heaps(project)] == ["hay-keep"]


def test_a_path_source_and_the_libraries_beside_it_are_heaps(tmp_path: Path) -> None:
    """A --dev project names a few dev-repo libraries; the rest of that barn/ comes along."""
    dev_barn = tmp_path / "haywire-repo" / "barn"
    _library(dev_barn / "haybale-core", "haybale-core")
    _library(dev_barn / "haybale-audio", "haybale-audio")
    (tmp_path / "haywire-repo" / "packages" / "haywire-core").mkdir(parents=True)
    project = _project(
        tmp_path / "proj",
        "[tool.uv.sources]\n"
        'haybale-core = { path = "../haywire-repo/barn/haybale-core", editable = true }\n'
        'haywire-core = { path = "../haywire-repo/packages/haywire-core", editable = true }\n'
        'numpy = { index = "pytorch" }\n',
    )

    heaps = derive_heaps(project)

    assert [h["name"] for h in heaps] == ["haybale-core", "haybale-audio"]
    assert heaps[1]["path"] == str((dev_barn / "haybale-audio").resolve())


def test_no_pyproject_means_no_heaps(tmp_path: Path) -> None:
    assert derive_heaps(tmp_path) == []


def test_a_hand_written_heap_replaces_the_derived_one_and_adds_its_own(tmp_path: Path) -> None:
    project = _project(tmp_path / "proj", '[tool.uv.workspace]\nmembers = ["barn/*"]\n')
    _library(project / "barn" / "hay-a", "hay-a")
    _library(project / "barn" / "hay-b", "hay-b")
    (project / ".haywire").mkdir()
    (project / ".haywire" / "marketplace.toml").write_text(
        '[[heaps]]\nname = "HAY-A"\npath = "/elsewhere/hay-a"\n\n'
        '[[heaps]]\nname = "hay-far"\npath = "/far"\n'
    )

    parsed = parse_project_marketplace(project / ".haywire" / "marketplace.toml")

    assert [h["name"] for h in parsed.heaps] == ["HAY-A", "hay-far"]
    assert [h["name"] for h in parsed.all_heaps] == ["hay-b", "HAY-A", "hay-far"]


def test_a_project_without_a_marketplace_file_still_has_its_heaps(tmp_path: Path) -> None:
    project = _project(tmp_path / "proj", '[tool.uv.workspace]\nmembers = ["barn/*"]\n')
    _library(project / "barn" / "hay-a", "hay-a")

    parsed = parse_project_marketplace(project / ".haywire" / "marketplace.toml")

    assert parsed.heaps == []
    assert [h["name"] for h in parsed.all_heaps] == ["hay-a"]


def test_refresh_shadows_derived_heaps_and_writes_only_hand_written_ones(tmp_path: Path) -> None:
    project = _project(tmp_path / "proj", '[tool.uv.workspace]\nmembers = ["barn/*"]\n')
    _library(project / "barn" / "hay-a", "hay-a")
    global_path = tmp_path / "global.toml"
    global_path.write_text('[[haybales]]\nname = "hay-a"\nversion = "1.0.0"\n')
    project_path = project / ".haywire" / "marketplace.toml"

    report = refresh(global_path=global_path, project_path=project_path, cache_dir=tmp_path / "c")

    assert report.haybales_resolved == 0
    written = parse_project_marketplace(project_path)
    assert written.heaps == []
    assert written.caches == []
    assert (project / ".haywire" / ".gitignore").read_text() == "*\n"

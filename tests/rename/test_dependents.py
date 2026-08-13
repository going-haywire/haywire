"""Sibling barn libraries referencing the renamed library."""

from __future__ import annotations

import pytest


def _barn_lib(root, dist, *, linked=None, deps=None):
    module = dist.replace("-", "_").lower()
    lib = root / "barn" / dist
    pkg = lib / module
    pkg.mkdir(parents=True)
    linked_line = ""
    if linked:
        entries = ", ".join(f'"{x}"' for x in linked)
        linked_line = f"linked_libraries = [{entries}]\n"
    (pkg / "haybale.toml").write_text(f'name = "{dist}"\nversion = "0.1.0"\n{linked_line}')
    dep_line = ""
    if deps:
        entries = ", ".join(f'"{x}"' for x in deps)
        dep_line = f"dependencies = [{entries}]\n"
    (lib / "pyproject.toml").write_text(f'[project]\nname = "{dist}"\n{dep_line}')
    return lib


@pytest.mark.unit
def test_finds_dependent_via_linked_libraries(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    _barn_lib(tmp_path, "hay-src")
    _barn_lib(tmp_path, "hay-dependent", linked=["hay_src"])

    dependents, blockers = find_dependents(tmp_path, "hay-src")
    assert not blockers
    assert [d.name for d in dependents] == ["hay-dependent"]


@pytest.mark.unit
def test_finds_dependent_via_pyproject_dependency(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    _barn_lib(tmp_path, "hay-src")
    _barn_lib(tmp_path, "hay-dependent", deps=["hay-src"])

    dependents, _ = find_dependents(tmp_path, "hay-src")
    assert [d.name for d in dependents] == ["hay-dependent"]


@pytest.mark.unit
def test_finds_dependent_via_import(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    _barn_lib(tmp_path, "hay-src")
    dep = _barn_lib(tmp_path, "hay-dependent")
    (dep / "hay_dependent" / "use.py").write_text("from hay_src.nodes import Adder\n")

    dependents, _ = find_dependents(tmp_path, "hay-src")
    assert [d.name for d in dependents] == ["hay-dependent"]


@pytest.mark.unit
def test_finds_dependent_via_registry_key_literal(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    _barn_lib(tmp_path, "hay-src")
    dep = _barn_lib(tmp_path, "hay-dependent")
    (dep / "hay_dependent" / "w.py").write_text('K = "hay-src:widget:Thing"\n')

    dependents, _ = find_dependents(tmp_path, "hay-src")
    assert [d.name for d in dependents] == ["hay-dependent"]


@pytest.mark.unit
def test_unrelated_library_is_not_a_dependent(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    _barn_lib(tmp_path, "hay-src")
    _barn_lib(tmp_path, "hay-other", linked=["haybale_core"])

    assert find_dependents(tmp_path, "hay-src")[0] == []


@pytest.mark.unit
def test_the_library_itself_is_never_its_own_dependent(tmp_path):
    from haywire_studio.packaging.rename.checks import find_dependents

    src = _barn_lib(tmp_path, "hay-src")
    (src / "hay_src" / "internal.py").write_text("from hay_src.types import X\n")

    assert find_dependents(tmp_path, "hay-src")[0] == []

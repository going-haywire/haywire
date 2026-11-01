"""haybale-example's demo model catalog: every file registers; one entry carries two precisions."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.catalog import CatalogRegistry


def _catalog_folder() -> Path:
    return Path(str(importlib.import_module("haybale_example").__file__)).parent / "catalog"


@pytest.mark.unit
def test_demo_catalog_parses(test_injector) -> None:
    folder = _catalog_folder()
    identity = LibraryIdentity(
        label="Example",
        name="haybale-example",
        folder_path=str(folder.parent),
        module_name="haybale_example",
    )
    registry = CatalogRegistry()

    registry.add_folder(str(folder), identity)

    files = sorted(p.stem for p in folder.glob("*.json"))
    assert len(files) == 3
    assert sorted(registry.list_names()) == [f"haybale-example:catalog:{stem}" for stem in files]
    two = [e for e in registry.entries() if len(e.resources) == 2]
    assert two, "one entry offers two variants"
    assert sorted(r.precision or "" for r in two[0].resources) == ["fp16", "fp32"]
    for entry in registry.entries():
        for resource in entry.resources:
            assert resource.sha256 is not None
            assert resource.size is not None
            assert resource.size < 20_000_000

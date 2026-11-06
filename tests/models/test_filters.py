"""Which catalog rows a selection of filter chips keeps."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from haywire.core.catalog import CatalogEntry, Resource
from haywire.core.library.identity import LibraryIdentity

from haybale_models.filters import FILTER_FIELDS, entry_facts, row_matches, values_on_offer

pytestmark = pytest.mark.unit


def _resource() -> Resource:
    return Resource(platform="pytorch", type="pth", size=1, sha256=None, urls=(), files=())


def _entry(**overrides: Any) -> CatalogEntry:
    fields: dict[str, Any] = {
        "name": "m",
        "author": "",
        "license": "MIT",
        "architecture": "esrgan",
        "scale": 4,
        "purpose": ["SR"],
        "tags": ["anime", "photo"],
        "description": "",
        "size": None,
        "input_channels": None,
        "output_channels": None,
        "requires": {},
        "resources": (_resource(),),
        "document": {},
        "path": Path("m.json"),
        "content_hash": "",
        "identity": None,
        "library": LibraryIdentity(label="Alpha", name="a", folder_path="", module_name="a"),
    }
    fields.update(overrides)
    return CatalogEntry(**fields)


def _facts(entry: CatalogEntry, *, on_machine: bool = False, needed: bool = False) -> dict[str, set[str]]:
    return entry_facts(entry, on_machine=on_machine, needed=needed)


def test_the_fields_and_their_order() -> None:
    assert [label for _key, label in FILTER_FIELDS] == [
        "Library",
        "Purpose",
        "Tags",
        "Architecture",
        "Scale",
        "Commercial use",
        "Status",
    ]


def test_facts_of_an_entry() -> None:
    facts = _facts(_entry())
    assert facts["library"] == {"Alpha"}
    assert facts["purpose"] == {"SR"}
    assert facts["tags"] == {"anime", "photo"}
    assert facts["architecture"] == {"esrgan"}
    assert facts["scale"] == {"4x"}
    assert facts["commercial"] == {"non-commercial"}
    assert facts["status"] == {"available"}


def test_a_flagged_entry_reads_commercial() -> None:
    assert _facts(_entry(commercial=True))["commercial"] == {"commercial"}


def test_status_is_per_resource() -> None:
    entry = _entry()
    assert _facts(entry, on_machine=True)["status"] == {"on this machine"}
    assert _facts(entry, needed=True)["status"] == {"available", "needed"}


def test_missing_values_add_no_fact() -> None:
    facts = _facts(_entry(architecture="", scale=None, tags=[], purpose=[]))
    for key in ("architecture", "scale", "tags", "purpose"):
        assert facts[key] == set()


def test_every_field_is_offered_however_many_values_it_has() -> None:
    offered = values_on_offer(
        [_facts(_entry(architecture="esrgan", tags=[])), _facts(_entry(architecture="compact", tags=[]))]
    )
    assert list(offered) == [key for key, _label in FILTER_FIELDS]
    assert offered["architecture"] == ["compact", "esrgan"]
    assert offered["library"] == ["Alpha"]
    assert offered["tags"] == []


def test_scale_sorts_numerically() -> None:
    offered = values_on_offer([_facts(_entry(scale=s)) for s in (10, 2, 4)])
    assert offered["scale"] == ["2x", "4x", "10x"]


def test_or_within_a_field_and_between_fields() -> None:
    facts = _facts(_entry())
    assert row_matches(facts, {"tags": {"anime", "cartoon"}})
    assert row_matches(facts, {"tags": {"anime"}, "scale": {"4x"}})
    assert not row_matches(facts, {"tags": {"anime"}, "scale": {"2x"}})


def test_an_entry_without_the_value_does_not_match() -> None:
    assert not row_matches(_facts(_entry(architecture="")), {"architecture": {"esrgan"}})


def test_nothing_selected_matches_everything() -> None:
    assert row_matches(_facts(_entry()), {})
    assert row_matches(_facts(_entry()), {"tags": set()})

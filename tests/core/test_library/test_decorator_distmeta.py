"""The decorator fills LibraryMetadata's PEP 621 half from the installed dist.

An author writes these in pyproject.toml only. The decorator carries the
Haywire-specific fields, which have no packaging equivalent and must survive
into an installed wheel — hence kwargs rather than [tool.haywire], which the
wheel does not contain.
"""

import pytest

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library


def _make(**kwargs):
    @library(id="core", label="Core", **kwargs)
    class _Lib(BaseLibrary):
        pass

    # Attribute the class to an installed distribution's module so the
    # decorator can resolve it; haybale_core is installed in this workspace.
    return _Lib


def test_version_comes_from_the_distribution_not_a_kwarg(monkeypatch):
    import haywire.core.library.decorator as dec

    monkeypatch.setattr(dec, "_dist_for_module", lambda _m: "haybale-core")
    identity = _make().class_identity
    assert identity.version
    assert identity.version != "1.0.0"  # the old hardcoded default


def test_description_and_tags_come_from_the_distribution(monkeypatch):
    import haywire.core.library.decorator as dec

    monkeypatch.setattr(dec, "_dist_for_module", lambda _m: "haybale-core")
    identity = _make().class_identity
    assert identity.description
    assert isinstance(identity.tags, list)


def test_removed_kwargs_are_ignored_not_fatal(monkeypatch):
    """Barn libraries still pass these until the author-facing migration."""
    import haywire.core.library.decorator as dec

    monkeypatch.setattr(dec, "_dist_for_module", lambda _m: "haybale-core")
    identity = _make(
        version="9.9.9",
        description="stale decorator copy",
        author="Stale",
        author_url="https://stale",
        url="https://stale",
        tags=["stale"],
    ).class_identity
    assert identity.version != "9.9.9"
    assert identity.description != "stale decorator copy"
    assert "stale" not in identity.tags


def test_haywire_specific_kwargs_are_carried():
    identity = _make(
        os=["macos", "linux"],
        examples_path="examples/OVERVIEW.md",
        tests_path="tests/",
        linked_libraries=["haybale_studio"],
        on_reload="restart",
    ).class_identity
    assert identity.os == ["macos", "linux"]
    assert identity.examples_path == "examples/OVERVIEW.md"
    assert identity.tests_path == "tests/"
    assert identity.linked_libraries == ["haybale_studio"]
    assert identity.on_reload == "restart"


def test_dependencies_keyword_still_maps_to_linked_libraries():
    """The shim stays until the author-facing migration rewrites the libraries."""
    identity = _make(dependencies=["haybale_core"]).class_identity
    assert identity.linked_libraries == ["haybale_core"]


def test_id_is_required():
    with pytest.raises(ValueError, match="id"):

        @library(label="No Id")
        class _Lib(BaseLibrary):
            pass


def test_uninstalled_module_leaves_pep621_fields_empty(monkeypatch):
    """A library imported from a path with no distribution still loads."""
    import haywire.core.library.decorator as dec

    monkeypatch.setattr(dec, "_dist_for_module", lambda _m: None)
    identity = _make().class_identity
    assert identity.version == ""
    assert identity.label == "Core"  # decorator-authored fields unaffected


def test_transitional_fields_are_gone():
    """url and author were placeholders for homepage_url and authors.

    Not an absence check for its own sake: while both spellings existed a
    consumer could read the decorator-authored one and silently get a value
    pyproject.toml never sanctioned.
    """
    from dataclasses import fields

    from haywire.core.library.identity import LibraryIdentity

    names = {f.name for f in fields(LibraryIdentity)}
    assert "url" not in names
    assert "author" not in names
    assert {"homepage_url", "authors"} <= names

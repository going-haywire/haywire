"""LibraryMetadata is the shape both the runtime identity and the feed row share.

The detail renderer takes the base, so a field present on one subclass and absent
from the other would force it to branch — which is what this base exists to avoid.
"""

from dataclasses import fields

from haywire.core.library.identity import LibraryIdentity
from haywire.core.library.metadata import LibraryMetadata
from haywire.core.marketstall.types import Haybale

SHARED_FIELDS = {
    "label",
    "version",
    "description",
    "authors",
    "tags",
    "linked_libraries",
    "on_reload",
    "os",
    "docs_path",
    "examples_path",
    "tests_path",
    "homepage_url",
    "documentation_url",
    "author_url",
    "issues_url",
}


def test_base_carries_exactly_the_shared_fields():
    assert {f.name for f in fields(LibraryMetadata)} == SHARED_FIELDS


def test_identity_extends_the_base():
    assert issubclass(LibraryIdentity, LibraryMetadata)
    assert SHARED_FIELDS <= {f.name for f in fields(LibraryIdentity)}


def test_haybale_extends_the_base():
    assert issubclass(Haybale, LibraryMetadata)
    assert SHARED_FIELDS <= {f.name for f in fields(Haybale)}


def test_identity_adds_its_own_concerns():
    own = {f.name for f in fields(LibraryIdentity)} - SHARED_FIELDS
    assert {"id", "folder_path", "module_name", "file_watcher"} <= own


def test_haybale_adds_its_own_concerns():
    own = {f.name for f in fields(Haybale)} - SHARED_FIELDS
    assert {"name", "require", "source", "install_spec", "origin"} <= own


def test_haybale_carries_no_duplicate_spellings():
    """The base's fields must not sit beside the ones they replace.

    Not an absence check for its own sake — a subclass redeclaring `authors` as
    `author`, or keeping `dependencies` next to `linked_libraries`, silently
    shadows the base and reintroduces the split this base exists to close.
    """
    names = {f.name for f in fields(Haybale)}
    superseded = {
        "dependencies",  # -> linked_libraries
        "author",  # -> authors
        "source_url",  # -> origin
        "docs_url",  # -> docs_path
        "examples_url",  # -> examples_path
        "tests_url",  # -> tests_path
    }
    assert not (superseded & names)


def test_every_base_field_defaults():
    """Dataclass inheritance requires it, and it is why LibraryIdentity's
    previously-required fields become optional."""
    assert LibraryMetadata() is not None


def test_a_renderer_can_read_either_shape_through_the_base():
    def render(meta: LibraryMetadata) -> tuple[str, str, list[str]]:
        return meta.label, meta.version, meta.authors

    identity = LibraryIdentity(id="demo", label="Demo", version="1.0.0", authors=["Ada"], folder_path="/tmp")
    row = Haybale(name="haybale-demo", label="Demo", version="1.0.0", authors=["Ada"])

    assert render(identity) == render(row) == ("Demo", "1.0.0", ["Ada"])


def test_linked_libraries_holds_module_names_on_both():
    """Module names are the authored form; pip-name conversion happens at the
    point of use, not in the metadata."""
    identity = LibraryIdentity(id="d", linked_libraries=["haybale_studio"])
    row = Haybale(name="haybale-d", linked_libraries=["haybale_studio"])
    assert identity.linked_libraries == row.linked_libraries == ["haybale_studio"]


def test_reload_action_available_on_both():
    from haywire.core.library.identity import LibraryReloadAction

    assert Haybale(name="x", on_reload="restart").reload_action is LibraryReloadAction.RESTART
    assert LibraryIdentity(id="x", on_reload="refresh").reload_action is LibraryReloadAction.REFRESH
